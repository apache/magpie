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

"""The workspace static-check hooks must fire on every workspace member.

The hooks discover their members from the root ``pyproject.toml`` and run the
check across all of them, so the ``files:`` filter only decides when to start.
A filter that names only ``tools/src`` and ``tools/tests`` leaves the other
layouts unchecked on a pull request, which is how a formatting break reached
``main`` in #2199 (tracked in #2201).

The paths come from ``git ls-files`` filtered by the workspace members, so a
new member, or a new layout inside an existing one, cannot slip past silently.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

HOOKS = ("workspace-ruff-check", "workspace-ruff-format", "workspace-ty")

# Markdown-only changes under the members still skip the static checks on
# purpose; widening the filter must not start running them.
MARKDOWN_ONLY_PATH = "plugins/magpie-setup/skills/setup/SKILL.md"


def files_pattern(hook_id: str) -> str:
    text = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    block = text.split(f"- id: {hook_id}\n", 1)[1].split("pass_filenames:", 1)[0]
    match = re.search(r"files: (.+)", block)
    assert match is not None
    return match.group(1)


def workspace_members() -> tuple[str, ...]:
    root = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return tuple(root["tool"]["uv"]["workspace"]["members"])


def checked_paths() -> list[str]:
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    members = workspace_members()
    return [
        path
        for path in tracked
        if path.endswith((".py", "pyproject.toml"))
        and any(path == member or path.startswith(f"{member}/") for member in members)
    ]


def test_every_workspace_static_check_fires_on_every_member():
    paths = checked_paths()
    assert paths, "no tracked Python under a workspace member"
    for hook in HOOKS:
        pattern = files_pattern(hook)
        for path in paths:
            assert re.match(pattern, path), f"{hook} would skip {path}"
        assert re.match(pattern, "tools/dev/run-workspace-check.sh"), hook


def test_markdown_only_changes_skip_the_static_checks():
    for hook in HOOKS:
        assert not re.match(files_pattern(hook), MARKDOWN_ONLY_PATH), hook
