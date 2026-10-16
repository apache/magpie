# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""Body-field sections and the status rollup, in Jira wiki markup.

A body field is a level-3 section: ``h3. <Heading>`` (wiki markup), or
``### <Heading>`` (Markdown, read compatibility), running until the next
level 1-3 heading of either syntax.  Headings inside ``{code}`` /
``{noformat}`` macros and Markdown code fences are ignored.

The rollup is one comment whose first line is the invisible anchor macro
:data:`ROLLUP_MARKER`; each entry is a bold summary line
``*YYYY-MM-DD · @user · <Action>*``, a blank line, the entry body, and
entries are separated by a ``----`` line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ROLLUP_MARKER = "{anchor:magpie-status-rollup-v1}"

_MARKER_RE = re.compile(r"^\{anchor:magpie-status-rollup-v\d+\}\s*$")
_SUMMARY_RE = re.compile(r"^\*(\d{4}-\d{2}-\d{2}) · @(.+?) · (.+)\*\s*$")
_WIKI_HEADING_RE = re.compile(r"^\s*h([1-6])\.\s+(.*?)\s*$")
_MD_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_WIKI_BLOCK_RE = re.compile(r"\{(code|noformat)(?::[^}]*)?\}")
_FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")


@dataclass(frozen=True)
class Heading:
    """A heading line found in a body."""

    index: int
    level: int
    text: str
    wiki: bool


def _normalise(name: str) -> str:
    return " ".join(name.split()).casefold()


def find_headings(lines: list[str]) -> list[Heading]:
    """Return every heading outside code blocks, in document order."""
    headings: list[Heading] = []
    in_wiki_block: str | None = None
    in_fence = False
    for index, line in enumerate(lines):
        if in_fence:
            if _FENCE_RE.match(line):
                in_fence = False
            continue
        if in_wiki_block is not None:
            # A {code} / {noformat} block closes on the bare macro name.
            if "{" + in_wiki_block + "}" in line:
                in_wiki_block = None
            continue
        if _FENCE_RE.match(line):
            in_fence = True
            continue
        macros = _WIKI_BLOCK_RE.findall(line)
        if len(macros) % 2 == 1:
            in_wiki_block = macros[-1]
            continue
        wiki = _WIKI_HEADING_RE.match(line)
        if wiki:
            headings.append(Heading(index, int(wiki.group(1)), wiki.group(2), True))
            continue
        md = _MD_HEADING_RE.match(line)
        if md:
            headings.append(Heading(index, len(md.group(1)), md.group(2), False))
    return headings


def _locate(lines: list[str], heading: str) -> tuple[int, int] | None:
    """Return ``(heading_index, end_index)`` of the field section, or None."""
    wanted = _normalise(heading)
    headings = find_headings(lines)
    for pos, found in enumerate(headings):
        if found.level == 3 and _normalise(found.text) == wanted:
            end = len(lines)
            for later in headings[pos + 1 :]:
                if later.level <= 3:
                    end = later.index
                    break
            return found.index, end
    return None


def get_field(body: str, heading: str) -> str | None:
    """Return the stripped value of the ``heading`` section, or None when missing."""
    lines = body.splitlines()
    span = _locate(lines, heading)
    if span is None:
        return None
    start, end = span
    return "\n".join(lines[start + 1 : end]).strip()


def set_field(body: str, heading: str, value: str) -> tuple[str, bool]:
    """Replace (or append) the ``heading`` section; return ``(new_body, created)``."""
    lines = body.splitlines()
    value_lines = value.strip("\n").splitlines()
    span = _locate(lines, heading)
    if span is not None:
        start, end = span
        tail = lines[end:]
        new_lines = [*lines[: start + 1], *value_lines]
        if tail:
            new_lines.append("")
        new_lines.extend(tail)
        return "\n".join(new_lines) + "\n", False
    headings = find_headings(lines)
    markdown_only = bool(headings) and not any(h.wiki for h in headings)
    heading_line = f"### {heading}" if markdown_only else f"h3. {heading}"
    prefix = body.rstrip()
    section = "\n".join([heading_line, *value_lines]) + "\n"
    return (f"{prefix}\n\n{section}" if prefix else section), True


@dataclass
class RollupEntry:
    """One rollup entry."""

    date: str
    user: str
    action: str
    body: str


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
