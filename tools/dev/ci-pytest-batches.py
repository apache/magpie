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
as `tools/dev/run-workspace-check.sh`. On a pull request only the members whose
Python or `tests/` files changed are picked, unless a shared build input changed;
on any other event every member is.

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
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

SOLO_MAX = 6
MAX_BATCHES = 8

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


def member_changed(path: str, changed: list[str]) -> bool:
    """A `.py` file anywhere under the member, or any file under its `tests/`."""
    prefix, tests = path + "/", path + "/tests/"
    return any(c.startswith(prefix) and (c.endswith(".py") or c.startswith(tests)) for c in changed)


def select(root: Path, changed: list[str] | None) -> list[str]:
    with (root / "pyproject.toml").open("rb") as f:
        paths = tomllib.load(f)["tool"]["uv"]["workspace"]["members"]
    run_all = changed is None or any(c in GLOBAL for c in changed)
    picked = [p for p in paths if has_pytest(root, p) and (run_all or member_changed(p, changed or []))]
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
    args = parser.parse_args(argv)
    changed = None
    if args.changed_file:
        changed = [
            line.strip()
            for line in args.changed_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    paths = select(args.root, changed)
    out = batches(paths, {p: weight(args.root, p) for p in paths})
    for batch in out:
        batch["packages"] = " ".join(package(args.root, p) for p in batch["paths"].split())
    json.dump(out, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
