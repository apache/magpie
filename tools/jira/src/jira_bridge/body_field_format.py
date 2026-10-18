# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Parse, normalise and rewrite the ``### Field`` sections of a GitHub issue body.

The tracker issue body is a sequence of `### <FieldName>` headings,
each followed by the field's value. This module exposes a pure
parser/replacer so the CLI can run without ever bringing the body
into the agent's context, and so the (numerous) tricky edge cases
can be unit-tested in isolation. It is the one implementation of the
body-field contract (tools/body-field-contract/contract.md): every reader and
writer of a field, generate-cve-json included, goes through it.

The contract:

- lines end at ``\\n``, ``\\r\\n`` or ``\\r`` (CommonMark's line endings,
  not every character ``str.splitlines`` breaks on);
- **every line that starts, at column 0, with ``###`` followed by a space,
  a tab or the end of the line ends the current field and starts the next
  one, code block or not.** No fence, Jira macro or duplicate heading left
  in one field's text can therefore make it absorb the next field (a
  private mailing-list URL, say): a value is always exactly one section of
  that split. The heading's name is the rest of the line with surrounding
  spaces and tabs and a closing run of ``#`` dropped, compared
  case-sensitively; normalising against known field names also collapses
  inner whitespace;
- **a heading inside a closed code block never starts a field.** A closed
  block is a CommonMark fence pair (an opener of three or more backticks or
  tildes indented at most three spaces, closed only by a run of the *same*
  character, at least as long, followed by nothing but spaces or tabs; a
  backtick opener whose info string holds a backtick is not a fence) or a
  Jira ``{code}`` / ``{code:…}`` / ``{noformat}`` block that opens on a line
  starting with the macro and closes on the bare macro. A block left open
  at the end of the body marks nothing. Among the ``### <name>`` lines, the
  field is the one outside every closed block; a heading inside a closed
  block never starts a field, so a field whose only copies are inside
  closed blocks is absent: a PoC quoting ``### Severity`` inside a fence is
  never taken for the field, whether or not the real heading exists. Two
  or more copies outside closed blocks are a duplicate;
- **a Jira macro a renderer may open mid-line is a decision.** Jira opens
  ``{code}`` / ``{noformat}`` anywhere in a line; a line that leaves such a
  macro open (outside closed blocks) and is followed, before the macro's
  close, by a field boundary is reported as ``macro-ambiguous``, and the
  fields it touches are refused, rather than either reading winning. A
  macro opened and closed on the same line is text;
- a heading-shaped line that does not end a field (indented, behind a
  block-quote or list marker) is content. A renderer may still show one as
  a heading, so :func:`normalise` reports one naming a known field as a
  decision (fail closed) rather than guessing what a renderer makes of it;
- the original body is preserved exactly when no change is needed
  (idempotent rewrite).

:func:`normalise` rewrites a body into the canonical shape every reader
agrees on (LF line endings, ``### Name`` headings, fences closed in the
field they open in, no repeated field) and reports what it changed and
what it would not decide on its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field


class FieldNotFoundError(LookupError):
    """Raised when the requested field heading is absent from the body."""


class DuplicateFieldError(FieldNotFoundError):
    """Raised when the requested field heading appears more than once outside closed code blocks."""


class AmbiguousFieldError(FieldNotFoundError):
    """Raised when readers could disagree on the body's fields: a heading-shaped
    line naming the requested field sits where a renderer may show it as a
    heading although it ends no field, or a rewrite would change another field."""


# A CommonMark line: content plus its ending (`\n`, `\r\n` or `\r`), or a last unterminated line.
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z")
# A fence line: up to three spaces, a run of 3+ backticks or tildes, the rest (info string or nothing).
_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
# A field boundary: `###` at column 0, then a space, a tab or the end of the line.
_BOUNDARY = re.compile(r"###(?:[ \t]|$)")
# A Jira block opener: a line starting (after spaces or tabs) with `{code}`, `{code:…}` or `{noformat}`.
_JIRA_OPEN = re.compile(r"[ \t]*\{(code|noformat)(?::[^}]*)?\}")
# A Jira block macro anywhere in a line, as Jira's renderer sees one.
_JIRA_MACRO = re.compile(r"\{(code|noformat)(?::[^}]*)?\}")


