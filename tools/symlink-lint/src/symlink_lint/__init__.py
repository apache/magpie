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
"""Lint the framework's self-adoption skill symlinks. Two working-tree rules:

1. **No cycles** — a symlink must not resolve to its own directory or an
   ancestor (that traps recursive `**/SKILL.md` scanners in looped paths).
2. **Relay correctness** — a `magpie-<skill>` link under `.agents/skills/`
   (canonical) points into `../../skills/`; the same link under any other
   agent dir relays through `../../.agents/skills/magpie-<skill>`.

Plus one **release-archive** rule, run with `--archive`:

3. **Archive is extractor-safe** — build the source archive exactly as the
   release does (`git archive --worktree-attributes` of the staged tree,
   honouring `.gitattributes` `export-ignore`), then reject any symlink in
   it that is *dangling* (target absent — orphaned by an `export-ignore`)
   or a *chain* (target is itself a symlink — a safe extractor such as
   ATR's upload validator rejects it as "target outside extraction
   directory"). This is what breaks an RC upload; catching it here fails
   the commit before an RC is ever cut. See `README.md`.

Dangling links are skipped by rules 1-2. Full rationale + examples:
`README.md`.

Run as the `symlink-lint` / `symlink-lint-archive` prek hooks, or directly:
`python3 tools/symlink-lint/src/symlink_lint/__init__.py [--archive]`.
Exit 0 if clean, 1 otherwise (offenders on stderr).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import tempfile
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


def find_archive_symlink_problems(root: Path) -> list[tuple[str, str, str]]:
    """Build the source archive the way the release does and return
    `(archive_path, target, kind)` for every symlink in it that a safe
    extractor rejects.

    The archive is `git archive --worktree-attributes` of the *staged* tree
    (`git write-tree`), so it reflects the change being committed and honours
    the working-tree `.gitattributes` `export-ignore` rules — identical to
    `release-build.md`/`release-rc-cut`. Two rejected kinds:

    - `dangling` — the link's target is not present in the archive (its real
      file was `export-ignore`d, orphaning the link).
    - `chain` — the link's target is itself a symlink; an extractor that
      refuses to follow a symlink-to-symlink reads the target as escaping the
      extraction directory (ATR's upload validator rejects this exact shape).

    Returns an empty list if `git` is unavailable or the tree cannot be
    written (nothing to assert against)."""
    try:
        tree = subprocess.run(
            ["git", "write-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if tree.returncode != 0 or not tree.stdout.strip():
        return []
    archived = subprocess.run(
        ["git", "archive", "--worktree-attributes", "--format=tar", tree.stdout.strip()],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if archived.returncode != 0:
        return []

    problems: list[tuple[str, str, str]] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "archive.tar"
        base.write_bytes(archived.stdout)
        with tarfile.open(base) as tar:
            members = tar.getmembers()
        # Map every archived path to its member; symlink targets are resolved
        # against this set, never the host filesystem, so the check reflects
        # only what the archive itself contains.
        by_path = {m.name: m for m in members}
        for member in members:
            if not member.issym():
                continue
            link_dir = os.path.dirname(member.name)
            target = os.path.normpath(os.path.join(link_dir, member.linkname))
            resolved = by_path.get(target)
            if resolved is None:
                problems.append((member.name, member.linkname, "dangling"))
            elif resolved.issym():
                problems.append((member.name, member.linkname, "chain"))
    return sorted(problems)


def _rel(link: Path, root: Path) -> Path:
    try:
        return link.relative_to(root)
    except ValueError:
        return link


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    archive_mode = "--archive" in args
    root = repo_root()

    if archive_mode:
        archive = find_archive_symlink_problems(root)
        if not archive:
            return 0
        out = sys.stderr.write
        out("error: release-archive symlink(s) a safe extractor rejects:\n")
        for arc_path, arc_target, kind in archive:
            hint = (
                "target export-ignored -> dangling in archive"
                if kind == "dangling"
                else "target is itself a symlink -> extractor sees it outside the archive"
            )
            out(f"  {arc_path} -> {arc_target}  ({kind}: {hint})\n")
        out(
            "\nThe source archive (git archive of the export tree) must contain only\n"
            "single-hop symlinks to real files. Fix .gitattributes export-ignore\n"
            "rules or the offending links. See tools/symlink-lint/README.md.\n"
        )
        return 1

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
