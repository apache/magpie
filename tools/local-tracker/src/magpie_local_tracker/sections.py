# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Markdown section surgery, comment entries, and the status rollup."""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")


_FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<rest>.*)$")


def _fence_step(open_fence: str, line: str) -> tuple[str, bool]:
    """Advance the fence state over one line, the CommonMark way.

    Returns (open fence after the line, whether the line is a fence line). A
    fence opens with three or more backticks or tildes and closes only on a
    line of the same character, at least as long, with nothing after it.
    """
    m = _FENCE_RE.match(line)
    if not m:
        return open_fence, False
    fence, rest = m.group("fence"), m.group("rest")
    if open_fence:
        if fence[0] == open_fence[0] and len(fence) >= len(open_fence) and not rest.strip():
            return "", True
        return open_fence, False
    if fence[0] == "`" and "`" in rest:
        return "", False  # an inline code span, not a fence
    return fence, True


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line index, level, text) for every ATX heading outside code fences."""
    out: list[tuple[int, int, str]] = []
    fence = ""
    for idx, line in enumerate(lines):
        fence, is_fence = _fence_step(fence, line)
        if is_fence or fence:
            continue
        m = _HEADING_RE.match(line)
        if m:
            out.append((idx, len(m.group("hashes")), m.group("text").strip()))
    return out


def open_fence(lines: list[str]) -> str:
    """The fence marker still open after ``lines`` (```` ``` ```` / ``~~~``), or "".

    The same toggling `_headings` uses, so escaping and parsing agree on what is
    code.
    """
    fence = ""
    for line in lines:
        fence, _ = _fence_step(fence, line)
    return fence


def close_fences(text: str) -> str:
    """``text`` with a closing line added for a fence it leaves open.

    Every piece of untrusted text is balanced before it is written, and so is
    the existing text it is appended to. Otherwise a body that *starts* with a
    fence line could close a fence left open earlier in the file, and a heading
    the body-local escaping skipped as "fenced" would parse as a real one.
    """
    marker = open_fence(text.split("\n"))
    return f"{text.rstrip(chr(10))}\n{marker}" if marker else text


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


def neutralize(text: str, managed_headings: tuple[str, ...] = ()) -> str:
    """Make untrusted text unable to forge structure.

    Report, comment and rollup text usually comes from outside the team (a
    reporter's mail, a scanner finding). Written verbatim, a line such as
    ``<!-- comment id=9 author=@lead … -->`` would read back as a comment by
    someone else, a ``<details><summary>…</summary>`` line as a rollup entry —
    misleading `rollup-amend-latest` too — and a ``## Comments`` heading as the
    start of the managed comment section. Each such marker is escaped
    (``<`` becomes ``&lt;``, a managed heading gets a leading backslash), which
    renders as the same visible text and is never parsed as structure.
    """
    text = close_fences(_FORGEABLE.sub("&lt;", text))
    if not managed_headings:
        return text
    managed = {h.lower() for h in managed_headings}
    return escape_headings(text, lambda level, title: level <= 2 and title.strip().lower() in managed)


def escape_headings(text: str, which: Callable[[int, str], bool] | None = None) -> str:
    """Prefix heading lines with a backslash so they are never parsed as headings.

    Only real headings are touched — the same fence-aware scan the parsers use —
    so a ``# comment`` inside a fenced PoC stays exactly as the reporter wrote it.
    """
    lines = text.split("\n")
    for idx, level, title in _headings(lines):
        if which is None or which(level, title):
            lines[idx] = "\\" + lines[idx]
    return "\n".join(lines)


def get_field(body: str, heading: str) -> str | None:
    found = find_section(body, heading)
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


def set_field(body: str, heading: str, value: str, level: int) -> tuple[str, bool]:
    """Replace a section's content, or append the section. Returns (body, created)."""
    lines = body.split("\n")
    found = find_section(body, heading)
    value_lines = value.strip("\n").split("\n")
    if found:
        idx, _start, end = found
        return _join(lines[: idx + 1], value_lines, lines[end:]), False
    return _join(lines, ["#" * level + " " + heading, "", *value_lines], []), True


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