def split_lines(body: str) -> list[str]:
    """``body`` split into lines with their endings kept, at CommonMark line endings only."""
    return _LINE.findall(body)


def _content(line: str) -> str:
    """``line`` without its line ending."""
    return line.rstrip("\r\n")


def is_boundary(line: str) -> bool:
    """Whether ``line`` ends a field: ``###`` at column 0, then a space, a tab or the end of the line."""
    return _BOUNDARY.match(_content(line)) is not None


def _opens_fence(match: re.Match[str] | None) -> bool:
    return match is not None and not (match.group(2)[0] == "`" and "`" in match.group(3))


def _blocks(lines: list[str], *, jira: bool, max_indent: int = 3) -> list[tuple[int, int | None]]:
    """``(opener, closer)`` line indices of every code block, ``closer`` None for one left open.

    The one block scanner: CommonMark fences (an opener indented at most
    ``max_indent`` spaces; the closer uses the opener's character, is at
    least as long, and carries nothing but spaces or tabs after the run; a
    backtick opener whose info string holds a backtick is not a fence), and
    with ``jira`` also Jira ``{code}`` / ``{noformat}`` blocks, opened on a
    line starting with the macro (and not closing it on the same line) and
    closed on the bare macro. Inside a block nothing else opens. A block
    left open runs to the end of ``lines``.
    """
    spans: list[tuple[int, int | None]] = []
    fence: tuple[str, int] | None = None
    macro: str | None = None
    start = 0
    for index, raw in enumerate(lines):
        content = _content(raw)
        if fence is not None:
            match = _FENCE.match(content)
            if (
                match
                and match.group(2)[0] == fence[0]
                and len(match.group(2)) >= fence[1]
                and not match.group(3).strip(" \t")
            ):
                spans.append((start, index))
                fence = None
            continue
        if macro is not None:
            if "{" + macro + "}" in content:
                spans.append((start, index))
                macro = None
            continue
        match = _FENCE.match(content)
        if _opens_fence(match):
            assert match is not None
            if len(match.group(1)) <= max_indent:
                fence, start = (match.group(2)[0], len(match.group(2))), index
                continue
        if jira:
            opened = _JIRA_OPEN.match(content)
            if opened and content.count("{" + opened.group(1)) == 1:
                macro, start = opened.group(1), index
    if fence is not None or macro is not None:
        spans.append((start, None))
    return spans


def _roles(spans: list[tuple[int, int | None]], count: int) -> list[str]:
    roles = ["text"] * count
    for start, end in spans:
        roles[start] = "open"
        for index in range(start + 1, count if end is None else end):
            roles[index] = "code"
        if end is not None:
            roles[end] = "close"
    return roles


def fence_roles(lines: Iterable[str]) -> list[str]:
    """Each line's role in CommonMark fences: ``"open"``, ``"close"``, ``"code"`` or ``"text"``.

    How a Markdown renderer sees fences (no Jira blocks): an unclosed fence
    runs to the end of ``lines``. Field boundaries never depend on it; see
    :func:`closed_block_lines` for the blocks that choose a field's heading.
    """
    lines = list(lines)
    return _roles(_blocks(lines, jira=False), len(lines))


def closed_block_lines(lines: Iterable[str]) -> list[bool]:
    """Per line, whether it sits in a closed code block (opener and closer included).

    Closed blocks are CommonMark fence pairs and Jira ``{code}`` /
    ``{noformat}`` blocks; a block left open at the end marks nothing.
    """
    lines = list(lines)
    inside = [False] * len(lines)
    for start, end in _blocks(lines, jira=True):
        if end is not None:
            inside[start : end + 1] = [True] * (end + 1 - start)
    return inside


def _left_open(content: str) -> str | None:
    """The Jira macro a renderer leaves open at the end of ``content``, pairing
    ``{code}`` / ``{code:…}`` / ``{noformat}`` left to right; None when every
    one it opens is closed on the line."""
    open_macro: str | None = None
    for match in _JIRA_MACRO.finditer(content):
        if open_macro is None:
            open_macro = match.group(1)
        elif match.group(0) == "{" + open_macro + "}":
            open_macro = None
    return open_macro


