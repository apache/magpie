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
"""Lint the framework's self-adoption skill symlinks. Two rules:

1. **No cycles** — a symlink must not resolve to its own directory or an
   ancestor (that traps recursive `**/SKILL.md` scanners in looped paths).
2. **Relay correctness** — a `magpie-<skill>` link under `.agents/skills/`
   (canonical) points into `../../skills/`; the same link under any other
   agent dir relays through `../../.agents/skills/magpie-<skill>`.

Dangling links are skipped. Full rationale + examples: `README.md`.

Run as the `symlink-lint` prek hook, or directly:
`python3 tools/symlink-lint/src/symlink_lint/__init__.py`. Exit 0 if clean,
1 otherwise (offenders on stderr).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Directories pruned from the scan (VCS metadata, virtualenvs, vendored
# deps, build/test caches, gitignored snapshot).
PRUNE_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        ".apache-magpie",
        ".apache-magpie-sources",
        ".mypy_cache",
        ".pytest_cache",
        ".hatch",
    }
)


def repo_root() -> Path:
    """The repo root — `git rev-parse --show-toplevel`, else CWD."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return Path.cwd()
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())
    return Path.cwd()


def find_cyclic_symlinks(root: Path, prune: frozenset[str] = PRUNE_DIR_NAMES) -> list[tuple[Path, Path]]:
    """Return `(link, resolved_target)` for every symlink under `root` that
    resolves to its own directory or an ancestor. Dangling / unresolvable
    links are skipped; directories in `prune` are not descended into."""
    violations: list[tuple[Path, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in prune]
        # os.walk never follows a symlink (followlinks=False), so a cyclic
        # link cannot trap the walk; symlinks show up in dirnames + filenames.
        for name in (*dirnames, *filenames):
            link = Path(dirpath) / name
            if not link.is_symlink():
                continue
            try:
                target = link.resolve(strict=True)
            except (OSError, RuntimeError):
                continue  # dangling / unresolvable -> out of scope
            link_dir = link.parent.resolve()
            if target == link_dir or target in link_dir.parents:
                violations.append((link, target))
    return sorted(violations)


def find_misdirected_relays(
    root: Path, prune: frozenset[str] = PRUNE_DIR_NAMES
) -> list[tuple[Path, str, str]]:
    """Return `(link, actual_target, expected_target)` for every
    `magpie-<skill>` symlink under an `<agent>/skills/` directory whose
    one-hop target breaks the one-directional convention: canonical links
    under `.agents/skills/` point into `../../skills/`; every other agent
    dir's relay points at `../../.agents/skills/magpie-<skill>`."""
    problems: list[tuple[Path, str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in prune]
        if os.path.basename(dirpath) != "skills":
            continue
        agent = os.path.basename(os.path.dirname(dirpath))
        for name in (*dirnames, *filenames):
            if not name.startswith("magpie-"):
                continue
            link = Path(dirpath) / name
            if not link.is_symlink():
                continue
            if agent == ".agents":
                expected = f"../../skills/{name.removeprefix('magpie-')}"
            else:
                expected = f"../../.agents/skills/{name}"
            actual = os.readlink(link)
            if actual != expected:
                problems.append((link, actual, expected))
    return sorted(problems)


def _rel(link: Path, root: Path) -> Path:
    try:
        return link.relative_to(root)
    except ValueError:
        return link


def main() -> int:
    root = repo_root()
    cycles = find_cyclic_symlinks(root)
    relays = find_misdirected_relays(root)
    if not cycles and not relays:
        return 0

    out = sys.stderr.write
    if cycles:
        out("error: self-referential / cyclic symlink(s):\n")
        for link, target in cycles:
            out(f"  {_rel(link, root)} -> {os.readlink(link)}  (resolves to {target})\n")
    if relays:
        out("error: misdirected skill relay symlink(s):\n")
        for link, actual, expected in relays:
            out(f"  {_rel(link, root)} -> {actual}  (expected {expected})\n")
    out("\nSee tools/symlink-lint/README.md and skills/setup/agents.md.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
