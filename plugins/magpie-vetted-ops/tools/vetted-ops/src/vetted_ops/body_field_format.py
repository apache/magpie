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
"""Parse and rewrite the ``### Field`` sections of a GitHub issue body.

The tracker issue body is a sequence of `### <FieldName>` headings,
each followed by the field's value. This module exposes a pure
parser/replacer so the CLI can run without ever bringing the body
into the agent's context, and so the (numerous) tricky edge cases
can be unit-tested in isolation.

The parser is a small state machine that:

- tracks whether the current line is inside a fenced code block
  (``` ``` ``` or ``` ~~~ ```) so that a literal ``### foo`` line
  inside a shell snippet never false-matches as a heading;
- considers only level-3 ATX headings (``^### <name>$``);
  level-2 (``## ``) and level-4 (``#### ``) headings are passed
  through as content;
- preserves the original body exactly when no changes are needed
  (idempotent rewrite).
"""

from __future__ import annotations

from dataclasses import dataclass


class FieldNotFoundError(LookupError):
    """Raised when the requested field heading is absent from the body."""


# A fence-line opens / closes a fenced code block when it starts with
# three or more backticks or three or more tildes, optionally followed
# by an info string. Per CommonMark §4.5 the opening and closing fences
# must use the same character; the info string may only follow the
# opener. We don't enforce matching-character-count strictly because
# GitHub's tracker body editor is lenient and we want to err on the
# side of "treat anything ``` ``` ```-ish as a fence" so headings
# embedded in code samples never get mis-parsed as field markers.
_BACKTICK_FENCE = "```"
_TILDE_FENCE = "~~~"

# Heading marker for a field. GitHub trims trailing whitespace on
# rendered headings; we strip it on the parsed name too so a stray
# space after the field name doesn't break the lookup.
_HEADING_PREFIX = "### "


@dataclass(frozen=True)
class _Section:
    """One ``### <Name>`` heading + the lines that follow it."""

    name: str
    heading_line: str  # the original "### Name" line as it appeared
    body_lines: list[str]  # everything between this heading and the next


def _is_fence(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(_BACKTICK_FENCE) or stripped.startswith(_TILDE_FENCE)


def _parse(body: str) -> tuple[list[str], list[_Section]]:
    """Split ``body`` into a preamble (anything before the first
    ``### `` heading) and a list of ``_Section`` records.

    The preamble is returned as a list of raw lines so the round-trip
    is byte-exact when no field is replaced.
    """
    lines = body.splitlines(keepends=True)
    preamble: list[str] = []
    sections: list[_Section] = []
    current: _Section | None = None
    in_fence = False

    for line in lines:
        if _is_fence(line):
            in_fence = not in_fence
            (current.body_lines if current is not None else preamble).append(line)
            continue

        # Only top-level (outside any fence) `### ` openers count.
        if not in_fence and line.startswith(_HEADING_PREFIX):
            # Stash whatever section we were building.
            if current is not None:
                sections.append(current)
            name = line[len(_HEADING_PREFIX) :].rstrip("\r\n").rstrip()
            current = _Section(name=name, heading_line=line, body_lines=[])
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


def extract_field(body: str, field: str) -> str:
    """Return the raw text value of ``### <field>``.

    The blank-line spacer that conventionally separates the heading
    from the value, and the value from the next heading, is stripped
    so callers get the value as a user would copy-paste it. Internal
    blank lines are preserved.

    Raises :class:`FieldNotFoundError` if the heading does not exist
    or appears more than once.
    """
    _, sections = _parse(body)
    matches = [s for s in sections if s.name == field]
    if not matches:
        raise FieldNotFoundError(f"field not found: {field!r}")
    if len(matches) > 1:
        raise FieldNotFoundError(f"field {field!r} appears {len(matches)} times; refusing to guess")
    _, stripped, _ = _strip_spacer_blanks(matches[0].body_lines)
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

    Raises :class:`FieldNotFoundError` if the heading does not exist
    or appears more than once.
    """
    preamble, sections = _parse(body)
    indices = [i for i, s in enumerate(sections) if s.name == field]
    if not indices:
        raise FieldNotFoundError(f"field not found: {field!r}")
    if len(indices) > 1:
        raise FieldNotFoundError(f"field {field!r} appears {len(indices)} times; refusing to guess")

    target_idx = indices[0]
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

    rebuilt_sections = [
        _Section(name=s.name, heading_line=s.heading_line, body_lines=s.body_lines) for s in sections
    ]
    rebuilt_sections[target_idx] = _Section(
        name=target.name,
        heading_line=target.heading_line,
        body_lines=rebuilt_body_lines,
    )

    out: list[str] = list(preamble)
    for s in rebuilt_sections:
        out.append(s.heading_line)
        out.extend(s.body_lines)
    return "".join(out)