def macro_spans(lines: list[str]) -> list[tuple[int, list[int]]]:
    """``(opener, boundaries)`` line indices for each Jira macro a renderer may
    open where this parser does not, with the field boundaries it would hide.

    A line outside closed blocks that leaves ``{code}`` / ``{noformat}`` open
    (mid-line, or after other macros on its line) and a later line closing
    it, with one or more field boundaries between: Jira shows those headings
    as code, this parser as fields. Which reading is right depends on the
    renderer, so it is a decision, never a guess.
    """
    inside = closed_block_lines(lines)
    spans: list[tuple[int, list[int]]] = []
    index = 0
    while index < len(lines):
        macro = None if inside[index] else _left_open(_content(lines[index]))
        if macro is None:
            index += 1
            continue
        closer = "{" + macro + "}"
        end = next((j for j in range(index + 1, len(lines)) if closer in _content(lines[j])), None)
        if end is None:
            index += 1
            continue
        boundaries = [j for j in range(index + 1, end) if is_boundary(lines[j])]
        if boundaries:
            spans.append((index, boundaries))
        index = end + 1
    return spans


def _macro_fields(lines: list[str]) -> set[str]:
    """Names of every field a :func:`macro_spans` span touches: the field the
    macro opens in and each field it would hide."""
    names = boundary_names(lines)
    touched: set[str] = set()
    for opener, boundaries in macro_spans(lines):
        enclosing = next((names[i] for i in range(opener, -1, -1) if names[i] is not None), None)
        if enclosing is not None:
            touched.add(enclosing)
        touched.update(str(names[i]) for i in boundaries)
    return touched


def _strip_closing(text: str) -> str:
    """``text`` (already stripped) without a closing run of ``#``: one that stands
    alone or follows a space or tab. Index scans only, linear in the length."""
    end = len(text)
    while end > 0 and text[end - 1] == "#":
        end -= 1
    if end == len(text):
        return text
    if end == 0:
        return ""
    if text[end - 1] in " \t":
        return text[:end].rstrip(" \t")
    return text


def heading_name(line: str) -> str | None:
    """The name of a level-3 ATX heading line, or None when ``line`` is not one.

    Up to three spaces of indent, ``###``, then a space or tab (or nothing).
    Surrounding spaces and tabs and a closing run of ``#`` are dropped; a bare
    ``###`` is a heading with an empty name. Index scans only: linear in the
    line length whatever its whitespace. Only a heading at column 0
    (:func:`is_boundary`) ends a field.
    """
    content = _content(line)
    start = 0
    while start < 3 and content[start : start + 1] == " ":
        start += 1
    if not content.startswith("###", start):
        return None
    rest = content[start + 3 :]
    if rest[:1] not in ("", " ", "\t"):
        return None
    return _strip_closing(rest.strip(" \t"))


def boundary_names(lines: Iterable[str]) -> list[str | None]:
    """Per line, the name of the field it starts (``""`` for a bare ``###``), or None."""
    return [heading_name(line) if is_boundary(line) else None for line in lines]


def loose_heading_name(line: str) -> str | None:
    """The name of a level-3 heading behind block-quote / list markers or indent, else None.

    Skips whitespace and markers (``>``, a bullet or an ordered marker of one
    to nine digits followed by a space or tab) with one index that only moves
    forward, however many markers there are: O(len(line)), no cap.
    """
    content = _content(line)
    if "###" not in content:
        return None
    i, n = 0, len(content)
    while True:
        while i < n and content[i] in " \t":
            i += 1
        if i < n and content[i] == ">":
            i += 1
            continue
        if i + 1 < n and content[i] in "-*+" and content[i + 1] in " \t":
            i += 2
            continue
        j = i
        while j < n and j - i < 9 and content[j].isascii() and content[j].isdigit():
            j += 1
        if i < j < n - 1 and content[j] in ".)" and content[j + 1] in " \t":
            i = j + 2
            continue
        break
    rest = content[i:]
    if not rest.startswith("###") or rest[3:4] not in ("", " ", "\t"):
        return None
    return _strip_closing(rest[3:].strip(" \t"))


