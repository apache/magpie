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
"""Pick the workspace members the `tests` workflow runs, and group them into jobs.

A member gets pytest when it has a `[tool.pytest.ini_options]` section and does
not opt out with `[tool.magpie.checks] skip = [..., "pytest"]` — the same rule
as `tools/dev/run-workspace-check.sh`. On a pull request only the members with a
changed file other than Markdown (directly or through a symlinked source) are
picked, together with every member that depends on one of them, unless
a shared build input changed; on any other event every member is.

Most of a pytest job is setup (checkout, uv, a workspace sync), so the picked
members are grouped:

* up to `SOLO_MAX` members: one job each, named after the member, so a typical
  pull request keeps one check per project;
* more: at most `MAX_BATCHES` jobs, balanced by the size of each member's tests
  (heaviest first onto the lightest job), each running its members one by one.

Prints a JSON array of `{"key", "name", "paths", "packages"}` for the workflow's
matrix (`paths` and `packages` space-separated, in the same order; `packages` are
the members' project names, so a job syncs only what its members declare).
`--changed-file` names a file listing the changed paths; omit it for a full run.
`--paths` prints the picked member paths one per line instead, for the local
`workspace-pytest` hook, so a commit runs the same members a pull request would.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path

SOLO_MAX = 6
MAX_BATCHES = 8

#: The shared toolchain every member's `dev` group lists; not a dependency to follow.
TOOLCHAIN = "magpie-dev"

# A change to any of these can affect every member's tests.
GLOBAL = frozenset(
    {
        "pyproject.toml",
        "uv.lock",
        "tools/dev/run-workspace-check.sh",
        "tools/dev/ci-pytest-batches.py",
        ".github/workflows/tests.yml",
    }
)


def has_pytest(root: Path, path: str) -> bool:
    with (root / path / "pyproject.toml").open("rb") as f:
        tool = tomllib.load(f).get("tool", {})
    if "ini_options" not in tool.get("pytest", {}):
        return False
    return "pytest" not in tool.get("magpie", {}).get("checks", {}).get("skip", [])


def find_linked_sources(root: Path, path: str) -> list[str]:
    """Repo-relative targets of the directory symlinks under a member.

    A member such as `tools/setup-preflight` tests code that lives elsewhere in
    the tree through a `src/` symlink; a change at the target is a change to
    the member.
    """
    resolved_root = root.resolve()
    linked = []
    for current, dirs, _ in os.walk(root / path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for name in dirs:
            entry = Path(current) / name
            if not entry.is_symlink():
                continue
            try:
                linked.append(entry.resolve().relative_to(resolved_root).as_posix())
            except ValueError:
                continue
    return sorted(linked)


def member_changed(path: str, changed: list[str], linked: list[str] | None = None) -> bool:
    """Any file under the member or its linked sources, but Markdown and plugin manifests.

    Not only Python: tests also run shell scripts and read data files beside
    the code (`tools/agent-isolation` tests `agent-iso.sh`). A dev-version bump
    rewrites every `.claude-plugin/plugin.json`, which no member's tests read;
    the `check-family-plugins` hook checks them.
    """
    prefixes = tuple(p + "/" for p in [path, *(linked or [])])
    return any(
        c.startswith(prefixes) and not c.endswith(".md") and "/.claude-plugin/" not in c for c in changed
    )


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def find_dependents(root: Path, paths: list[str]) -> dict[str, set[str]]:
    """Map each member to the members that depend on it, at runtime or in a dependency group.

    Groups count because a test-only dependency is still exercised by the
    dependent's tests (`release-management` tests run `release-config`).
    `TOOLCHAIN` does not: every member lists it in its `dev` group for the shared
    toolchain, and following it would turn any change under `tools/dev` into a
    full run.
    """
    pyprojects = {}
    for path in paths:
        with (root / path / "pyproject.toml").open("rb") as f:
            pyprojects[path] = tomllib.load(f)
    by_name = {
        _normalize(data["project"]["name"]): path
        for path, data in pyprojects.items()
        if "name" in data.get("project", {})
    }
    by_name.pop(TOOLCHAIN, None)
    dependents: dict[str, set[str]] = {path: set() for path in paths}
    for path, data in pyprojects.items():
        project = data.get("project", {})
        requirements = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            requirements += extra
        for group in data.get("dependency-groups", {}).values():
            requirements += [r for r in group if isinstance(r, str)]
        for requirement in requirements:
            target = by_name.get(_normalize(re.split(r"[\s\[<>=!~;@(]", requirement, maxsplit=1)[0]))
            if target is not None and target != path:
                dependents[target].add(path)
    return dependents


def select(root: Path, changed: list[str] | None) -> list[str]:
    """The members to test: those a change touches, plus every member depending on them."""
    with (root / "pyproject.toml").open("rb") as f:
        paths = tomllib.load(f)["tool"]["uv"]["workspace"]["members"]
    if changed is None or any(c in GLOBAL for c in changed):
        affected = set(paths)
    else:
        affected = {p for p in paths if member_changed(p, changed, find_linked_sources(root, p))}
        dependents = find_dependents(root, paths)
        pending = list(affected)
        while pending:
            for dependent in dependents[pending.pop()] - affected:
                affected.add(dependent)
                pending.append(dependent)
    picked = [p for p in paths if p in affected and has_pytest(root, p)]
    return sorted(picked, key=lambda p: p.rsplit("/", 1)[-1])


def weight(root: Path, path: str) -> int:
    """Lines of test code: a cheap, deterministic stand-in for how long a member's tests take."""
    tests = root / path / "tests"
    if not tests.is_dir():
        return 1
    return max(1, sum(len(f.read_bytes().splitlines()) for f in sorted(tests.rglob("*.py"))))


def package(root: Path, path: str) -> str:
    with (root / path / "pyproject.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["name"])


def _name(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def batches(paths: list[str], weights: dict[str, int]) -> list[dict[str, str]]:
    if len(paths) <= SOLO_MAX:
        return [{"key": _name(p), "name": _name(p), "paths": p} for p in paths]
    count = min(MAX_BATCHES, len(paths))
    groups: list[list[str]] = [[] for _ in range(count)]
    loads = [0] * count
    # Longest-processing-time first; ties broken by name so the split is stable.
    for path in sorted(paths, key=lambda p: (-weights[p], _name(p))):
        slot = min(range(count), key=lambda i: (loads[i], i))
        groups[slot].append(path)
        loads[slot] += weights[path]
    out = []
    for index, group in enumerate(groups, start=1):
        names = sorted(_name(p) for p in group)
        shown = ", ".join(names[:3]) + (f", +{len(names) - 3}" if len(names) > 3 else "")
        out.append(
            {"key": f"batch-{index}", "name": f"{index}/{count}: {shown}", "paths": " ".join(sorted(group))}
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--changed-file", type=Path, help="file listing a pull request's changed paths")
    parser.add_argument("--paths", action="store_true", help="print the picked member paths, one per line")
    args = parser.parse_args(argv)
    changed = None
    if args.changed_file:
        changed = [
            line.strip()
            for line in args.changed_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    paths = select(args.root, changed)
    if args.paths:
        for path in paths:
            print(path)
        return 0
    out = batches(paths, {p: weight(args.root, p) for p in paths})
    for batch in out:
        batch["packages"] = " ".join(package(args.root, p) for p in batch["paths"].split())
    json.dump(out, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
