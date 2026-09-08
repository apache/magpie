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

It also checks that every declared member's tests actually run. The CI
pytest matrix and the workspace pytest sweep are both driven by the
presence of a `[tool.pytest.ini_options]` section, so a project can carry
a full `tests/` directory and still never be executed by anything — the
job simply is not emitted, and nobody sees a failure because nobody sees
a run. Three ways that goes wrong, all reported here:

  * tests on disk, no `[tool.pytest.ini_options]` — the tests never run;
  * `[tool.pytest.ini_options]`, no tests on disk — the CI job runs and
    collects nothing, so a green tick proves nothing;
  * neither — the project has no tests at all.

A project that genuinely should not be tested declares it, rather than
being silently absent:

    [tool.magpie.checks]
    skip = ["pytest"]

which is the same opt-out `tools/dev/run-workspace-check.sh` and the CI
matrix already honour.

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
        sys.stderr.write("error: root pyproject.toml has no [tool.uv.workspace] members\n")
        sys.exit(2)


def has_test_files(member: Path) -> bool:
    """True when the member carries at least one pytest-discoverable file.

    Scans for both naming conventions and ignores anything inside a virtual
    environment or an installed package, which would otherwise make a member
    with no tests of its own look tested.
    """
    for pattern in ("test_*.py", "*_test.py"):
        for found in member.rglob(pattern):
            parts = set(found.parts)
            if ".venv" in parts or "site-packages" in parts or "node_modules" in parts:
                continue
            return True
    return False


def check_tests_run(member_dirs: list[Path]) -> list[str]:
    """Report members whose tests do not actually execute anywhere."""
    problems: list[str] = []
    for member in member_dirs:
        rel = member.relative_to(ROOT)
        with (member / "pyproject.toml").open("rb") as f:
            tool = tomllib.load(f).get("tool", {})
        if "pytest" in tool.get("magpie", {}).get("checks", {}).get("skip", []):
            continue  # deliberate, declared opt-out
        configured = "ini_options" in tool.get("pytest", {})
        present = has_test_files(member)
        if present and not configured:
            problems.append(
                f"{rel}: has test files but no [tool.pytest.ini_options] — the CI "
                f"matrix and the workspace pytest sweep are both driven by that "
                f"section, so these tests never run"
            )
        elif configured and not present:
            problems.append(
                f"{rel}: declares [tool.pytest.ini_options] but has no test files — "
                f"the CI job runs and collects nothing, so its green tick proves nothing"
            )
        elif not present and not configured:
            problems.append(
                f"{rel}: has no tests. Add them, or declare the exemption with "
                f'[tool.magpie.checks] skip = ["pytest"]'
            )
    return problems


def main() -> int:
    member_dirs = find_member_dirs()
    declared = read_workspace_members()
    found_paths = {str(p.relative_to(ROOT)) for p in member_dirs}

    missing = sorted(found_paths - declared)
    stale = sorted(declared - found_paths)
    # Only meaningful for members that are actually declared; an undeclared
    # one is already reported above and its test wiring is moot until it is.
    untested = check_tests_run([p for p in member_dirs if str(p.relative_to(ROOT)) in declared])

    if not missing and not stale and not untested:
        return 0

    out = sys.stderr.write
    out("error: workspace members are not wired the way CI assumes\n")
    out("\n")
    if missing:
        out("Found `tools/.../pyproject.toml` that is NOT in `[tool.uv.workspace] members`:\n")
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
        out("Workspace members list references paths that no longer have a pyproject.toml on disk:\n")
        for p in stale:
            out(f"  - {p!r}\n")
        out("\n")
        out("Remove each stale entry from the root pyproject.toml.\n\n")
    if untested:
        out("Workspace members whose tests do not run:\n")
        for problem in untested:
            out(f"  ! {problem}\n")
        out("\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