@dataclass(frozen=True)
class Section:
    """One field boundary (``### <Name>`` at column 0) and the lines up to the next."""

    name: str
    heading_line: str  # the original "### Name" line as it appeared
    body_lines: list[str]  # everything between this heading and the next boundary
    line_no: int = 0  # 1-based line number of the heading
    in_block: bool = False  # the heading sits in a closed code block

    @property
    def value(self) -> str:
        """The section's value, stripped: how copies of a field are compared."""
        return "".join(self.body_lines).strip()


def parse(body: str) -> tuple[list[str], list[Section]]:
    """Split ``body`` at every field boundary: the preamble (raw lines before the
    first one) and one :class:`Section` per boundary, in document order.

    The lines are kept with their endings, so the round-trip is byte-exact.
    """
    lines = split_lines(body)
    inside = closed_block_lines(lines)
    preamble: list[str] = []
    sections: list[Section] = []
    for number, (line, name) in enumerate(zip(lines, boundary_names(lines), strict=True), 1):
        if name is not None:
            sections.append(Section(name, line, [], number, inside[number - 1]))
        else:
            (sections[-1].body_lines if sections else preamble).append(line)
    return preamble, sections


def locate(sections: list[Section], field_name: str) -> int:
    """The index in ``sections`` of the field ``field_name``.

    The copy outside every closed code block: a heading inside one never
    starts a field. Raises :class:`FieldNotFoundError` when there is none
    (whatever copies closed blocks hold) and :class:`DuplicateFieldError`
    when two or more sit outside closed blocks.
    """
    outside = [i for i, s in enumerate(sections) if s.name == field_name and not s.in_block]
    if not outside:
        raise FieldNotFoundError(f"field not found: {field_name!r}")
    if len(outside) > 1:
        raise DuplicateFieldError(f"field {field_name!r} appears {len(outside)} times; refusing to guess")
    return outside[0]


def field_sections(sections: list[Section]) -> list[int]:
    """Indices, in document order, of the sections a reader takes for fields.

    Every section whose heading sits outside closed code blocks: a heading
    inside one never starts a field.
    """
    return [index for index, section in enumerate(sections) if not section.in_block]


def list_fields(body: str) -> list[str]:
    """Return the field names declared by the body, in document order.

    A heading inside a closed code block is quoted text, never a field.
    Duplicate field names are returned as many times
    as they appear so the caller can flag an ambiguous body (the rewrite
    refuses to touch duplicates — see :func:`replace_field`).
    """
    _, sections = parse(body)
    return [s.name for s in sections if not s.in_block]


def fold_name(name: str) -> str:
    """``name`` case-folded with its whitespace collapsed: how case-insensitive readers compare field names (the inert-block escapes)."""
    return " ".join(name.split()).casefold()


def collapse_name(name: str) -> str:
    """``name`` with its whitespace collapsed, case kept: how a heading matches a known field."""
    return " ".join(name.split())


@dataclass(frozen=True)
class NormaliseResult:
    """What :func:`normalise` produced.

    ``changes`` holds one ``{"line", "kind"}`` record per rewrite (1-based
    line numbers of the input body); ``needs_decision`` holds one
    ``{"field", "kind", "lines"}`` record per ambiguity left in ``text``.
    """

    text: str
    changes: list[dict[str, object]] = field(default_factory=list)
    needs_decision: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self, *, include_text: bool = False) -> dict[str, object]:
        out: dict[str, object] = {"changes": self.changes, "needs_decision": self.needs_decision}
        if include_text:
            out["text"] = self.text
        return out


def _selection(lines: list[str]) -> list[bool]:
    """Per field boundary, in order, whether it sits in a closed block: what picks each field."""
    inside = closed_block_lines(lines)
    return [inside[i] for i, line in enumerate(lines) if is_boundary(line)]


