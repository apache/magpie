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
"""Pure parser + composer for the status-rollup comment shape.

The on-disk spec lives at
[`tools/github/status-rollup.md`](../../../../github/status-rollup.md);
this module is the executable spec the CLI dispatches to. Keeping
the parser pure (no I/O, no `gh` shellouts) lets the tests exhaust
every edge case (legacy variants, missing rulers, embedded
backticks, trailing whitespace) without mocking subprocess.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

# First line the tools write when they create a rollup: the
# framework-wide `<!-- apache-magpie: <kind> v<N> -->` skill-comment
# marker, with `status-rollup` as the kind.
ROLLUP_MARKER = "<!-- apache-magpie: status-rollup v1 -->"

# The canonical marker, any version so a future `v2` bump stays findable.
CANONICAL_MARKER_RE = re.compile(r"^<!-- apache-magpie: status-rollup v\d+\b")

# The legacy marker earlier versions wrote,
# `<!-- <name> status rollup v<N> — … -->`, where `<name>` is the tracker
# repository's name (for example `airflow-s`). Still recognised so a
# tracker whose rollup predates the canonical marker keeps working.
LEGACY_MARKER_RE = re.compile(r"^<!-- \S+ status rollup v\d+")

# Either marker — what "is this comment a rollup" detection matches.
ROLLUP_MARKER_RE = re.compile(r"^<!-- (?:apache-magpie: status-rollup|\S+ status rollup) v\d+")

# Kept for callers that imported it; detection no longer depends on it.
ROLLUP_MARKER_PREFIX = "<!-- airflow-s status rollup v"


def is_rollup_body(body: str) -> bool:
    """True when ``body`` starts with a status-rollup marker line,
    canonical or legacy."""
    return bool(ROLLUP_MARKER_RE.match(body))


def is_canonical_rollup_body(body: str) -> bool:
    """True when ``body`` starts with the canonical
    `<!-- apache-magpie: status-rollup v<N> -->` marker."""
    return bool(CANONICAL_MARKER_RE.match(body))


def find_rollup_index(
    bodies: Sequence[str],
    authors: Sequence[str] | None = None,
    trusted: Collection[str] | None = None,
) -> int | None:
    """Index of the rollup among the comment ``bodies``, or ``None``.

    The first comment with the canonical marker wins; failing that, the
    first with a legacy marker. Preferring the canonical one means a
    tracker that carries both (a legacy-marker comment written next to
    the skills' rollup) keeps growing the rollup the skills read.

    When ``trusted`` is given, ``authors`` holds each comment's author
    login (parallel to ``bodies``), and only a comment whose author is in
    ``trusted`` (compared case-insensitively, as GitHub logins are) can be
    the rollup. A marker line in a comment by anyone else is ignored, so a
    commenter outside the trusted set cannot plant a comment the tools
    then read from or write to.
    """
    eligible = [True] * len(bodies)
    if trusted is not None:
        if authors is None or len(authors) != len(bodies):
            raise ValueError("authors must list one login per body when trusted is given")
        allowed = {login.lower() for login in trusted if login}
        eligible = [bool(login) and login.lower() in allowed for login in authors]
    legacy: int | None = None
    for i, body in enumerate(bodies):
        if not eligible[i]:
            continue
        if is_canonical_rollup_body(body):
            return i
        if legacy is None and is_rollup_body(body):
            legacy = i
    return legacy


def marker_line(tracker_name: str = "") -> str:
    """The first-line marker the tool writes when creating a rollup.

    ``tracker_name`` is accepted so existing callers keep working; the
    canonical marker no longer names the tracker, so it is ignored.
    """
    del tracker_name
    return ROLLUP_MARKER


# Between consecutive `<details>` entries we always write exactly one
# blank line, a horizontal rule, and one blank line. Keeping this as
# a module constant guarantees `append` lays it down byte-identical
# every time so the regex round-trips.
_RULER_BETWEEN_ENTRIES = "\n\n---\n\n"

# Open and close tags for one rollup entry. The open tag is one line
# per the spec — split-tag variants get normalised on the next write.
_OPEN_TAG_RE = re.compile(r"^<details><summary>(.+?)</summary>$", re.MULTILINE)
_CLOSE_TAG = "</details>"


@dataclass(frozen=True)
class RollupEntry:
    """One parsed rollup entry."""

    date: str  # YYYY-MM-DD
    user: str  # @handle (with leading `@`)
    action: str  # human-friendly action label
    body: str  # the markdown between <summary>...</summary> and </details>


def parse_summary_line(summary: str) -> RollupEntry | None:
    """Parse the summary line's three middle-dot-separated fields.

    Returns ``None`` when the summary doesn't follow the
    `YYYY-MM-DD · @handle · <Action>` shape — the caller can keep
    the entry as raw text without failing the whole parse.
    """
    parts = [p.strip() for p in summary.split("·")]
    if len(parts) != 3:
        return None
    date, user, action = parts
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return None
    if not user.startswith("@") or len(user) < 2:
        return None
    if not action:
        return None
    return RollupEntry(date=date, user=user, action=action, body="")


def iter_entries(rollup_body: str) -> list[RollupEntry]:
    """Walk a full rollup-comment body and return every entry it
    contains, ordered top-to-bottom.

    Robust to:

    - the marker line at the top of the comment,
    - rulers (`---`) between entries,
    - entries whose summary doesn't follow the canonical shape
      (those are returned with `date=user=action=""` and the
      surrounding context still in `body` for downstream
      preservation),
    - trailing whitespace and missing trailing newline.
    """
    text = rollup_body
    # Drop the marker line if present so the regex doesn't false-match
    # the marker's HTML-comment content.
    if is_rollup_body(text):
        nl = text.find("\n")
        text = text[nl + 1 :] if nl != -1 else ""

    entries: list[RollupEntry] = []
    pos = 0
    for match in _OPEN_TAG_RE.finditer(text):
        summary = match.group(1)
        body_start = match.end()
        close_idx = text.find(f"\n{_CLOSE_TAG}", body_start)
        if close_idx == -1:
            # Tolerate a missing close tag at end-of-body.
            entry_body = text[body_start:].lstrip("\n").rstrip()
            next_pos = len(text)
        else:
            entry_body = text[body_start:close_idx].lstrip("\n").rstrip()
            next_pos = close_idx + len(f"\n{_CLOSE_TAG}")
        parsed = parse_summary_line(summary)
        if parsed is None:
            entries.append(RollupEntry(date="", user="", action="", body=entry_body))
        else:
            entries.append(
                RollupEntry(
                    date=parsed.date,
                    user=parsed.user,
                    action=parsed.action,
                    body=entry_body,
                )
            )
        pos = next_pos
    # `pos` is unused for the return but kept so future callers can
    # compute trailing content if they need to.
    _ = pos
    return entries


def build_entry(*, date: str, user: str, action: str, body: str) -> str:
    """Compose one rollup entry — the `<details>...</details>` block
    a single sync pass appends to the rollup.

    The result has no trailing newline; the caller decides whether
    to glue a ruler before it. The body's leading + trailing
    whitespace is stripped to keep the rendered shape consistent.
    """
    if not user.startswith("@"):
        user = f"@{user}"
    body_stripped = body.strip()
    summary = f"{date} · {user} · {action}"
    return f"<details><summary>{summary}</summary>\n\n{body_stripped}\n\n{_CLOSE_TAG}"


def build_new_rollup_body(entry: str, tracker_name: str = "") -> str:
    """Compose a brand-new rollup comment body wrapping the first
    entry. Use when no rollup comment exists yet on the tracker.
    The body always starts with the canonical marker; ``tracker_name``
    is accepted for existing callers and ignored.
    """
    return f"{marker_line(tracker_name)}\n{entry}"


def rebuild_with_appended_entry(existing_body: str, new_entry: str) -> str:
    """Append ``new_entry`` to an existing rollup body, separated by
    the canonical ruler block. Strips any trailing whitespace from
    ``existing_body`` so the ruler lands in the right place.
    """
    return f"{existing_body.rstrip()}{_RULER_BETWEEN_ENTRIES}{new_entry}"


def insert_entries_by_date(existing_body: str, entries: Sequence[RollupEntry]) -> str:
    """Insert ``entries`` into ``existing_body`` in date order.

    Each entry lands before the first existing entry dated the same day or
    later, or at the end when none is, so the existing latest entry stays
    last: readers take the last entry as the tracker's current state, and
    a summary carries only a date, so a same-day entry being merged in is
    not known to be newer. Existing entries keep their text
    byte-identical; an existing entry whose summary does not parse is
    never an anchor, and entries sharing a slot keep their given order.
    """
    body = existing_body.rstrip()
    anchors: list[tuple[int, str]] = []
    # Walk entries the way `iter_entries` does: an open tag inside an entry's
    # body (a quoted example, a nested block) is part of that entry, never an
    # anchor, or a merged entry could land inside it.
    entry_end = 0
    for match in _OPEN_TAG_RE.finditer(body):
        if match.start() < entry_end:
            continue
        close_idx = body.find(f"\n{_CLOSE_TAG}", match.end())
        entry_end = len(body) if close_idx == -1 else close_idx + len(f"\n{_CLOSE_TAG}")
        parsed = parse_summary_line(match.group(1))
        if parsed is not None:
            anchors.append((match.start(), parsed.date))
    slots: dict[int, list[str]] = {}
    for entry in sorted(entries, key=lambda e: e.date):
        pos = next((start for start, date in anchors if date >= entry.date), len(body))
        block = build_entry(date=entry.date, user=entry.user, action=entry.action, body=entry.body)
        slots.setdefault(pos, []).append(block)
    for pos in sorted(slots, reverse=True):
        blocks = _RULER_BETWEEN_ENTRIES.join(slots[pos])
        if pos == len(body):
            body = f"{body}{_RULER_BETWEEN_ENTRIES}{blocks}"
        else:
            body = f"{body[:pos]}{blocks}{_RULER_BETWEEN_ENTRIES}{body[pos:]}"
    return body


def replace_latest_entry(existing_body: str, new_entry: str) -> str:
    """Replace the last `<details>` entry of ``existing_body`` with
    ``new_entry``, keeping everything before it byte-identical.

    Raises ``ValueError`` when the body has no entry to replace.
    """
    body = existing_body.rstrip()
    starts = [m.start() for m in _OPEN_TAG_RE.finditer(body)]
    if not starts:
        raise ValueError("rollup has no entries")
    return f"{body[: starts[-1]]}{new_entry}"


def left_trim_lines(text: str) -> str:
    """Left-trim every line. Legacy comments that were hand-edited carry
    stray indentation that would render as a code block inside
    `<details>`."""
    return "\n".join(line.lstrip() for line in text.splitlines())
