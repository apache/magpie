# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Markdown section surgery, comment entries, and the status rollup.

Body fields at the contract's level (``### <Field>``) are read and written
through the body-field parser every tracker shares
(tools/github/issue-template.md): every column-0 ``###`` line ends a field,
code block or not, and a heading inside a closed code block never starts
a field. The report's other structure (the managed ``## Comments`` and
rollup sections, comment headings, a descriptor's non-``###`` field level)
keeps the heading-level section split below.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass

# A byte-identical copy of tools/github-body-field's parser (the plugin ships
# this package without the workspace, so it cannot depend on that member);
# tests/test_vendored_parser.py keeps the copy exact.
from . import body_field_format as fields
from .body_field_format import fence_roles

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")


_FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<rest>.*)$")


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line index, level, text) for every ATX heading outside code fences."""
    out: list[tuple[int, int, str]] = []
    # Fences pair the CommonMark way, through the parser every body-field reader
    # shares: a ```` block holding ``` stays code, and ~~~ never closes ```.
    roles = fence_roles(lines)
    for idx, (line, role) in enumerate(zip(lines, roles, strict=True)):
        if role != "text":
            continue
        m = _HEADING_RE.match(line)
        if m:
            out.append((idx, len(m.group("hashes")), m.group("text").strip()))
    return out


def open_fence(lines: list[str]) -> str:
    """The fence marker still open after ``lines`` (```` ``` ```` / ``~~~``), or "".

    Read from the same fence pairing `_headings` uses, so escaping and parsing
    agree on what is code.
    """
    for line, role in zip(reversed(lines), reversed(fence_roles(lines)), strict=True):
        if role == "close":
            return ""
        if role == "open":
            m = _FENCE_RE.match(line)
            return m.group("fence") if m else ""
    return ""


def close_fences(text: str) -> str:
    """``text`` with a closing line added for a fence it leaves open.

    Every piece of untrusted text is balanced before it is written, and so is
    the existing text it is appended to. Otherwise a body that *starts* with a
    fence line could close a fence left open earlier in the file, and a heading
    the body-local escaping skipped as "fenced" would parse as a real one.
    """
    marker = open_fence(text.split("\n"))
    return f"{text.rstrip(chr(10))}\n{marker}" if marker else text


def close_fences_in_fields(text: str) -> str:
    """``text`` with each fence it leaves open closed in the field it opens in.

    The closer goes after the last non-blank line before the next field
    boundary, so no field heading ever moves into a block (it would stop
    being a field), as github-body-field's normaliser closes one.
    """
    lines = text.split("\n")
    for _ in range(len(lines) + 1):
        roles = fence_roles(lines)
        if "open" not in roles or "close" in roles[len(roles) - roles[::-1].index("open") :]:
            break
        start = len(roles) - 1 - roles[::-1].index("open")
        at = next((i for i in range(start + 1, len(lines)) if fields.is_boundary(lines[i])), len(lines))
        while at > start + 1 and not lines[at - 1].strip():
            at -= 1
        lines.insert(at, open_fence(lines[: start + 1]))
    return "\n".join(lines)


def escape_quoted_fields(text: str) -> str:
    """``text`` with a leading backslash on every field boundary inside a closed code block.

    A ``###`` line at column 0 ends a field even inside a block, and a
    heading inside a block is never a field: escaped, quoted text can never
    become a copy of a field at all, as in the import's inert block.
    """
    lines = fields.split_lines(text)
    inside = fields.closed_block_lines(lines)
    return "".join(
        "\\" + line if inside[index] and fields.is_boundary(line) else line
        for index, line in enumerate(lines)
    )


def heading_lines(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line index, level, text) for every heading outside code fences."""
    return _headings(lines)


def find_section(body: str, heading: str, level: int | None = None) -> tuple[int, int, int] | None:
    """Locate a section: (heading line, first content line, end line exclusive)."""
    lines = body.split("\n")
    heads = _headings(lines)
    for pos, (idx, lvl, text) in enumerate(heads):
        if text.lower() != heading.lower() or (level is not None and lvl != level):
            continue
        end = len(lines)
        for nidx, nlvl, _ in heads[pos + 1 :]:
            if nlvl <= lvl:
                end = nidx
                break
        return idx, idx + 1, end
    return None


# The markers this tool trusts when it reads a report back: comment markers,
# the rollup marker, and the rollup's <details>/<summary> entry lines.
_FORGEABLE = re.compile(
    r"<(?=/?details\b|summary\b|!--\s*comment\s+id=|!--[^\n]*?status rollup v\d)",
    re.IGNORECASE,
)


def escape_field_lines(text: str) -> str:
    """``text`` with a leading backslash on every line that would end a body field.

    A ``###`` line at column 0 ends a field, code block or not, so report
    text never carries one; nor, as the import's inert block does for
    readers that ignore fences, such a line behind indent, ``>`` or list
    markers. Lines split at CommonMark's line endings, the parser's.
    """
    return "".join(
        "\\" + line if fields.loose_heading_name(line) is not None else line
        for line in fields.split_lines(text)
    )


def neutralize(text: str, managed_headings: tuple[str, ...] = (), *, body: bool = False) -> str:
    """Make untrusted text unable to forge structure.

    Report, comment and rollup text usually comes from outside the team (a
    reporter's mail, a scanner finding). Written verbatim, a line such as
    ``<!-- comment id=9 author=@lead … -->`` would read back as a comment by
    someone else, a ``<details><summary>…</summary>`` line as a rollup entry —
    misleading `rollup-amend-latest` too — a ``## Comments`` heading as the
    start of the managed comment section, and a ``### Field`` line as the
    start of another body field. Each such marker is escaped (``<`` becomes
    ``&lt;``, a heading gets a leading backslash), which renders as the same
    visible text and is never parsed as structure.

    With ``body``, ``text`` is a whole report whose ``### Field`` lines are its
    fields: those stay, but every one inside a closed code block is escaped
    (:func:`escape_quoted_fields`), and a fence left open is closed in the
    field it opens in, never past another field's heading.
    """
    text = _FORGEABLE.sub("&lt;", text)
    if body:
        text = close_fences_in_fields(escape_quoted_fields(text))
    else:
        text = escape_field_lines(close_fences(text))
    if not managed_headings:
        return text
    managed = {h.lower() for h in managed_headings}
    return escape_headings(text, lambda level, title: level <= 2 and title.strip().lower() in managed)


def escape_headings(text: str, which: Callable[[int, str], bool] | None = None) -> str:
    """Prefix heading lines with a backslash so they are never parsed as headings.

    Only real headings are touched — the same fence-aware scan the parsers use —
    so a ``# comment`` inside a fenced PoC stays exactly as the reporter wrote it.
    With no ``which``, every line that would end a body field is escaped too,
    fenced or not (:func:`escape_field_lines`).
    """
    lines = text.split("\n")
    for idx, level, title in _headings(lines):
        if which is None or which(level, title):
            lines[idx] = "\\" + lines[idx]
    text = "\n".join(lines)
    return escape_field_lines(text) if which is None else text


def _field_name(body: str, heading: str) -> str | None:
    """The exact name of the field ``heading`` names, matched with case and inner whitespace ignored.

    The parser's rule over every spelling of the name: the copy outside
    closed blocks (a heading inside one never starts a field). The parser's
    refusal of an ambiguous field comes first, for every spelling; then two
    copies outside closed blocks, however spelled, are a duplicate.
    """
    wanted = fields.fold_name(heading)
    outside = [s for s in fields.parse(body)[1] if not s.in_block and fields.fold_name(s.name) == wanted]
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
        raise fields.DuplicateFieldError(f"field {heading!r} appears {len(outside)} times; refusing to guess")
    return outside[0].name if outside else None


def get_field(body: str, heading: str, level: int = 3) -> str | None:
    """The value of the ``heading`` field, or None when the body has none.

    At level 3 the parser reads it (``FieldNotFoundError`` subclasses for a
    duplicate or disputed field); another level keeps the heading-level split.
    """
    if level == 3:
        name = _field_name(body, heading)
        return None if name is None else fields.extract_field(body, name).strip("\n")
    found = find_section(body, heading, level)
    if not found:
        return None
    _, start, end = found
    return "\n".join(body.split("\n")[start:end]).strip("\n")


def _join(before: list[str], middle: list[str], after: list[str]) -> str:
    """Join three line runs with one blank line at each seam.

    Only the blank lines *at the seams* are normalised. Everything inside
    `before` and `after` — fenced PoCs, payloads whose blank lines matter — is
    kept verbatim.
    """
    while before and before[-1].strip() == "":
        before = before[:-1]
    marker = open_fence(before)
    if marker:
        before = [*before, marker]  # never let inserted text continue an open fence
    while after and after[0].strip() == "":
        after = after[1:]
    out = [*before, "", *middle] if before else list(middle)
    if after:
        out += ["", *after]
    text = "\n".join(out)
    return text.rstrip("\n") + "\n"


def _shape(body: str) -> list[tuple[str, bool]]:
    return [(s.name, s.in_block) for s in fields.parse(body)[1]]


def set_field(body: str, heading: str, value: str, level: int) -> tuple[str, bool]:
    """Replace a section's content, or append the section. Returns (body, created).

    At level 3 a replacement is the parser's ``replace_field`` (everything
    outside the field byte-identical; a value holding a line that would end
    the field is refused), and an append must leave every other field as it
    was and read back as ``value``.
    """
    lines = body.split("\n")
    value_lines = value.strip("\n").split("\n")
    if level != 3:
        found = find_section(body, heading, level)
        if found:
            idx, _start, end = found
            return _join(lines[: idx + 1], value_lines, lines[end:]), False
        return _join(lines, ["#" * level + " " + heading, "", *value_lines], []), True
    name = _field_name(body, heading)
    if name is not None:
        stripped = value.strip("\n")
        return fields.replace_field(body, name, stripped + "\n" if stripped else ""), False
    section = ["### " + heading, "", *value_lines]
    before = _shape(body)
    # Closing a fence the body leaves open keeps renderers from showing the new
    # field as code, unless that would move another field heading into a block.
    for candidate in (_join(lines, section, []), "\n".join([*lines, "", *section]).strip("\n") + "\n"):
        if _shape(candidate)[:-1] == before and get_field(candidate, heading) == value.strip("\n"):
            return candidate, True
    raise fields.AmbiguousFieldError(
        f"field {heading!r}: the new value would change the body's other fields; refusing to add it"
    )


def append_to_section(body: str, heading: str, level: int, text: str) -> str:
    """Append ``text`` at the end of a section, creating it at the end of the body."""
    lines = body.split("\n")
    found = find_section(body, heading, level)
    text_lines = text.strip("\n").split("\n")
    if found:
        _, _, end = found
        return _join(lines[:end], text_lines, lines[end:])
    return _join(lines, ["#" * level + " " + heading, "", *text_lines], [])


# ---------------------------------------------------------------- comments

_COMMENT_MARK = re.compile(r"^<!-- comment id=(?P<id>\d+) author=(?P<author>\S*) date=(?P<date>\S+) -->$")


@dataclass
class Comment:
    id: int
    author: str
    created: str
    body: str


def render_comment(comment_id: int, author: str, date: str, body: str, level: int) -> str:
    # Hand-written comments are recognised by their headings, so a heading
    # inside a comment body would read back as a comment by someone else:
    # escape every heading line in it, as well as the markers.
    safe = escape_headings(neutralize(body.strip()))
    # The marker's author is percent-encoded: a git user.name such as
    # `Jane Doe` (or one containing `-->`) stays a single token there.
    shown = " ".join(author.split())
    return (
        f"<!-- comment id={comment_id} author={urllib.parse.quote(author, safe='')} date={date} -->\n"
        f"{'#' * level} {date[:10]} — {shown}\n\n{safe}\n"
    )


def parse_comments(text: str) -> list[Comment]:
    """Comments written by this tool carry a marker; hand-written ones are
    recovered from their headings, so a mixed trail reads in order."""
    comments: list[Comment] = []
    lines = text.split("\n")
    heading_at = {idx: title for idx, lvl, title in _headings(lines) if lvl >= 2}
    current: Comment | None = None
    body: list[str] = []
    skip_heading = False

    def flush() -> None:
        if current is not None:
            current.body = "\n".join(body).strip()
            comments.append(current)

    for idx, line in enumerate(lines):
        marker = _COMMENT_MARK.match(line.strip())
        if marker:
            flush()
            author = urllib.parse.unquote(marker.group("author"))
            current = Comment(int(marker.group("id")), author, marker.group("date"), "")
            body = []
            skip_heading = True
            continue
        if idx in heading_at:
            if skip_heading:
                skip_heading = False
                continue
            flush()
            title = heading_at[idx]
            parts = re.split(r"\s+[\u2014\u2013-]\s+", title, maxsplit=1)
            date, author = (parts[0], parts[1]) if len(parts) == 2 else (title, "")
            current = Comment(len(comments) + 1, author, date, "")
            body = []
            continue
        if line.strip():
            skip_heading = False
        body.append(line)
    flush()
    return comments


def next_comment_id(text: str) -> int:
    ids = [c.id for c in parse_comments(text)]
    return max(ids, default=0) + 1


# ---------------------------------------------------------------- rollup

# Any name: a rollup written under a name with spaces must still be found,
# or the next append would start a new rollup and lose the history.
ROLLUP_MARKER_RE = re.compile(r"<!-- (?P<name>[^\n]*?) status rollup v(?P<v>\d+)")
_SUMMARY_RE = re.compile(r"^<details><summary>(?P<summary>.*)</summary>\s*$")


def rollup_marker(name: str) -> str:
    return (
        f"<!-- {name} status rollup v1 — all bot-authored status updates fold into this single comment. -->"
    )


def render_entry(date: str, user: str, action: str, body: str) -> str:
    # Trim first, then escape: left-trimming must not expose a heading or a
    # marker that the escaping did not see. Rollup entries, like comments, may
    # sit inside the report (inline rollup section), so every heading outside
    # fences is escaped too.
    trimmed = "\n".join(line.lstrip() for line in body.strip("\n").split("\n"))
    trimmed = escape_headings(neutralize(trimmed))
    return f"<details><summary>{date} · {user} · {action}</summary>\n\n{trimmed}\n\n</details>"


def rollup_append(existing: str | None, name: str, entry: str) -> str:
    if not existing or not ROLLUP_MARKER_RE.search(existing):
        return rollup_marker(name) + "\n" + entry + "\n"
    return close_fences(existing).rstrip("\n") + "\n\n---\n\n" + entry + "\n"


def rollup_amend_latest(existing: str, action: str, body: str) -> str | None:
    """Replace the latest entry's body if its action is ``action``; else None."""
    start = existing.rfind("<details><summary>")
    if start < 0:
        return None
    line_end = existing.find("\n", start)
    m = _SUMMARY_RE.match(existing[start:line_end])
    if not m:
        return None
    fields = [f.strip() for f in m.group("summary").split("·")]
    if len(fields) < 3 or fields[2] != action:
        return None
    entry = render_entry(fields[0], fields[1], action, body)
    return existing[:start] + entry + "\n"