def _close_unclosed_fences(lines: list[str], origin: list[int], changes: list[dict[str, object]]) -> None:
    """Close, in place, each fence left open, in the field it opens in.

    The closer (the opener's indent and run) goes after the last non-blank
    line before the next field boundary, so it never moves into another
    field. A closer that would move any field heading into or out of a
    closed block is not added: the fence is left open, which marks nothing.
    ``origin`` maps each line to its input line number (0 for an added one).
    """
    for _ in range(len(lines) + 1):
        spans = _blocks(lines, jira=False)
        if not spans or spans[-1][1] is not None:
            return
        start = spans[-1][0]
        at = next((i for i in range(start + 1, len(lines)) if is_boundary(lines[i])), len(lines))
        while at > start + 1 and not _content(lines[at - 1]).strip(" \t"):
            at -= 1
        opener = _FENCE.match(_content(lines[start]))
        assert opener is not None  # an opener always matched
        candidate = list(lines)
        if at == len(candidate) and not candidate[-1].endswith(("\n", "\r")):
            candidate[-1] += "\n"
        candidate.insert(at, opener.group(1) + opener.group(2) + "\n")
        if _selection(candidate) != _selection(lines):
            return
        lines[:] = candidate
        origin.insert(at, 0)
        changes.append({"line": origin[start], "kind": "unclosed_fence"})


def _disputes(lines: list[str], origin: list[int], canonical: Mapping[str, str]) -> dict[str, list[int]]:
    """Known field name -> input lines of heading-shaped lines that end no field
    but a renderer may show as a heading (behind ``>`` or a list marker, or
    indented), outside a fence in CommonMark's view or a column-0-only one."""
    disputed: dict[str, list[int]] = {}
    if not canonical:
        return disputed
    lenient = fence_roles(lines)
    strict = _roles(_blocks(lines, jira=False, max_indent=0), len(lines))
    for index, line in enumerate(lines):
        if is_boundary(line) or (lenient[index] != "text" and strict[index] != "text"):
            continue
        name = loose_heading_name(line)
        if name and collapse_name(name) in canonical:
            disputed.setdefault(canonical[collapse_name(name)], []).append(origin[index])
    return disputed


def _comparable(sections: list[Section]) -> list[tuple[str, bool]]:
    """Each field heading's name and whether it sits in a closed block: what picks every field."""
    return [(s.name, s.in_block) for s in sections]


