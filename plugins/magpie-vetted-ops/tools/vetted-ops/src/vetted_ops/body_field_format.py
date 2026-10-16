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
can be unit-tested in isolation.

The parser follows CommonMark where it matters for finding fields:

- lines end at ``\\n``, ``\\r\\n`` or ``\\r`` (CommonMark's line endings,
  not every character ``str.splitlines`` breaks on);
- fenced code blocks pair the CommonMark way (§4.5): an opener is a run
  of three or more backticks or tildes indented at most three spaces,
  and only a run of the *same* character, at least as long, followed by
  nothing but spaces or tabs, closes it; a fence never closed runs to
  the end of the body. So a four-backtick block holding a three-backtick
  line keeps its content, and a ``### foo`` line inside a shell snippet
  never false-matches as a heading;
- a field heading is, outside any fence, a ``### <name>`` line at
  column 0, or the lenient form (up to three spaces of indent, one or
  more spaces or tabs after ``###``, an optional closing run of ``#``)
  when the previous line is blank, is itself a field heading, or there
  is none; level-2 (``## ``) and level-4 (``#### ``) headings are
  content. Lists and block quotes are deliberately not modelled: a
  heading-shaped line in any other position is never a field, and
  :func:`normalise` reports one naming a known field as a decision
  (fail closed) rather than guessing what a renderer makes of it;
- the original body is preserved exactly when no change is needed
  (idempotent rewrite).

:func:`normalise` rewrites a body into the canonical shape every reader
agrees on (LF line endings, ``### Name`` headings, closed fences, no
heading-shaped line inside a fence, no repeated field) and reports what
it changed and what it would not decide on its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field


class FieldNotFoundError(LookupError):
    """Raised when the requested field heading is absent from the body."""


class DuplicateFieldError(FieldNotFoundError):
    """Raised when the requested field heading appears more than once outside fences."""


class AmbiguousFieldError(FieldNotFoundError):
    """Raised when readers would disagree on the body's fields: the strict
    cross-check finds a different field set, or a heading-shaped line naming
    the requested field sits where it may or may not be the field."""


# A CommonMark line: content plus its ending (`\n`, `\r\n` or `\r`), or a last unterminated line.
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z")
# A fence line: up to three spaces, a run of 3+ backticks or tildes, the rest (info string or nothing).
_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
# A level-3 ATX heading: up to three spaces, `###`, then whitespace and content, or nothing at all.
_H3 = re.compile(r"^ {0,3}###(?:[ \t]+(.*?))?[ \t]*$")
# An optional closing sequence: a run of `#` preceded by whitespace (or standing alone).
_CLOSING = re.compile(r"(?:^|[ \t]+)#+$")
# Any heading-shaped line (any level, any indent), escaped when it sits inside a fence.
_ANY_HEADING = re.compile(r"^([ \t]*)(?=#{1,6}(?:[ \t]|$))")
# The strict field heading: `### ` at column 0 and a name.
_STRICT_H3 = re.compile(r"^### \S")
# One list marker at the start of a (whitespace-stripped) line: a bullet or an ordered marker, then space/tab.
_LIST_MARKER = re.compile(r"(?:[-*+]|\d{1,9}[.)])[ \t]")
# How many block-quote / list markers `_nested_heading_name` strips before giving up.
_MAX_MARKERS = 64


def split_lines(body: str) -> list[str]:
    """``body`` split into lines with their endings kept, at CommonMark line endings only."""
    return _LINE.findall(body)


def _content(line: str) -> str:
    """``line`` without its line ending."""
    return line.rstrip("\r\n")


def _opens_fence(match: re.Match[str] | None) -> bool:
    return match is not None and not (match.group(2)[0] == "`" and "`" in match.group(3))


def fence_roles(lines: Iterable[str]) -> list[str]:
    """Each line's role: ``"open"``, ``"close"``, ``"code"`` (inside a fence) or ``"text"``.

    Fences pair the CommonMark way: the closer uses the opener's character,
    is at least as long, and carries nothing but spaces or tabs after the
    run. A backtick opener whose info string holds a backtick is not a
    fence. An unclosed fence runs to the end of ``lines``.
    """
    roles: list[str] = []
    opened: tuple[str, int] | None = None
    for raw in lines:
        match = _FENCE.match(_content(raw))
        if opened is None:
            if _opens_fence(match):
                assert match is not None
                opened = (match.group(2)[0], len(match.group(2)))
                roles.append("open")
            else:
                roles.append("text")
            continue
        if (
            match
            and match.group(2)[0] == opened[0]
            and len(match.group(2)) >= opened[1]
            and not match.group(3).strip(" \t")
        ):
            opened = None
            roles.append("close")
        else:
            roles.append("code")
    return roles


def heading_name(line: str) -> str | None:
    """The field name of a level-3 ATX heading line, or None when ``line`` is not one.

    Surrounding spaces and tabs and a closing run of ``#`` are dropped;
    a bare ``###`` is a heading with an empty name.
    """
    match = _H3.match(_content(line))
    if match is None:
        return None
    text = (match.group(1) or "").strip(" \t")
    return _CLOSING.sub("", text).strip(" \t")


def field_names(lines: list[str], roles: list[str] | None = None) -> list[str | None]:
    """Per line, the field name it opens, or None.

    Outside fences, a ``### <name>`` line at column 0 always opens a field.
    A lenient level-3 heading at column 0 (extra spaces or tabs after
    ``###``, a closing run of ``#``) does when the previous line is blank,
    is a field heading, or there is none; an indented one only right after
    a field heading or as the first line, since after a blank line an
    indent can place it inside a list item. Every other heading-shaped line
    is content.
    """
    roles = roles if roles is not None else fence_roles(lines)
    names: list[str | None] = []
    after_heading = True  # the start of the body counts as "after a heading"
    after_blank = True
    for line, role in zip(lines, roles, strict=True):
        content = _content(line)
        name: str | None = None
        if role == "text":
            indented = content[:1] in (" ", "\t")
            if _STRICT_H3.match(content) or after_heading or (after_blank and not indented):
                name = heading_name(content)
        names.append(name)
        after_heading = name is not None
        after_blank = not content.strip(" \t")
    return names


def _nested_heading_name(line: str) -> str | None:
    """The name of a level-3 heading behind block-quote / list markers or indent, else None.

    Strips leading whitespace, then one marker at a time (``>``, a bullet or
    an ordered marker followed by a space or tab) with the whitespace after
    it, at most ``_MAX_MARKERS`` times; linear in the line length.
    """
    rest = _content(line)
    if "###" not in rest:
        return None
    rest = rest.lstrip(" \t")
    for _ in range(_MAX_MARKERS):
        if rest.startswith(">"):
            rest = rest[1:].lstrip(" \t")
            continue
        marker = _LIST_MARKER.match(rest)
        if marker is None:
            break
        rest = rest[marker.end() :].lstrip(" \t")
    if not rest.startswith("###") or rest[3:4] not in ("", " ", "\t"):
        return None
    text = rest[3:].strip(" \t")
    return _CLOSING.sub("", text).strip(" \t")


@dataclass(frozen=True)
class _Section:
    """One ``### <Name>`` heading + the lines that follow it."""

    name: str
    heading_line: str  # the original "### Name" line as it appeared
    body_lines: list[str]  # everything between this heading and the next
    line_no: int = 0  # 1-based line number of the heading


def _parse(body: str) -> tuple[list[str], list[_Section]]:
    """Split ``body`` into a preamble (anything before the first
    ``### `` heading) and a list of ``_Section`` records.

    The preamble is returned as a list of raw lines so the round-trip
    is byte-exact when no field is replaced.
    """
    lines = split_lines(body)
    preamble: list[str] = []
    sections: list[_Section] = []
    current: _Section | None = None

    for number, (line, name) in enumerate(zip(lines, field_names(lines), strict=True), 1):
        if name is not None:
            if current is not None:
                sections.append(current)
            current = _Section(name=name, heading_line=line, body_lines=[], line_no=number)
            continue
        (current.body_lines if current is not None else preamble).append(line)

    if current is not None:
        sections.append(current)
    return preamble, sections


def list_fields(body: str) -> list[str]:
    """Return the field names declared by the body, in document order.

    Duplicate field names are returned as many times as they appear so
    the caller can flag an ambiguous body (the rewrite refuses to
    touch duplicates — see :func:`replace_field`).
    """
    _, sections = _parse(body)
    return [s.name for s in sections]


def _fold(name: str) -> str:
    return " ".join(name.split()).casefold()


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


def _canonical_lines(
    lines: list[str],
    canonical: Mapping[str, str],
    changes: list[dict[str, object]],
    disputed: dict[str, list[int]],
    plain: list[str],
) -> list[str]:
    """Headings canonicalised, headings inside fences escaped, an unclosed fence closed.

    A heading-shaped line outside fences that is not a field heading (behind
    a block-quote or list marker, indented, or not after a blank line) but
    names a known field goes to ``disputed``: whether it is the field depends
    on how a renderer nests it, so it is a decision, not a guess.
    """
    out = list(lines)
    open_index: int | None = None
    roles = fence_roles(out)
    names = field_names(out, roles)
    for index, (line, role) in enumerate(zip(out, roles, strict=True)):
        content = _content(line)
        ending = line[len(content) :]
        if role == "open":
            open_index = index
        elif role == "close":
            open_index = None
        elif role == "code":
            escaped = _ANY_HEADING.sub(lambda m: m.group(1) + "\\", content, count=1)
            if escaped != content:
                out[index] = escaped + ending
                changes.append({"line": index + 1, "kind": "heading_in_fence"})
        elif role == "text":
            name = names[index]
            if name is None:
                nested = _nested_heading_name(content)
                if nested and _fold(nested) in canonical:
                    disputed.setdefault(canonical[_fold(nested)], []).append(index + 1)
                continue
            if not name:
                continue
            spelled = canonical.get(_fold(name), name)
            wanted = f"### {spelled}"
            if wanted != content:
                out[index] = wanted + ending
                changes.append({"line": index + 1, "kind": "heading" if spelled == name else "heading_name"})
    # The strict cross-check reads the headings as canonicalised but the fences
    # unescaped and unclosed, so it still sees what a column-0 reader would.
    plain.extend(out)
    for index, role in enumerate(roles):
        if role == "code":
            plain[index] = lines[index]
    if open_index is not None:
        opener = _FENCE.match(_content(out[open_index]))
        assert opener is not None  # an "open" role always matched
        if not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append(opener.group(2) + "\n")
        changes.append({"line": open_index + 1, "kind": "unclosed_fence"})
    return out


def _strict_fields(text: str) -> list[tuple[int, str]]:
    """``(line, name)`` of every field a strict reader finds in ``text``.

    A second, deliberately simpler reading used to cross-check the lenient
    parser on a normalised body: a field is a ``### <name>`` line at column
    0 outside a fence, and a fence opens only at column 0. Where the two
    readings disagree, a reader of the body could disagree too.
    """
    found: list[tuple[int, str]] = []
    opened: tuple[str, int] | None = None
    for number, raw in enumerate(split_lines(text), 1):
        line = _content(raw)
        match = _FENCE.match(line)
        if opened is not None:
            if (
                match
                and match.group(2)[0] == opened[0]
                and len(match.group(2)) >= opened[1]
                and not match.group(3).strip(" \t")
            ):
                opened = None
            continue
        if match and not match.group(1) and _opens_fence(match):
            opened = (match.group(2)[0], len(match.group(2)))
        elif _STRICT_H3.match(line):
            found.append((number, heading_name(line) or ""))
    return found


def normalise(
    body: str,
    known_fields: Iterable[str] | None = None,
    keep: Mapping[str, int] | None = None,
) -> NormaliseResult:
    """``body`` in the canonical shape every field reader agrees on.

    - ``\\r\\n`` and a lone ``\\r`` become ``\\n`` (kind ``line_endings``,
      recorded once, at the first such line);
    - a level-3 heading outside a fence becomes ``### Name`` (kind
      ``heading``); with ``known_fields``, a name equal to a known field
      once case-folded and whitespace-collapsed takes the known spelling
      (kind ``heading_name``);
    - a heading-shaped line inside a fence gets a ``\\`` before its first
      ``#``, so no reader takes it for a field (kind ``heading_in_fence``);
    - a fence still open at the end of the body is closed (kind
      ``unclosed_fence``, at the opener's line);
    - a field heading repeated outside fences: when every copy holds the
      same value (after stripping), the later copies are dropped (kind
      ``duplicate_dropped``, at each dropped heading); otherwise every copy
      stays and ``{"field", "kind": "duplicate", "lines"}`` goes to
      ``needs_decision`` — unless ``keep`` maps the field to the heading
      line of the copy to keep (a decision made elsewhere), which is then
      kept and the others dropped (kind ``duplicate_resolved``);
    - a heading-shaped line that is not a field heading (behind ``>`` or a
      list marker, indented, or not after a blank line) is never rewritten;
      when its name is a known field, and wherever the strict cross-check
      (:func:`_strict_fields`) and this parser disagree about a field
      heading, ``{"field", "kind": "container-heading", "lines"}`` goes to
      ``needs_decision`` instead of any reading winning.

    Line numbers are the input body's. Normalising a normalised body
    changes nothing.
    """
    changes: list[dict[str, object]] = []
    canonical = {_fold(name): name for name in (known_fields or [])}

    lines: list[str] = []
    first_cr: int | None = None
    for number, raw in enumerate(split_lines(body), 1):
        content = _content(raw)
        if raw[len(content) :] not in ("", "\n"):
            first_cr = first_cr or number
            raw = content + "\n"
        lines.append(raw)
    if first_cr is not None:
        changes.append({"line": first_cr, "kind": "line_endings"})

    disputed: dict[str, list[int]] = {}
    plain: list[str] = []
    text = "".join(_canonical_lines(lines, canonical, changes, disputed, plain)) if lines else ""

    preamble, sections = _parse(text)
    lenient = {(s.line_no, s.name) for s in sections if s.name}
    for line_no, name in sorted(lenient ^ {f for f in _strict_fields("".join(plain)) if f[1]}):
        disputed.setdefault(name, []).append(line_no)
    needs_decision: list[dict[str, object]] = [
        {"field": name, "kind": "container-heading", "lines": sorted(set(line_nos))}
        for name, line_nos in disputed.items()
    ]
    copies_of: dict[str, list[_Section]] = {}
    for section in sections:
        if section.name:
            copies_of.setdefault(section.name, []).append(section)
    drop: set[int] = set()
    for name, copies in copies_of.items():
        if len(copies) < 2:
            continue
        line_nos = [s.line_no for s in copies]
        if len({"".join(s.body_lines).strip() for s in copies}) == 1:
            dropped = line_nos[1:]
            kind = "duplicate_dropped"
        elif keep is not None and keep.get(name) in line_nos:
            dropped = [n for n in line_nos if n != keep[name]]
            kind = "duplicate_resolved"
        else:
            needs_decision.append({"field": name, "kind": "duplicate", "lines": line_nos})
            continue
        drop.update(dropped)
        changes.extend({"line": n, "kind": kind} for n in dropped)
    if drop:
        rebuilt = list(preamble)
        for section in sections:
            if section.line_no not in drop:
                rebuilt.append(section.heading_line)
                rebuilt.extend(section.body_lines)
        trailing_blank = text.endswith("\n\n")
        text = "".join(rebuilt)
        if not trailing_blank and text.endswith("\n\n"):
            # The dropped copy was last: its predecessor's spacer is now the body's end.
            text = text.rstrip("\n") + "\n"
    changes.sort(key=lambda c: (int(str(c["line"])), str(c["kind"])))
    return NormaliseResult(text=text, changes=changes, needs_decision=needs_decision)


def _strip_spacer_blanks(body_lines: list[str]) -> tuple[bool, list[str], bool]:
    """Strip up to one leading and one trailing blank-line spacer.

    Returns ``(had_leading, stripped_lines, had_trailing)`` so the
    caller can later re-emit with the same convention.
    """
    lines = list(body_lines)
    had_leading = bool(lines) and lines[0] == "\n"
    if had_leading:
        lines = lines[1:]
    had_trailing = bool(lines) and lines[-1] == "\n" and len(lines) > 1
    # The `len(lines) > 1` guard is so a field whose *only* line
    # is a blank one (i.e. an empty value with one spacer) doesn't
    # get the same line both stripped and counted as "trailing".
    if had_trailing:
        lines = lines[:-1]
    return had_leading, lines, had_trailing


def _refuse_ambiguous(body: str, field_name: str) -> None:
    """Raise :class:`AmbiguousFieldError` when readers could disagree on ``field_name``.

    Run by every read and write, so no caller can skip it: the strict
    cross-check must find the same field set, and no heading-shaped line
    naming ``field_name`` may sit where it may or may not be the field.
    """
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


def _matching(sections: list[_Section], field_name: str) -> list[int]:
    indices = [i for i, s in enumerate(sections) if s.name == field_name]
    if not indices:
        raise FieldNotFoundError(f"field not found: {field_name!r}")
    if len(indices) > 1:
        raise DuplicateFieldError(f"field {field_name!r} appears {len(indices)} times; refusing to guess")
    return indices


def extract_field(body: str, field: str) -> str:
    """Return the raw text value of ``### <field>``.

    The blank-line spacer that conventionally separates the heading
    from the value, and the value from the next heading, is stripped
    so callers get the value as a user would copy-paste it. Internal
    blank lines are preserved.

    Raises :class:`FieldNotFoundError` if the heading does not exist,
    :class:`DuplicateFieldError` (a subclass) if it appears more than once,
    :class:`AmbiguousFieldError` (a subclass) if readers could disagree on it.
    """
    _refuse_ambiguous(body, field)
    _, sections = _parse(body)
    index = _matching(sections, field)[0]
    _, stripped, _ = _strip_spacer_blanks(sections[index].body_lines)
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
    value they pass.

    Raises :class:`FieldNotFoundError` if the heading does not exist,
    :class:`DuplicateFieldError` (a subclass) if it appears more than once,
    :class:`AmbiguousFieldError` (a subclass) if readers could disagree on it.
    """
    _refuse_ambiguous(body, field)
    preamble, sections = _parse(body)
    target_idx = _matching(sections, field)[0]
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
    normalised = new_value
    while normalised.endswith("\n\n"):
        normalised = normalised[:-1]
    if normalised and not normalised.endswith("\n"):
        normalised += "\n"

    rebuilt_body_lines: list[str] = []
    if normalised:
        if had_leading:
            rebuilt_body_lines.append("\n")
        rebuilt_body_lines.extend(normalised.splitlines(keepends=True))
        if had_trailing and not is_last_section:
            rebuilt_body_lines.append("\n")
    else:
        # Empty value: collapse to a single blank-line spacer so the
        # next heading isn't glued to the current one. Don't stack
        # both leading and trailing spacers (that would render as
        # two blank lines, which reads worse than one in the tracker
        # UI). For the last section, emit nothing — the bare heading
        # line is sufficient.
        if not is_last_section and (had_leading or had_trailing):
            rebuilt_body_lines.append("\n")

    out: list[str] = list(preamble)
    for index, s in enumerate(sections):
        out.append(s.heading_line)
        out.extend(rebuilt_body_lines if index == target_idx else s.body_lines)
    return "".join(out)
