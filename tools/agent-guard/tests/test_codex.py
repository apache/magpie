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

"""Codex native PreToolUse contract: block guards, defer ordinary approvals."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

import agent_guard


def event(command="git status", **extra):
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, **extra}


def run(monkeypatch, capsys, payload):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    rc = agent_guard.cli(["--codex"])
    return rc, capsys.readouterr()


def test_deny_uses_native_schema_and_passes_cwd(monkeypatch, capsys):
    calls = []

    def guard(command, cwd=None):
        calls.append((command, cwd))
        return "test denial"

    monkeypatch.setattr(agent_guard, "dispatch", guard)
    rc, out = run(monkeypatch, capsys, event("git push", cwd="/tmp/worktree"))
    assert calls == [("git push", "/tmp/worktree")]
    assert rc == 0
    assert json.loads(out.out) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "test denial",
        }
    }
    assert out.err == ""


@pytest.mark.parametrize(
    "payload",
    [
        event(),
        event(None),
        event([]),
        [],
        None,
        event(tool_name="apply_patch"),
        event(hook_event_name="PostToolUse"),
        {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": "bad"},
    ],
)
def test_ordinary_and_unhandled_events_never_auto_approve(monkeypatch, capsys, payload):
    rc, out = run(monkeypatch, capsys, payload)
    assert (rc, out.out, out.err) == (0, "", "")


def test_invalid_json_is_silent(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("invalid"))
    assert agent_guard.cli(["--codex"]) == 0
    assert capsys.readouterr().out == ""


def test_real_guard_blocks_before_side_effect(tmp_path):
    marker = tmp_path / "should-not-exist"
    command = f"git commit --no-verify -m test; touch {marker}"
    proc = subprocess.run(
        [sys.executable, agent_guard.__file__, "--codex"],
        input=json.dumps(event(command, cwd=str(Path(__file__).resolve().parents[3]))),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not marker.exists()


def test_committed_registration_runs_from_a_subdirectory():
    import tomllib

    root = Path(__file__).resolve().parents[3]
    config = tomllib.loads((root / ".codex/config.toml").read_text())
    command = config["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    result = subprocess.run(
        command,
        shell=True,
        cwd=root / "docs",
        input=json.dumps(event("git commit --no-verify -m test", cwd=str(root))),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_committed_hook_works_in_a_snapshot_adopter(tmp_path):
    import shutil
    import tomllib

    root = Path(__file__).resolve().parents[3]
    command = tomllib.loads((root / ".codex/config.toml").read_text())["hooks"]["PreToolUse"][0]["hooks"][0][
        "command"
    ]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    target = tmp_path / ".apache-magpie/tools/agent-guard/src/agent_guard"
    shutil.copytree(Path(agent_guard.__file__).parent, target, ignore=shutil.ignore_patterns("__pycache__"))
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    result = subprocess.run(
        command,
        shell=True,
        cwd=subdir,
        input=json.dumps(event("git commit --no-verify -m test", cwd=str(tmp_path))),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