def normalise(
    body: str,
    known_fields: Iterable[str] | None = None,
    keep: Mapping[str, int] | None = None,
) -> NormaliseResult:
    """``body`` in the canonical shape every field reader agrees on.

    - ``\\r\\n`` and a lone ``\\r`` become ``\\n`` (kind ``line_endings``,
      recorded once, at the first such line);
    - a fence left open is closed in the field it opens in (kind
      ``unclosed_fence``, at the opener's line), unless that would move a
      field heading into or out of a closed block;
    - a field heading outside closed code blocks becomes ``### Name`` (kind
      ``heading``); with ``known_fields``, a name equal to a known field
      once whitespace-collapsed (case kept) takes the known spelling (kind
      ``heading_name``). Lines inside a closed block are never rewritten,
      so fenced payloads round-trip byte-exact;
    - a field repeated outside closed blocks: when every copy holds the
      same value (after stripping), the later copies are dropped (kind
      ``duplicate_dropped``, at each dropped heading); otherwise every copy
      stays and ``{"field", "kind": "duplicate", "lines"}`` goes to
      ``needs_decision`` — unless ``keep`` maps the field to the heading
      line of the copy to keep (a decision made elsewhere), which is then
      kept and the others dropped (kind ``duplicate_resolved``);
    - a heading-shaped line that ends no field (behind ``>`` or a list
      marker, or indented) is never rewritten; when it names a known field
      and sits outside a fence for either a CommonMark or a column-0-only
      reader, ``{"field", "kind": "container-heading", "lines"}`` goes to
      ``needs_decision`` instead of any reading winning;
    - a Jira macro left open mid-line before field boundaries
      (:func:`macro_spans`) gives ``{"field", "kind": "macro-ambiguous",
      "lines"}``: the first hidden field, then the opener's line and each
      hidden boundary's.

    Line numbers are the input body's. Normalising a normalised body
    changes nothing.
    """
    changes: list[dict[str, object]] = []
    canonical = {collapse_name(name): name for name in (known_fields or [])}

    lines: list[str] = []
    origin: list[int] = []
    first_cr: int | None = None
    for number, raw in enumerate(split_lines(body), 1):
        content = _content(raw)
        if raw[len(content) :] not in ("", "\n"):
            first_cr = first_cr or number
            raw = content + "\n"
        lines.append(raw)
        origin.append(number)
    if first_cr is not None:
        changes.append({"line": first_cr, "kind": "line_endings"})

    _close_unclosed_fences(lines, origin, changes)
    inside = closed_block_lines(lines)
    for index, line in enumerate(lines):
        if inside[index] or not is_boundary(line):
            continue
        content = _content(line)
        name = heading_name(content)
        if not name:
            continue
        spelled = canonical.get(collapse_name(name), name)
        wanted = f"### {spelled}"
        if wanted != content:
            lines[index] = wanted + line[len(content) :]
            changes.append({"line": origin[index], "kind": "heading" if spelled == name else "heading_name"})

    needs_decision: list[dict[str, object]] = [
        {"field": name, "kind": "container-heading", "lines": sorted(set(line_nos))}
        for name, line_nos in _disputes(lines, origin, canonical).items()
    ]
    names = boundary_names(lines)
    needs_decision.extend(
        {
            "field": names[boundaries[0]],
            "kind": "macro-ambiguous",
            "lines": [origin[opener], *(origin[i] for i in boundaries)],
        }
        for opener, boundaries in macro_spans(lines)
    )
    text = "".join(lines)
    preamble, sections = parse(text)
    copies_of: dict[str, list[Section]] = {}
    for section in sections:
        if section.name and not section.in_block:
            copies_of.setdefault(section.name, []).append(section)
    drop: dict[int, str] = {}
    for name, copies in copies_of.items():
        if len(copies) < 2:
            continue
        line_nos = [origin[s.line_no - 1] for s in copies]
        if len({s.value for s in copies}) == 1:
            dropped = line_nos[1:]
            kind = "duplicate_dropped"
        elif keep is not None and keep.get(name) in line_nos:
            dropped = [n for n in line_nos if n != keep[name]]
            kind = "duplicate_resolved"
        else:
            needs_decision.append({"field": name, "kind": "duplicate", "lines": line_nos})
            continue
        drop.update(dict.fromkeys(dropped, kind))
    if drop:
        kept = [s for s in sections if origin[s.line_no - 1] not in drop]
        rebuilt = list(preamble)
        for section in kept:
            rebuilt.append(section.heading_line)
            rebuilt.extend(section.body_lines)
        trailing_blank = text.endswith("\n\n")
        candidate = "".join(rebuilt)
        if not trailing_blank and candidate.endswith("\n\n"):
            # The dropped copy was last: its predecessor's spacer is now the body's end.
            candidate = candidate.rstrip("\n") + "\n"
        if _comparable(parse(candidate)[1]) == _comparable(kept):
            text = candidate
            changes.extend({"line": n, "kind": kind} for n, kind in drop.items())
        else:
            # Dropping a copy would move another field heading into or out of a
            # closed block: leave every copy and let a human decide.
            for name in sorted({s.name for s in sections if origin[s.line_no - 1] in drop}):
                lines_of = [origin[s.line_no - 1] for s in copies_of[name]]
                needs_decision.append({"field": name, "kind": "duplicate", "lines": lines_of})
    changes.sort(key=lambda c: (int(str(c["line"])), str(c["kind"])))
    return NormaliseResult(text=text, changes=changes, needs_decision=needs_decision)


_EOLS = ("\r\n", "\r", "\n")
_ANY_EOL = re.compile(r"\r\n|\r|\n")


def _is_blank_eol(line: str) -> bool:
    """Whether ``line`` is an empty line: nothing but its ending (LF, CRLF or CR)."""
    return line in _EOLS


def _eol_of(body: str, line: str) -> str:
    """The line ending ``line`` uses, else the body's first one, else LF."""
    ending = line[len(_content(line)) :]
    if ending:
        return ending
    first = _ANY_EOL.search(body)
    return first.group(0) if first else "\n"


