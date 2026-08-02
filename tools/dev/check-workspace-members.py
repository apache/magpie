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
"""Validate that every directory containing a `pyproject.toml` under
`tools/` is registered as a uv-workspace member in the root
`pyproject.toml`'s `[tool.uv.workspace] members` list.

This is the safety net for the DRY refactor introduced by the
uv-workspace adoption: the workspace members list is the single
source of truth for which projects get pre-commit hooks + CI matrix
entries. A new `tools/<name>/pyproject.toml` that is *not* added to
the members list silently skips both surfaces — exactly the bug
this hook prevents.

Run as a prek hook on every pyproject.toml change. Exit code 0 if
the two sets agree; 1 otherwise, with a diff explaining what to add
or remove.

Scope: only `tools/*/pyproject.toml` and `tools/*/*/pyproject.toml`
(maxdepth-3). The root `pyproject.toml` and any deeper nested
pyprojects (e.g. inside `tests/` fixtures or vendored deps) are
excluded.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def find_member_dirs() -> list[Path]:
    """Discover every directory that contains its own `pyproject.toml`:
    top-level project directories, plus anything under `tools/` at depth
    2 or 3 below the repo root.

    Most members live under `tools/`, but not all — `ai-tutors/` carries
    the knowledge-base injector and its tests alongside the prompts it
    rewrites, so it is a member without being a tool. Scanning only
    `tools/` reported such a member as stale and pushed contributors to
    delete a correct entry."""
    found: list[Path] = []

    # Top-level project directories (excluding the repo root itself, which
    # is the workspace root rather than a member).
    for top in sorted(ROOT.iterdir()):
        if not top.is_dir() or top.name.startswith("."):
            continue
        if top.name == "tools":
            continue  # handled below, which also descends one level
        if (top / "pyproject.toml").is_file():
            found.append(top)

    tools = ROOT / "tools"
    if not tools.is_dir():
        return found
    for top in sorted(tools.iterdir()):
        if not top.is_dir():
            continue
        if (top / "pyproject.toml").is_file():
            found.append(top)
            # When a top-level tools/<name> is itself a project, do
            # NOT descend further — its `tests/` and `src/` are
            # internal layout, not nested members.
            continue
        for child in sorted(top.iterdir()):
            if not child.is_dir():
                continue
            if (child / "pyproject.toml").is_file():
                found.append(child)
    return found


def read_workspace_members() -> set[str]:
    with (ROOT / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    try:
        return set(data["tool"]["uv"]["workspace"]["members"])
    except KeyError:
        sys.stderr.write(
            "error: root pyproject.toml has no [tool.uv.workspace] members\n"
        )
        sys.exit(2)


def main() -> int:
    member_dirs = find_member_dirs()
    declared = read_workspace_members()
    found_paths = {str(p.relative_to(ROOT)) for p in member_dirs}

    missing = sorted(found_paths - declared)
    stale = sorted(declared - found_paths)

    if not missing and not stale:
        return 0

    out = sys.stderr.write
    out("error: uv workspace members list drifts from on-disk pyprojects\n")
    out("\n")
    if missing:
        out(
            "Found `tools/.../pyproject.toml` that is NOT in "
            "`[tool.uv.workspace] members`:\n"
        )
        for p in missing:
            out(f"  + {p!r}\n")
        out("\n")
        out(
            "Add each to the `members = [...]` array in the root "
            "pyproject.toml — without this, the project will silently "
            "be skipped by the workspace-* prek hooks and the CI "
            "pytest matrix.\n\n"
        )
    if stale:
        out(
            "Workspace members list references paths that no longer "
            "have a pyproject.toml on disk:\n"
        )
        for p in stale:
            out(f"  - {p!r}\n")
        out("\n")
        out("Remove each stale entry from the root pyproject.toml.\n\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
