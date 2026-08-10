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
"""Print a human-readable index of skills in this repository.

Walks ``.claude/skills/*/SKILL.md`` (relative to the script's own
location), parses the YAML frontmatter, and prints each skill's
name plus the first sentence of its ``description``, grouped by
the family prefix derived from the directory name
(e.g. ``security-issue-triage`` → family ``security``).

The output is generated on every run from the live filesystem, so
it never goes stale: adding a skill, renaming one, or rewriting a
description is reflected immediately.

Usage::

    python3 .claude/skills/magpie-list-skills/scripts/list_skills.py
    python3 .claude/skills/magpie-list-skills/scripts/list_skills.py --verbose
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

# Two-token family prefixes that should not be split on the first hyphen.
# Add to this list when a new multi-token family appears.
KNOWN_TWO_TOKEN_FAMILIES: tuple[str, ...] = ("pr-management",)


def find_skills_dir(start: Path) -> Path:
    """Resolve the framework ``skills/`` directory from the script's location."""
    # Script lives at skills/list-skills/scripts/list_skills.py;
    # parents[2] is the skills/ root.
    return start.resolve().parents[2]


def family_for(skill_name: str) -> str:
    for prefix in KNOWN_TWO_TOKEN_FAMILIES:
        if skill_name == prefix or skill_name.startswith(f"{prefix}-"):
            return prefix
    head, _, _ = skill_name.partition("-")
    return head or skill_name


def first_sentence(text: str) -> str:
    """Return the first sentence of a description, single-line."""
    collapsed = " ".join(text.split())
    match = re.match(r"(.+?[.!?])(?:\s|$)", collapsed)
    return match.group(1) if match else collapsed


def load_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    raw = text[3:end].lstrip("\n")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def collect_skills(skills_dir: Path) -> list[tuple[str, str, str]]:
    """Return a list of ``(family, name, description)`` for each skill."""
    rows: list[tuple[str, str, str]] = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        meta = load_frontmatter(skill_md)
        desc = meta.get("description") or ""
        rows.append((family_for(name), name, first_sentence(str(desc))))
    return rows


def render(rows: list[tuple[str, str, str]], *, verbose: bool) -> str:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for family, name, desc in rows:
        grouped[family].append((name, desc))

    width = max((len(name) for _, name, _ in rows), default=0)
    lines: list[str] = []
    lines.append(f"Skills in this repository ({len(rows)} total)")
    lines.append("=" * 50)
    lines.append("")
    for family in sorted(grouped):
        entries = grouped[family]
        lines.append(f"{family}/  ({len(entries)})")
        for name, desc in entries:
            if verbose:
                lines.append(f"  {name}")
                lines.append(f"      {desc}")
            else:
                lines.append(f"  {name.ljust(width)}  {desc}")
        lines.append("")
    lines.append("Invoke a skill by typing /<skill-name>, or describe what you want to do.")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a human-readable index of skills.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Place description on its own indented line per skill.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skills_dir = find_skills_dir(Path(__file__))
    if not skills_dir.is_dir():
        print(f"error: skills directory not found at {skills_dir}", file=sys.stderr)
        return 1
    rows = collect_skills(skills_dir)
    if not rows:
        print(f"no skills found under {skills_dir}", file=sys.stderr)
        return 1
    print(render(rows, verbose=args.verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