def _strip_spacer_blanks(body_lines: list[str]) -> tuple[bool, list[str], bool]:
    """Strip up to one leading and one trailing blank-line spacer.

    Returns ``(had_leading, stripped_lines, had_trailing)`` so the
    caller can later re-emit with the same convention.
    """
    lines = list(body_lines)
    had_leading = bool(lines) and _is_blank_eol(lines[0])
    if had_leading:
        lines = lines[1:]
    had_trailing = bool(lines) and _is_blank_eol(lines[-1]) and len(lines) > 1
    # The `len(lines) > 1` guard is so a field whose *only* line
    # is a blank one (i.e. an empty value with one spacer) doesn't
    # get the same line both stripped and counted as "trailing".
    if had_trailing:
        lines = lines[:-1]
    return had_leading, lines, had_trailing


def _refuse_ambiguous(body: str, field_name: str) -> None:
    """Raise :class:`AmbiguousFieldError` when readers could disagree on ``field_name``.

    Run by every read and write, so no caller can skip it: no heading-shaped
    line naming ``field_name`` may sit where a renderer may show it as a
    heading although it ends no field, and no Jira macro a renderer may open
    mid-line may hide the field or open inside it (:func:`macro_spans`).
    """
    if field_name in _macro_fields(split_lines(body)):
        raise AmbiguousFieldError(
            f"field {field_name!r}: a Jira code or noformat macro opened mid-line would show "
            "field headings as code to a Jira reader; refusing to guess"
        )
    disputes = [d for d in normalise(body, [field_name]).needs_decision if d["kind"] == "container-heading"]
    if disputes:
        where = "; ".join(
            f"{d['field']!r} at line(s) {', '.join(str(n) for n in d['lines'])}"  # type: ignore[attr-defined]
            for d in disputes
        )
        raise AmbiguousFieldError(
            f"field {field_name!r}: markdown readers could disagree on this body's fields ({where}); "
            "refusing to guess"
        )


def extract_field(body: str, field: str) -> str:
    """Return the raw text value of ``### <field>``.

    The value runs from the field's heading (:func:`locate`) to the next
    field boundary. The blank-line spacer that conventionally separates the
    heading from the value, and the value from the next heading, is stripped
    so callers get the value as a user would copy-paste it. Internal blank
    lines are preserved.

    Raises :class:`FieldNotFoundError` if the heading does not exist,
    :class:`DuplicateFieldError` (a subclass) if it appears more than once
    outside closed code blocks, :class:`AmbiguousFieldError` (a subclass)
    if readers could disagree on it.
    """
    _refuse_ambiguous(body, field)
    _, sections = parse(body)
    _, stripped, _ = _strip_spacer_blanks(sections[locate(sections, field)].body_lines)
    return "".join(stripped)


