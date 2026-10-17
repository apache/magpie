# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""Body-field sections and the status rollup, in Jira wiki markup.

Body fields follow the body-field contract (tools/body-field-contract/contract.md)
through :mod:`jira_bridge.body_field_format`, a byte-identical copy of
tools/github-body-field's parser (tests/test_vendored_parser.py keeps it
exact): every column-0 ``### <Heading>`` line ends a field, code block or
not, and a heading inside a closed code block never starts a field.

Jira's own heading syntax is mapped onto that contract before the parser
reads the body (:func:`as_fields`): a wiki heading of level 1 to 3
(``h3. <Heading>``, indented or not) outside every closed code block reads
as ``### <Heading>``. Closed blocks are the parser's: CommonMark fence pairs
and ``{code}`` / ``{code:…}`` / ``{noformat}`` blocks opened at the start of
a line and closed on the bare macro; a block left open marks nothing, so no
macro left in one field can hide the headings after it. Wiki ``h4.`` to
``h6.`` headings and Markdown ``#`` / ``##`` lines are field content.
Field names match with case and inner whitespace ignored.

The rollup is one comment whose first line is the invisible anchor macro
:data:`ROLLUP_MARKER`; each entry is a bold summary line
``*YYYY-MM-DD · @user · <Action>*``, a blank line, the entry body, and
entries are separated by a ``----`` line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import body_field_format as fields
from .body_field_format import (
    AmbiguousFieldError,
    DuplicateFieldError,
    FieldNotFoundError,
)

__all__ = [
    "ROLLUP_MARKER",
    "AmbiguousFieldError",
    "DuplicateFieldError",
    "FieldNotFoundError",
    "Heading",
    "RollupEntry",
    "as_fields",
    "escape_quoted_fields",
    "find_headings",
    "get_field",
    "is_rollup",
    "list_fields",
    "neutralize",
    "parse_rollup",
    "render_rollup",
    "set_field",
    "to_markdown_headings",
]

ROLLUP_MARKER = "{anchor:magpie-status-rollup-v1}"

_MARKER_RE = re.compile(r"^\{anchor:magpie-status-rollup-v\d+\}\s*$")
_SUMMARY_RE = re.compile(r"^\*(\d{4}-\d{2}-\d{2}) · @(.+?) · (.+)\*\s*$")
_WIKI_HEADING_RE = re.compile(r"^\s*h([1-6])\.\s+(.*?)\s*$")
_MD_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")


@dataclass(frozen=True)
class Heading:
    """A heading line found in a body."""

    index: int
    level: int
    text: str
    wiki: bool


def _content(line: str) -> str:
    return line.rstrip("\r\n")


def find_headings(lines: list[str]) -> list[Heading]:
    """Every heading outside closed code blocks (the parser's blocks), in document order."""
    inside = fields.closed_block_lines(lines)
    headings: list[Heading] = []
    for index, line in enumerate(lines):
        if inside[index]:
            continue
        wiki = _WIKI_HEADING_RE.match(_content(line))
        if wiki:
            headings.append(Heading(index, int(wiki.group(1)), wiki.group(2), True))
            continue
        md = _MD_HEADING_RE.match(_content(line))
        if md:
            headings.append(Heading(index, len(md.group(1)), md.group(2), False))
    return headings


def _project(lines: list[str]) -> list[str]:
    """``lines`` with each wiki heading of level 1 to 3 outside closed blocks as ``### <text>``."""
    inside = fields.closed_block_lines(lines)
    out = list(lines)
    for index, line in enumerate(lines):
        content = _content(line)
        wiki = None if inside[index] else _WIKI_HEADING_RE.match(content)
        if wiki and int(wiki.group(1)) <= 3:
            out[index] = f"### {wiki.group(2)}" + line[len(content) :]
    return out


def as_fields(body: str) -> str:
    """``body`` as the body-field parser reads it: its wiki field headings spelled ``### <text>``."""
    return "".join(_project(fields.split_lines(body)))


