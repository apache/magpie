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
#
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Measure a skill's two budgets in any repository, with the standard library only.

For each ``SKILL.md`` given (or every ``SKILL.md`` under a directory given):

- **always-on**: what the harness lists for the skill in every session,
  ``name: description - when_to_use``, in characters / 4. This is the same
  estimate the Magpie repository's ``tools/dev/estimate-skill-tokens.py`` makes.
- **body**: the file after its frontmatter, with any Magpie pre-flight block
  left out, in characters / 4. The Magpie repository stamps a tokenizer count
  instead (``skill-token-count``), which differs by a few per cent; use that
  one there, and this one in a project without it.

It also fails when a ``SKILL.md`` has no frontmatter or no ``name``, the one
structural check every harness relies on.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CHARS_PER_TOKEN = 4
BODY_TARGET = 5000
ALWAYS_ON_TARGET = 200

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
_PREFLIGHT = re.compile(r"<!-- BEGIN MAGPIE PREFLIGHT.*?<!-- END MAGPIE PREFLIGHT -->\n?", re.S)


def scalar(frontmatter: str, key: str) -> str:
    """Read one frontmatter value, plain or block (``key: |`` / ``key: >-``)."""
    m = re.search(rf"^{key}:[ \t]*(\|[-+]?|>[-+]?)?[ \t]*(.*)$", frontmatter, re.M)
    if not m:
        return ""
    if not m.group(1):
        return m.group(2).strip().strip("'\"")
    body: list[str] = []
    for line in frontmatter[m.end() :].split("\n")[1:]:
        if line.strip() and not line[:1].isspace():
            break
        body.append(line)
    return "\n".join(body).strip()


def always_on_chars(frontmatter: str) -> int:
    """``name: description - when_to_use``: the three fields and their separators."""
    chars = len(scalar(frontmatter, "name")) + 2 + len(scalar(frontmatter, "description"))
    when_to_use = scalar(frontmatter, "when_to_use")
    if when_to_use:
        chars += 3 + len(when_to_use)
    return chars


def measure(path: Path) -> tuple[int, int, list[str]]:
    """Return (always-on tokens, body tokens, problems) for one SKILL.md."""
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER.match(text)
    if not m:
        return 0, len(text) // CHARS_PER_TOKEN, [f"{path}: no frontmatter"]
    problems = [] if scalar(m.group(1), "name") else [f"{path}: frontmatter has no name"]
    body = _PREFLIGHT.sub("", text[m.end() :])
    return always_on_chars(m.group(1)) // CHARS_PER_TOKEN, len(body) // CHARS_PER_TOKEN, problems


def skill_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files.extend(sorted(target.rglob("SKILL.md")))
        else:
            files.append(target)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("targets", nargs="+", type=Path, help="SKILL.md files, or directories to search")
    args = parser.parse_args(argv)

    problems: list[str] = []
    print(f"{'always-on':>9} {'body':>7}  skill")
    for path in skill_files(args.targets):
        always_on, body, found = measure(path)
        problems.extend(found)
        flags = []
        if always_on > ALWAYS_ON_TARGET:
            flags.append(f"always-on over {ALWAYS_ON_TARGET}")
        if body > BODY_TARGET:
            flags.append(f"body over {BODY_TARGET}")
        note = f"  ({', '.join(flags)})" if flags else ""
        print(f"{always_on:>9} {body:>7}  {path}{note}")
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