def replace_field(body: str, field: str, new_value: str) -> str:
    """Return a new body with ``### <field>``'s value replaced.

    The replacement preserves:

    - the original heading line (including any trailing whitespace
      / line ending that was there);
    - everything outside the targeted section, byte-exact;
    - the blank-line spacer between this section and the next, if
      one was originally present;
    - the body's final line-ending style (LF vs CRLF) — we use the
      same convention as the file we read.

    The ``new_value`` is appended as-is and is **not** normalised:
    callers that want a trailing newline should include one in the
    value they pass. A value holding a line that would end the field
    (``###`` at column 0, then a space, a tab or nothing) is refused.

    Raises :class:`FieldNotFoundError` if the heading does not exist,
    :class:`DuplicateFieldError` (a subclass) if it appears more than once
    outside closed code blocks, :class:`AmbiguousFieldError` (a subclass)
    if readers could disagree on it or the rewrite would change another field.
    """
    _refuse_ambiguous(body, field)
    if any(is_boundary(line) for line in split_lines(new_value)):
        raise AmbiguousFieldError(
            f"field {field!r}: the new value holds a line starting with `###` that would end the field; "
            "refusing to rewrite it"
        )
    preamble, sections = parse(body)
    target_idx = locate(sections, field)
    target = sections[target_idx]
    had_leading, _, had_trailing = _strip_spacer_blanks(target.body_lines)
    is_last_section = target_idx == len(sections) - 1

    # Normalise the caller-supplied value:
    #   - strip any trailing blank-line spacer they may have
    #     accidentally included, so we don't double-stack blanks
    #     when we re-insert the spacer below;
    #   - ensure a single trailing newline if there's any content,
    #     so the next heading starts on its own line;
    #   - the empty-value case (caller passed "") produces an
    #     entirely empty content payload so the heading sits
    #     directly against the spacer / next heading.
    # Written in the body's own line-ending convention (the heading line's),
    # so a CRLF body stays CRLF and an unchanged value is byte-identical.
    eol = _eol_of(body, target.heading_line)
    normalised = _ANY_EOL.sub(eol, new_value)
    while normalised.endswith(eol * 2):
        normalised = normalised[: -len(eol)]
    if normalised and not normalised.endswith(eol):
        normalised += eol

    rebuilt_body_lines: list[str] = []
    if normalised:
        if had_leading:
            rebuilt_body_lines.append(eol)
        rebuilt_body_lines.extend(split_lines(normalised))
        if had_trailing and not is_last_section:
            rebuilt_body_lines.append(eol)
    else:
        # Empty value: collapse to a single blank-line spacer so the
        # next heading isn't glued to the current one. Don't stack
        # both leading and trailing spacers (that would render as
        # two blank lines, which reads worse than one in the tracker
        # UI). For the last section, emit nothing — the bare heading
        # line is sufficient.
        if not is_last_section and (had_leading or had_trailing):
            rebuilt_body_lines.append(eol)

    out: list[str] = list(preamble)
    for index, s in enumerate(sections):
        out.append(s.heading_line)
        out.extend(rebuilt_body_lines if index == target_idx else s.body_lines)
    new_body = "".join(out)
    _refuse_unsafe_rewrite(body, new_body, field, target_idx, target.body_lines, rebuilt_body_lines)
    return new_body


def _heading_shaped_lines(span: list[str]) -> list[int]:
    """1-based offsets in ``span`` of lines outside fences shaped like a level-3
    heading (behind any indent, ``>`` or list marker), whatever the name."""
    roles = fence_roles(span)
    return [
        i
        for i, (line, role) in enumerate(zip(span, roles, strict=True), 1)
        if role == "text" and loose_heading_name(line) is not None
    ]


def _refuse_unsafe_rewrite(
    old_body: str,
    new_body: str,
    field_name: str,
    target_idx: int,
    old_span: list[str],
    new_span: list[str],
) -> None:
    """Raise :class:`AmbiguousFieldError` unless rewriting ``field_name`` leaves
    every other field exactly as it was.

    The replaced span, before and after, must hold no heading-shaped line
    outside fences: whether such a line is a heading depends on the reader.
    And the rewritten body must parse to the same fields, each heading in or
    out of a closed block as before (so a fence in the new value cannot
    change which heading another field is read from), every other field
    byte-identical.
    """
    for label, span in (("current", old_span), ("new", new_span)):
        if _heading_shaped_lines(span):
            raise AmbiguousFieldError(
                f"field {field_name!r}: its {label} value holds a heading-shaped line that a reader "
                "could take for another field; refusing to rewrite it"
            )
    _, before = parse(old_body)
    _, after = parse(new_body)
    # The rewritten body must read the same to every reader: run the
    # nested-heading check over it, with every field of the old body as a
    # known name.
    known = [s.name for s in before if s.name]
    disputes = [
        d
        for d in normalise(new_body, known).needs_decision
        if d["kind"] in ("container-heading", "macro-ambiguous")
    ]
    if disputes:
        raise AmbiguousFieldError(
            f"field {field_name!r}: after the rewrite, markdown readers would disagree on the body's fields "
            f"({', '.join(sorted({str(d['field']) for d in disputes}))}); refusing to rewrite it"
        )
    if _comparable(before) != _comparable(after) or any(
        (b.heading_line, b.body_lines) != (a.heading_line, a.body_lines)
        for index, (b, a) in enumerate(zip(before, after, strict=True))
        if index != target_idx
    ):
        raise AmbiguousFieldError(
            f"field {field_name!r}: the rewrite would change another field; refusing to rewrite it"
        )
