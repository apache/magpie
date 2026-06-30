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

"""Validate adopter pilot-report Markdown files.

Checks every .md file that carries a YAML frontmatter block for:

1. Required frontmatter keys — skill, date, target_repo, profile.
2. Valid ``profile`` value — asf | non-asf | custom.
3. No unfilled placeholders — frontmatter values must not contain
   un-substituted ``<...>`` tokens, and ``date`` must be a real ISO 8601
   date (YYYY-MM-DD).
4. Required body sections — Skill or family, Target repo and profile,
   Blocked preflights, False positives, Confirmation points,
   Privacy and adapter notes, Proposed spec changes.

The frontmatter block must be at the top of the file; YAML frontmatter
placed lower in the document is not detected. Files without a
top-of-file frontmatter block (e.g. README.md) are skipped silently.
``docs/pilot-report-template.md`` ships with placeholder frontmatter
values, so running the validator on the unedited template reports those
placeholders until they are filled in.

Run from repo root::

    uv run --project tools/pilot-report-validator \
        pilot-report-validate docs/pilot-report-template.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_FRONTMATTER_KEYS: frozenset[str] = frozenset({"skill", "date", "target_repo", "profile"})

ALLOWED_PROFILES: frozenset[str] = frozenset({"asf", "non-asf", "custom"})

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Skill or family",
    "Target repo and profile",
    "Blocked preflights",
    "False positives",
    "Confirmation points",
    "Privacy and adapter notes",
    "Proposed spec changes",
)

_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_YAML_BLOCK_SCALAR_HEADERS: frozenset[str] = frozenset({"|", ">", "|-", "|+", ">-", ">+"})

# An un-substituted template placeholder, e.g. "<skill-name>" or "<owner>/<repo>".
_ANGLE_PLACEHOLDER_RE = re.compile(r"<[^<>\n]+>")
# ISO 8601 calendar date (YYYY-MM-DD); also rejects the "YYYY-MM-DD" placeholder.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Violation:
    def __init__(self, path: Path, line: int | None, message: str) -> None:
        self.path = path
        self.line = line
        self.message = message

    def __str__(self) -> str:
        if self.line is not None:
            return f"{self.path}:{self.line}: {self.message}"
        return f"{self.path}: {self.message}"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _frontmatter_bounds(text: str) -> tuple[int, int] | None:
    """Return (content_start, content_end) for the frontmatter block, or None.

    Handles files whose first non-whitespace content is an HTML comment
    (e.g. an SPDX license header) before the opening ``---`` delimiter.
    """
    idx = text.find("---\n")
    if idx == -1:
        return None
    prefix = text[:idx]
    clean = _HTML_COMMENT_RE.sub("", prefix).strip()
    if clean:
        return None
    try:
        end = text.index("\n---\n", idx + 4)
    except ValueError:
        return None
    return (idx + 4, end)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return a dict of top-level frontmatter key→value, or None if absent."""
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return None
    block = text[bounds[0] : bounds[1]]

    result: dict[str, str] = {}
    current_key: str | None = None
    current_value_lines: list[str] = []

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if line == "":
            if current_key is not None:
                current_value_lines.append("")
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            if current_key is not None:
                result[current_key] = "\n".join(current_value_lines).strip()
            key, _, value = line.partition(":")
            current_key = key.strip()
            inline = value.strip()
            current_value_lines = [inline] if inline and inline not in _YAML_BLOCK_SCALAR_HEADERS else []
            continue
        if current_key is not None:
            stripped = line[2:] if line.startswith("  ") else line
            current_value_lines.append(stripped)

    if current_key is not None:
        result[current_key] = "\n".join(current_value_lines).strip()
    return result


# ---------------------------------------------------------------------------
# Body section helpers
# ---------------------------------------------------------------------------


def _spec_body(text: str) -> str:
    """Return the document body — everything after the closing ``---`` delimiter."""
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return text
    return text[bounds[1] + 5 :]


def extract_section_headings(text: str) -> set[str]:
    """Return the text of every ## heading in the document body."""
    body = _spec_body(text)
    headings: set[str] = set()
    for line in body.splitlines():
        if line.startswith("## "):
            headings.add(line[3:].strip())
    return headings


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_frontmatter(path: Path, text: str) -> list[Violation]:
    fm = parse_frontmatter(text)
    if fm is None:
        return []  # No frontmatter — not a report file; skip silently

    violations: list[Violation] = []

    missing = REQUIRED_FRONTMATTER_KEYS - set(fm.keys())
    for key in sorted(missing):
        violations.append(Violation(path, 1, f"missing required frontmatter key: '{key}'"))

    if "profile" in fm and fm["profile"] not in ALLOWED_PROFILES:
        violations.append(
            Violation(
                path,
                1,
                f"invalid profile '{fm['profile']}' — must be one of {sorted(ALLOWED_PROFILES)}",
            )
        )

    # Un-substituted template placeholders left in any frontmatter value.
    for key in sorted(fm):
        if _ANGLE_PLACEHOLDER_RE.search(fm[key]):
            violations.append(
                Violation(
                    path,
                    1,
                    f"frontmatter key '{key}' still contains an un-substituted placeholder: {fm[key]!r}",
                )
            )

    # Date value must be a real ISO 8601 date (also catches the 'YYYY-MM-DD' placeholder).
    if fm.get("date") and not _ISO_DATE_RE.match(fm["date"]):
        violations.append(
            Violation(path, 1, f"invalid date '{fm['date']}' — must be ISO 8601 format YYYY-MM-DD")
        )

    return violations


def validate_body(path: Path, text: str) -> list[Violation]:
    if parse_frontmatter(text) is None:
        return []  # Not a report file

    violations: list[Violation] = []
    headings = extract_section_headings(text)

    for section in REQUIRED_SECTIONS:
        if section not in headings:
            violations.append(Violation(path, None, f"missing required section: '## {section}'"))

    return violations


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def validate_file(path: Path) -> list[Violation]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [Violation(path, None, f"cannot read file: {exc}")]
    return validate_frontmatter(path, text) + validate_body(path, text)


def collect_report_files(target: Path) -> list[Path]:
    """Return all .md files under *target* (or *target* itself if a file)."""
    if target.is_file():
        return [target]
    return sorted(target.rglob("*.md"))


def run_validation(target: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in collect_report_files(target):
        violations.extend(validate_file(path))
    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate adopter pilot-report files.",
        epilog="Files without frontmatter (READMEs, templates) are silently skipped.",
    )
    parser.add_argument(
        "path",
        help="Pilot-report file or directory to validate.",
    )
    args = parser.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"pilot-report-validate: path not found: {target}", file=sys.stderr)
        return 1

    violations = run_validation(target)
    if not violations:
        print("pilot-report-validate: OK (no violations)")
        return 0

    print(f"pilot-report-validate: {len(violations)} violation(s) found\n")
    for v in violations:
        print(v)
    return 1


if __name__ == "__main__":
    sys.exit(main())