def _field_name(body: str, heading: str) -> str | None:
    """The exact name of the field ``heading`` names, matched with case and inner whitespace ignored.

    The parser's rule over every spelling of the name: the copy outside
    closed blocks (a heading inside one never starts a field). The parser's
    refusal of an ambiguous field comes first, for every spelling; then two
    copies outside closed blocks, however spelled, are a duplicate.
    """
    wanted = fields.fold_name(heading)
    outside = [
        s
        for s in fields.parse(body)[1]
        if not s.in_block and fields.fold_name(s.name) == wanted
    ]
    for name in dict.fromkeys([heading, *(s.name for s in outside)]):
        try:
            fields.extract_field(body, name)
        except fields.AmbiguousFieldError:
            raise
        except fields.FieldNotFoundError:
            # This loop only probes each spelling for the ambiguity refusal above;
            # a spelling that is absent is fine, and the duplicate check follows.
            pass
    if len(outside) > 1:
        raise fields.DuplicateFieldError(
            f"field {heading!r} appears {len(outside)} times; refusing to guess"
        )
    return outside[0].name if outside else None


def escape_quoted_fields(body: str) -> str:
    """``body`` with a leading backslash on every ``###`` field boundary inside a closed code block.

    A heading inside a closed block is never a field; escaped at ingest
    (create, edit), quoted text cannot become a copy of a field at all, as
    in the import's inert block.
    """
    lines = fields.split_lines(body)
    inside = fields.closed_block_lines(lines)
    return "".join(
        "\\" + line if inside[index] and fields.is_boundary(line) else line
        for index, line in enumerate(lines)
    )


def list_fields(body: str) -> list[str]:
    """The field names the body declares (headings outside closed blocks), in document order."""
    return fields.list_fields(as_fields(body))


def get_field(body: str, heading: str) -> str | None:
    """The stripped value of the ``heading`` field, or None when the body has no such field.

    Raises :class:`DuplicateFieldError` or :class:`AmbiguousFieldError` (the
    parser's) when the body does not say which section is the field.
    """
    projected = as_fields(body)
    name = _field_name(projected, heading)
    if name is None:
        return None
    return fields.extract_field(projected, name).strip()


def _refuse(heading: str, action: str) -> AmbiguousFieldError:
    return AmbiguousFieldError(
        f"field {heading!r}: the new value holds a heading or a code block that would change "
        f"the body's other fields; refusing to {action} it"
    )


def set_field(body: str, heading: str, value: str) -> tuple[str, bool]:
    """Replace (or append) the ``heading`` field; return ``(new_body, created)``.

    A replacement is the parser's ``replace_field`` on :func:`as_fields`,
    mapped back onto the wiki body, so everything outside the field stays
    byte-identical. A value that would add, hide or move a field heading (a
    ``###`` or wiki heading line, a code block reaching past the field) is
    refused with :class:`AmbiguousFieldError`, as are the parser's own
    refusals (a duplicate or disputed field).
    """
    lines = fields.split_lines(body)
    projected = _project(lines)
    before = "".join(projected)
    sections = fields.parse(before)[1]
    name = _field_name(before, heading)
    if name is not None:
        rewritten = fields.split_lines(fields.replace_field(before, name, value))
        limit = min(len(projected), len(rewritten))
        head = 0
        while head < limit and rewritten[head] == projected[head]:
            head += 1
        tail = 0
        while tail < limit - head and rewritten[-1 - tail] == projected[-1 - tail]:
            tail += 1
        middle = rewritten[head : len(rewritten) - tail]
        new_body = "".join([*lines[:head], *middle, *lines[len(lines) - tail :]])
        if as_fields(new_body) != "".join(rewritten):
            raise _refuse(heading, "rewrite")
        return new_body, False
    headings = find_headings(lines)
    markdown_only = bool(headings) and not any(h.wiki for h in headings)
    heading_line = f"### {heading}" if markdown_only else f"h3. {heading}"
    prefix = body.rstrip()
    section = (
        "\n".join(
            [
                heading_line,
                *(_content(line) for line in fields.split_lines(value.strip("\n"))),
            ]
        )
        + "\n"
    )
    new_body = f"{prefix}\n\n{section}" if prefix else section
    after = fields.parse(as_fields(new_body))[1]
    if [(s.name, s.in_block) for s in after[:-1]] != [
        (s.name, s.in_block) for s in sections
    ] or (get_field(new_body, heading) != value.strip()):
        raise _refuse(heading, "add")
    return new_body, True


