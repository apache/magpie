# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Markdown section surgery, comment entries, and the status rollup."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line index, level, text) for every ATX heading outside code fences."""
    out: list[tuple[int, int, str]] = []
    fence = ""
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            fence = "" if fence == marker else (fence or marker)
            continue
        if fence:
            continue
        m = _HEADING_RE.match(line)
        if m:
            out.append((idx, len(m.group("hashes")), m.group("text").strip()))
    return out


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


def get_field(body: str, heading: str) -> str | None:
    found = find_section(body, heading)
    if not found:
        return None
    _, start, end = found
    return "\n".join(body.split("\n")[start:end]).strip("\n")


def set_field(body: str, heading: str, value: str, level: int) -> tuple[str, bool]:
    """Replace a section's content, or append the section. Returns (body, created)."""
    lines = body.split("\n")
    found = find_section(body, heading)
    content = ["", value.strip("\n"), ""]
    if found:
        _, start, end = found
        new = lines[:start] + content + lines[end:]
        return _tidy("\n".join(new)), False
    insert_at = len(lines)
    new = [*lines[:insert_at], "", "#" * level + " " + heading, *content]
    return _tidy("\n".join(new)), True


def append_to_section(body: str, heading: str, level: int, text: str) -> str:
    """Append ``text`` at the end of a section, creating it at the end of the body."""
    lines = body.split("\n")
    found = find_section(body, heading, level)
    if found:
        _, _, end = found
        new = [*lines[:end], "", text.strip("\n"), "", *lines[end:]]
    else:
        new = [*lines, "", "#" * level + " " + heading, "", text.strip("\n"), ""]
    return _tidy("\n".join(new))


def _tidy(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n") + "\n"


# ---------------------------------------------------------------- comments

_COMMENT_MARK = re.compile(r"^<!-- comment id=(?P<id>\d+) author=(?P<author>\S*) date=(?P<date>\S+) -->$")


@dataclass
class Comment:
    id: int
    author: str
    created: str
    body: str


def render_comment(comment_id: int, author: str, date: str, body: str, level: int) -> str:
    return (
        f"<!-- comment id={comment_id} author={author} date={date} -->\n"
        f"{'#' * level} {date[:10]} — {author}\n\n{body.strip()}\n"
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
            current = Comment(int(marker.group("id")), marker.group("author"), marker.group("date"), "")
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

ROLLUP_MARKER_RE = re.compile(r"<!-- (?P<name>\S+) status rollup v(?P<v>\d+)")
_SUMMARY_RE = re.compile(r"^<details><summary>(?P<summary>.*)</summary>\s*$")


def rollup_marker(name: str) -> str:
    return (
        f"<!-- {name} status rollup v1 — all bot-authored status updates fold into this single comment. -->"
    )


def render_entry(date: str, user: str, action: str, body: str) -> str:
    trimmed = "\n".join(line.lstrip() for line in body.strip("\n").split("\n"))
    return f"<details><summary>{date} · {user} · {action}</summary>\n\n{trimmed}\n\n</details>"


def rollup_append(existing: str | None, name: str, entry: str) -> str:
    if not existing or not ROLLUP_MARKER_RE.search(existing):
        return rollup_marker(name) + "\n" + entry + "\n"
    return existing.rstrip("\n") + "\n\n---\n\n" + entry + "\n"


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
