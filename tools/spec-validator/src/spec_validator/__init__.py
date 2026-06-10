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

"""Validate spec files in tools/spec-loop/specs/.

Checks every .md file that carries a YAML frontmatter block:

1. Required frontmatter keys — title, status, kind, mode, source, acceptance.
2. Valid ``status`` value — stable | experimental | proposed | off.
3. Valid ``kind`` value  — feature | fix | docs | chore.
4. Valid ``mode`` value  — Triage | Mentoring | Drafting | Pairing | infra.
5. Non-empty ``acceptance`` list — at least one ``- item`` entry.
6. Required body sections — What it does, Where it lives,
   Behaviour & contract, Out of scope, Acceptance criteria, Validation,
   Known gaps.
7. Validation section contains at least one fenced code block.

Files without frontmatter (README.md, overview.md) are skipped silently.

Run from repo root::

    uv run --project tools/spec-validator --group dev pytest
    uv run --project tools/spec-validator spec-validate tools/spec-loop/specs/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_FRONTMATTER_KEYS: frozenset[str] = frozenset(
    {"title", "status", "kind", "mode", "source", "acceptance"}
)
ALLOWED_STATUS: frozenset[str] = frozenset({"stable", "experimental", "proposed", "off"})
ALLOWED_KIND: frozenset[str] = frozenset({"feature", "fix", "docs", "chore"})
ALLOWED_MODE: frozenset[str] = frozenset({"Triage", "Mentoring", "Drafting", "Pairing", "infra"})

REQUIRED_SECTIONS: tuple[str, ...] = (
    "What it does",
    "Where it lives",
    "Behaviour & contract",
    "Out of scope",
    "Acceptance criteria",
    "Validation",
    "Known gaps",
)

DEFAULT_SPEC_DIR = Path("tools/spec-loop/specs")

_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_FENCED_CODE_RE = re.compile(r"^ {0,3}```[\s\S]*?^ {0,3}```", re.MULTILINE)
_YAML_BLOCK_SCALAR_HEADERS: frozenset[str] = frozenset({"|", ">", "|-", "|+", ">-", ">+"})


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
    """Return (block_start, block_end) for the frontmatter content, or None.

    Handles files whose first non-whitespace content is an HTML comment
    (e.g. the SPDX license header) before the ``---`` delimiter.
    """
    idx = text.find("---\n")
    if idx == -1:
        return None
    # Verify only HTML comments / whitespace precede the opening ---
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


def has_acceptance_items(text: str) -> bool:
    """Return True if the ``acceptance`` frontmatter key has at least one list item."""
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return False
    block = text[bounds[0] : bounds[1]]
    in_acceptance = False
    for line in block.splitlines():
        if not line.startswith((" ", "\t")) and ":" in line:
            in_acceptance = line.split(":", 1)[0].strip() == "acceptance"
            continue
        if in_acceptance and re.match(r"\s+-\s", line):
            return True
    return False


# ---------------------------------------------------------------------------
# Body section validation
# ---------------------------------------------------------------------------


def _spec_body(text: str) -> str:
    """Return the doc body — everything after the closing ``---`` frontmatter delimiter."""
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return text
    # body starts after "\n---\n"
    return text[bounds[1] + 5 :]


def extract_section_headings(text: str) -> set[str]:
    """Return the text of every ## heading in the spec body."""
    body = _spec_body(text)
    headings: set[str] = set()
    for line in body.splitlines():
        if line.startswith("## "):
            headings.add(line[3:].strip())
    return headings


def get_section_body(text: str, section: str) -> str | None:
    """Return the content of a named ## section, or None."""
    body = _spec_body(text)
    lines = body.splitlines()
    collecting = False
    collected: list[str] = []
    for line in lines:
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading == section:
                collecting = True
                continue
            if collecting:
                break
        if collecting:
            collected.append(line)
    return "\n".join(collected) if collected else None


def validation_has_code_block(text: str) -> bool:
    """Return True if the Validation section contains at least one fenced code block."""
    section = get_section_body(text, "Validation")
    if not section:
        return False
    return bool(_FENCED_CODE_RE.search(section))


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_frontmatter(path: Path, text: str) -> list[Violation]:
    fm = parse_frontmatter(text)
    if fm is None:
        return []  # No frontmatter — not a spec file; skip silently

    violations: list[Violation] = []

    missing = REQUIRED_FRONTMATTER_KEYS - set(fm.keys())
    for key in sorted(missing):
        violations.append(Violation(path, 1, f"missing required frontmatter key: '{key}'"))

    if "status" in fm and fm["status"] not in ALLOWED_STATUS:
        violations.append(
            Violation(
                path,
                1,
                f"invalid status '{fm['status']}' — must be one of {sorted(ALLOWED_STATUS)}",
            )
        )

    if "kind" in fm and fm["kind"] not in ALLOWED_KIND:
        violations.append(
            Violation(
                path,
                1,
                f"invalid kind '{fm['kind']}' — must be one of {sorted(ALLOWED_KIND)}",
            )
        )

    if "mode" in fm and fm["mode"] not in ALLOWED_MODE:
        violations.append(
            Violation(
                path,
                1,
                f"invalid mode '{fm['mode']}' — must be one of {sorted(ALLOWED_MODE)}",
            )
        )

    if "acceptance" in fm and not has_acceptance_items(text):
        violations.append(
            Violation(path, 1, "acceptance key is present but has no list items (expected '  - ...')")
        )

    return violations


def validate_body(path: Path, text: str) -> list[Violation]:
    if parse_frontmatter(text) is None:
        return []  # Not a spec file

    violations: list[Violation] = []
    headings = extract_section_headings(text)

    for section in REQUIRED_SECTIONS:
        if section not in headings:
            violations.append(Violation(path, None, f"missing required section: '## {section}'"))

    if "Validation" in headings and not validation_has_code_block(text):
        violations.append(
            Violation(path, None, "Validation section has no fenced code block (expected ```...```)")
        )

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


def collect_spec_files(target: Path) -> list[Path]:
    """Return all .md files under *target* (or *target* itself if a file)."""
    if target.is_file():
        return [target]
    return sorted(target.rglob("*.md"))


def run_validation(target: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in collect_spec_files(target):
        violations.extend(validate_file(path))
    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate spec files.")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_SPEC_DIR),
        help="Spec file or directory to validate (default: tools/spec-loop/specs/)",
    )
    args = parser.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"spec-validator: path not found: {target}", file=sys.stderr)
        return 1

    violations = run_validation(target)
    if not violations:
        print("spec-validator: OK (no violations)")
        return 0

    print(f"spec-validator: {len(violations)} violation(s) found\n")
    for v in violations:
        print(v)
    return 1


if __name__ == "__main__":
    sys.exit(main())