@dataclass
class RollupEntry:
    """One rollup entry."""

    date: str
    user: str
    action: str
    body: str


_ANCHOR_RE = re.compile(r"\{(?=anchor:magpie-status-rollup)", re.IGNORECASE)


def neutralize(text: str) -> str:
    """Make untrusted comment or rollup text unable to forge rollup structure.

    The text usually comes from outside the team. Written verbatim, a body that
    opens with the rollup anchor would be taken for the rollup comment, and a
    line shaped like ``*YYYY-MM-DD · @user · Action*`` would read back as a
    rollup entry by someone else — misleading `rollup-amend-latest` too. Both
    are escaped with a wiki-markup backslash, which renders the same visible
    text and is never parsed as structure.
    """
    text = _ANCHOR_RE.sub("\\{", text)
    # Split exactly as parse_rollup does (str.splitlines: \r, \u2028, \x85 …),
    # so no line boundary the parser honours can hide a forged summary line.
    out = []
    for part in text.splitlines(keepends=True):
        line = part.splitlines()[0] if part.splitlines() else ""
        out.append("\\" + part if _SUMMARY_RE.match(line) else part)
    return "".join(out)


def to_markdown_headings(text: str) -> str:
    """The description with markdown headings: :func:`as_fields`, and ``h4.``-``h6.`` as ``####``-``######``.

    The field headings are exactly the ones :func:`get_field` reads, so
    generate-cve-json reading this output sees the same fields, and
    heading-like text inside a closed ``{code}`` / ``{noformat}`` PoC never
    becomes a field it could read a CVE ID from. Lines end in ``\\n``.
    """
    lines = [_content(line) for line in _project(fields.split_lines(text))]
    inside = fields.closed_block_lines(lines)
    for index, line in enumerate(lines):
        wiki = None if inside[index] else _WIKI_HEADING_RE.match(line)
        if wiki:
            lines[index] = "#" * int(wiki.group(1)) + " " + wiki.group(2)
    return "\n".join(lines)


def is_rollup(text: str) -> bool:
    """True when ``text`` is a rollup comment (first non-empty line is the marker)."""
    for line in text.splitlines():
        if line.strip():
            return bool(_MARKER_RE.match(line.strip()))
    return False


def parse_rollup(text: str) -> list[RollupEntry]:
    """Parse a rollup comment into its entries, oldest first."""
    entries: list[RollupEntry] = []
    body_lines: list[list[str]] = []
    seen_marker = False
    for line in text.splitlines():
        if not seen_marker:
            if _MARKER_RE.match(line.strip()):
                seen_marker = True
            continue
        match = _SUMMARY_RE.match(line)
        if match:
            entries.append(
                RollupEntry(match.group(1), match.group(2), match.group(3), "")
            )
            body_lines.append([])
        elif entries:
            body_lines[-1].append(line)
    for entry, lines in zip(entries, body_lines, strict=True):
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip() == "----":
            lines.pop()
        entry.body = "\n".join(lines).strip("\n")
    return entries


def render_rollup(entries: list[RollupEntry]) -> str:
    """Render rollup entries into the comment body."""
    blocks = [
        f"*{e.date} · @{e.user} · {e.action}*\n\n{e.body.strip(chr(10))}"
        for e in entries
    ]
    return ROLLUP_MARKER + "\n" + "\n\n----\n\n".join(blocks) + "\n"
