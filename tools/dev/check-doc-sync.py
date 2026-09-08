#!/usr/bin/env python3
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

"""Check the documentation claims that must track the tree, and silently rot.

Four checks, all mechanical, each one written after the drift it catches was
found by hand:

1. **Spec-index completeness.** Every ``tools/spec-loop/specs/<name>.md`` is
   listed in both ``overview.md`` and ``README.md``. Ten specs were absent from
   both — including per-family specs and one added four PRs earlier — because
   nothing checked, and an index that lists two-thirds of its subject reads
   exactly like one that lists all of it.

2. **Per-family skill counts in README.md.** The family table's "N skills" cell
   against the live ``family:`` frontmatter. Two cells were wrong: one went
   stale when three skills landed, the other had been drifting for months.

3. **Per-mode skill counts in docs/modes.md.** The *Modes at a glance* table's
   Skill-count column against the live ``mode:`` frontmatter. The validator's
   ``modes-doc`` rule checks section *membership* but reads only the mode and
   status columns, so the counts were unguarded.

4. **Total-skill claims in prose.** A small allowlist of files whose "N skills"
   phrasing means the whole catalogue.

5. **Every script in ``tools/dev/`` is named in its README.** These scripts are
   the framework's own gates, and an undocumented one is invisible to the next
   contributor who has to decide whether it applies to their change. Naming it
   is the minimum; the README says what each guards.

Why counting is worth a hook at all: every one of these is a number a human has
to remember to update while thinking about something else, and none of them
breaks anything when wrong. They just quietly mislead the next reader.

Run from the repo root:

    python3 tools/dev/check-doc-sync.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKILLS_DIR = Path("skills")
SPECS_DIR = Path("tools/spec-loop/specs")
SPEC_INDEXES = (SPECS_DIR / "overview.md", SPECS_DIR / "README.md")
# The index files themselves are not specs.
SPEC_INDEX_NAMES = {p.name for p in SPEC_INDEXES}

# Files whose bare "N skills" phrasing means the whole catalogue. Deliberately
# an allowlist rather than a repo-wide sweep: plenty of docs legitimately count
# a subset ("Nine skills cover the staged path"), and a greedy scan would flag
# those as drift forever.
TOTAL_COUNT_FILES = (Path("docs/setup/marketplaces.md"),)

# Dev scripts must each be named in tools/dev/README.md. Suffixes rather than a
# mode check: a script is a script whether or not its executable bit survived a
# checkout.
DEV_DIR = Path("tools/dev")
DEV_SCRIPT_SUFFIXES = (".py", ".sh")

# `| [**security**](docs/security/README.md) | opt-in | … | 15 skills, [`docs/…`] |`
_README_FAMILY_ROW = re.compile(
    r"^\|\s*\[?\*\*(?P<family>[a-z-]+)\*\*\]?[^|]*\|.*?\|\s*(?P<count>\d+) skills?[,)]",
)
# `| **Triage** | *(Agentic Triage)* … | stable (…) | 35 |`
_MODES_GLANCE_ROW = re.compile(r"^\|\s*\*\*(?P<mode>[A-Za-z ]+?)\*\*\s*\|.*\|\s*(?P<count>\d+)\s*\|\s*$")
_BARE_TOTAL = re.compile(r"\b(?P<count>\d+) skills\b")


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def _key_counts(key: str) -> dict[str, int]:
    """Count live skills by a single-valued frontmatter key (``family``/``mode``)."""
    counts: dict[str, int] = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        m = re.search(rf"^{key}:\s*(\S+)\s*$", _frontmatter(skill_md), re.M)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def check_spec_index(errors: list[str]) -> None:
    if not SPECS_DIR.is_dir():
        return
    index_text = {p: p.read_text(encoding="utf-8") for p in SPEC_INDEXES if p.is_file()}
    for spec in sorted(SPECS_DIR.glob("*.md")):
        if spec.name in SPEC_INDEX_NAMES:
            continue
        for index, text in index_text.items():
            if f"({spec.name})" not in text:
                errors.append(f"{index}: spec '{spec.name}' is not listed — every spec belongs in both indexes")


def check_readme_family_counts(errors: list[str]) -> None:
    readme = Path("README.md")
    if not readme.is_file():
        return
    live = _key_counts("family")
    for lineno, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
        m = _README_FAMILY_ROW.match(line)
        if not m:
            continue
        family, declared = m.group("family"), int(m.group("count"))
        actual = live.get(family)
        if actual is None:
            continue  # a table row that is not a skill family
        if declared != actual:
            errors.append(
                f"README.md:{lineno}: family '{family}' says {declared} skills; "
                f"live family: frontmatter has {actual}"
            )


def check_modes_glance_counts(errors: list[str]) -> None:
    modes = Path("docs/modes.md")
    if not modes.is_file():
        return
    text = modes.read_text(encoding="utf-8")
    if "## Modes at a glance" not in text:
        return
    glance = text.split("## Modes at a glance", 1)[1].split("\n## ", 1)[0]
    live = _key_counts("mode")
    offset = text[: text.index("## Modes at a glance")].count("\n") + 1
    for lineno, line in enumerate(glance.splitlines(), offset):
        m = _MODES_GLANCE_ROW.match(line)
        if not m:
            continue
        mode, declared = m.group("mode").strip(), int(m.group("count"))
        actual = live.get(mode)
        if actual is None:
            # A mode with no skills (e.g. one deliberately switched off) must
            # declare 0 rather than be skipped.
            if declared != 0:
                errors.append(
                    f"docs/modes.md:{lineno}: mode '{mode}' says {declared} skills; "
                    f"no skill declares that mode"
                )
            continue
        if declared != actual:
            errors.append(
                f"docs/modes.md:{lineno}: mode '{mode}' says {declared} skills; "
                f"live mode: frontmatter has {actual}"
            )


def check_total_counts(errors: list[str], total: int) -> None:
    for path in TOTAL_COUNT_FILES:
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in _BARE_TOTAL.finditer(line):
                declared = int(m.group("count"))
                if declared != total:
                    errors.append(
                        f"{path}:{lineno}: says {declared} skills; the catalogue has {total}"
                    )


def check_dev_scripts_documented(errors: list[str]) -> None:
    readme = DEV_DIR / "README.md"
    if not DEV_DIR.is_dir() or not readme.is_file():
        return
    text = readme.read_text(encoding="utf-8")
    for script in sorted(DEV_DIR.iterdir()):
        if not script.is_file() or script.suffix not in DEV_SCRIPT_SUFFIXES:
            continue
        if script.name not in text:
            errors.append(
                f"{readme}: '{script.name}' is not named — every script in "
                f"{DEV_DIR}/ must be documented there"
            )


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print("check-doc-sync: run from the repository root", file=sys.stderr)
        return 2
    total = len(list(SKILLS_DIR.glob("*/SKILL.md")))
    errors: list[str] = []
    check_spec_index(errors)
    check_readme_family_counts(errors)
    check_modes_glance_counts(errors)
    check_total_counts(errors, total)
    check_dev_scripts_documented(errors)

    if errors:
        print("check-doc-sync: documentation is out of step with the tree.\n", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        print(
            f"\n{len(errors)} problem(s). These are counts and index entries a human has to "
            "remember to update; nothing breaks when they are wrong, which is why they drift.",
            file=sys.stderr,
        )
        return 1
    print(
        f"check-doc-sync: OK ({total} skills; spec indexes, declared counts, "
        "and dev-script docs agree)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
