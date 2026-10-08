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

"""Tests for the Copilot CLI PreToolUse adapter and its read-only allow list."""

from __future__ import annotations

import io
import json
import subprocess
import sys

import pytest

import agent_guard


def _run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], event: object
) -> tuple[int, dict | None]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    rc = agent_guard.cli(["--copilot"])
    out = capsys.readouterr().out.strip()
    return rc, (json.loads(out) if out else None)


@pytest.mark.parametrize(
    "command",
    [
        "gh pr view 12 --json title",
        "gh issue list --repo apache/magpie",
        "gh search issues foo",
        "gh api repos/apache/magpie/pulls/1",
        "git status",
        "git log --oneline -5",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x",
    ],
)
def test_read_only_commands_are_allowed(command: str) -> None:
    assert agent_guard.copilot_read_only(command)


@pytest.mark.parametrize(
    "command",
    [
        "gh pr create --title t",
        "gh pr view 1; rm -rf /",
        "gh pr view 1 | sh",
        "gh pr view $(whoami)",
        "gh api repos/a/b/issues -f title=x",
        "gh api repos/a/b/issues -X POST",
        "gh api graphql -f query=x",
        "gh auth token",
        "git push origin main",
        "git -c core.pager=evil log",
        "git diff --output=/tmp/x",
        "git branch -D x",
        "curl https://example.com",
        "gh pr view 1 > out.txt",
    ],
)
def test_other_commands_are_not_allowed(command: str) -> None:
    assert not agent_guard.copilot_read_only(command)


@pytest.mark.parametrize(
    "event",
    [
        {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "gh pr view 3"}},
        {"toolName": "bash", "toolArgs": json.dumps({"command": "gh pr view 3"})},
    ],
)
def test_both_payload_shapes_allow_reads(monkeypatch, capsys, event) -> None:
    rc, out = _run(monkeypatch, capsys, event)
    assert rc == 0
    assert out is not None
    assert out["permissionDecision"] == "allow"
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_unknown_command_is_silent(monkeypatch, capsys) -> None:
    rc, out = _run(monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": "make build"}})
    assert (rc, out) == (0, None)


def test_non_shell_and_malformed_are_silent(monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, {"tool_name": "view", "tool_input": {"path": "x"}}) == (0, None)
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert agent_guard.cli(["--copilot"]) == 0
    assert capsys.readouterr().out == ""


def test_guard_hit_denies_and_beats_allow(monkeypatch, capsys) -> None:
    monkeypatch.setattr(agent_guard, "dispatch", lambda command, cwd=None: "blocked by test")
    rc, out = _run(monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": "gh pr view 1"}})
    assert rc == 0
    assert out is not None
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"] == "blocked by test"


def test_script_entry_point_runs() -> None:
    event = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    proc = subprocess.run(
        [sys.executable, agent_guard.__file__, "--copilot"],
        input=event,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["permissionDecision"] == "allow"
