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

"""Checks for the Magpie Goose plugin and the ``agent-iso goose`` launch.

The repository root is the Goose plugin: ``.goose-plugin/plugin.json`` names
the skill directories (Goose's installer does not copy the root ``skills/``
symlinks) and ``hooks/hooks.json`` registers the PreToolUse hook. ``agent-iso
goose`` hands Goose to the installed plugin's launcher, which runs it in the
sandbox runtime, and refuses to start it unsandboxed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "agent-isolation" / "agent-iso.sh"
BASH = shutil.which("bash") or "/bin/bash"


def test_goose_manifest_lists_every_family_skill_directory() -> None:
    manifest = json.loads((REPO / ".goose-plugin" / "plugin.json").read_text())
    listed = sorted(manifest["skills"]["paths"])
    on_disk = sorted(
        f"./{p.relative_to(REPO).as_posix()}"
        for p in REPO.glob("plugins/*/skills")
        if p.is_dir()
    )
    assert listed == on_disk, (
        "a family's skills/ is missing from .goose-plugin/plugin.json (or listed but gone)"
    )
    # exclusive: Goose's copy drops the root skills/ symlinks, so they must not be read.
    assert manifest["skills"]["exclusive"] is True


def test_goose_hook_command_points_at_an_existing_file() -> None:
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text())
    commands = [
        hook["command"]
        for rule in hooks["hooks"]["PreToolUse"]
        for hook in rule["hooks"]
    ]
    assert commands, "no PreToolUse hook registered"
    for command in commands:
        match = re.search(r'\$\{PLUGIN_ROOT\}/([^"\s]+)', command)
        assert match, (
            f"hook command does not resolve a file under ${{PLUGIN_ROOT}}: {command}"
        )
        assert (REPO / match[1]).is_file(), f"hook target missing: {match[1]}"
    # The hook is a security control: a crash must refuse the call, not allow it.
    assert all(
        hook.get("on_failure") == "block"
        for rule in hooks["hooks"]["PreToolUse"]
        for hook in rule["hooks"]
    )


def _fake_goose(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "goose"
    fake.write_text('#!/bin/sh\necho "RAN-UNSANDBOXED"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _env(tmp_path: Path, bin_dir: Path, plugin: Path) -> dict[str, str]:
    return {
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(tmp_path / "home"),
        "USER": "testuser",
        "SHELL": "/bin/sh",
        "MAGPIE_GOOSE_PLUGIN": str(plugin),
    }


def test_agent_iso_goose_refuses_without_the_plugin_launcher(tmp_path: Path) -> None:
    bin_dir = _fake_goose(tmp_path)
    empty = tmp_path / "no-plugin"
    empty.mkdir()
    res = subprocess.run(
        [BASH, str(SCRIPT), "agent-iso", "goose", "session"],
        env=_env(tmp_path, bin_dir, empty),
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 127
    assert "Not starting Goose unsandboxed" in res.stderr
    assert "RAN-UNSANDBOXED" not in res.stdout


def test_agent_iso_goose_hands_goose_to_the_plugin_launcher(tmp_path: Path) -> None:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    bin_dir = _fake_goose(tmp_path)
    plugin = tmp_path / "plugin"
    launch = plugin / "tools" / "agent-isolation" / "goose" / "launch.ts"
    launch.parent.mkdir(parents=True)
    # Plain JavaScript is valid TypeScript, so any Node version runs it.
    launch.write_text('console.log("LAUNCH:" + process.argv.slice(2).join("|"));\n')
    res = subprocess.run(
        [BASH, str(SCRIPT), "agent-iso", "goose", "session", "--name", "x"],
        env=_env(tmp_path, bin_dir, plugin),
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    assert "RAN-UNSANDBOXED" not in res.stdout
    assert f"LAUNCH:{bin_dir / 'goose'}|session|--name|x" in res.stdout
