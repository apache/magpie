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

"""Tests for Antigravity's PreToolUse adapter.

Like the OpenCode and Kiro suites, these check the hook's transport and its
agreement with the harness-neutral guard core. Guard rule details remain in
test_guards.py and test_skill_guards.py. The event shape is the one Antigravity
CLI 1.3.6 sent to a probe hook.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import agent_guard

ALLOW = {"decision": "allow"}


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "MAGPIE_GUARD_OFF",
        "MAGPIE_GUARD_DIRS",
        "MAGPIE_ALLOW_COAUTHOR",
        "MAGPIE_ALLOW_EMPTY_PUSH",
        "MAGPIE_ALLOW_NO_VERIFY",
    ):
        monkeypatch.delenv(name, raising=False)


def _feed(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def _event(command: str, workspace: str = ".") -> dict:
    return {
        "conversationId": "synthetic",
        "modelName": "synthetic",
        "stepIdx": 2,
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": command, "WaitMsBeforeAsync": 5000, "toolSummary": "probe"},
        },
        "workspacePaths": [workspace],
    }


def _decision(capsys: pytest.CaptureFixture[str]) -> dict:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_cli_blocks_prohibited_trailer_without_executing_command(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    event = _event(f"git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'; touch '{marker}'", str(tmp_path))
    result = subprocess.run(
        [sys.executable, agent_guard.__file__, "--antigravity"],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )
    # Antigravity reads the decision from stdout; the exit code stays 0.
    assert result.returncode == agent_guard.ALLOW_EXIT
    decision = json.loads(result.stdout)
    assert decision["decision"] == "deny"
    assert "commit-trailer" in decision["reason"]
    assert not marker.exists()


@pytest.mark.parametrize(
    "command, reason",
    [
        ("git status --short", ""),
        ("git commit --dry-run --no-verify -m hook-probe", "agent-guard[no-verify]"),
    ],
)
def test_shipped_hook_command_runs_from_a_path_with_spaces(tmp_path: Path, command: str, reason: str) -> None:
    repo_root = Path(agent_guard.__file__).resolve().parents[4]
    hooks = json.loads((repo_root / "tools" / "agent-isolation" / "antigravity" / "hooks.json").read_text())
    (registered,) = [
        hook["command"]
        for config in hooks.values()
        for group in config["PreToolUse"]
        if group["matcher"] == "run_command"
        for hook in group["hooks"]
    ]
    # The template points at the staged plugin under $HOME; stand one up there.
    home = tmp_path / "home with spaces"
    plugin = home / ".gemini" / "config" / "plugins"
    plugin.mkdir(parents=True)
    (plugin / "magpie").symlink_to(repo_root, target_is_directory=True)
    hook_cwd = tmp_path / ".agents"
    hook_cwd.mkdir()
    # Execute the registered command through a shell, as Antigravity does, never the tool command.
    result = subprocess.run(
        registered,
        shell=True,
        cwd=hook_cwd,
        env={**os.environ, "HOME": str(home)},
        input=json.dumps(_event(command, str(tmp_path))),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == agent_guard.ALLOW_EXIT
    decision = json.loads(result.stdout)
    if reason:
        assert decision["decision"] == "deny"
        assert reason in decision["reason"]
    else:
        assert decision == ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'",
        "git commit -m 'x' --no-verify",
        "git commit -m 'x\n\nGenerated-by: Antigravity'",
        "ls -la && echo hi",
    ],
)
def test_decision_and_reason_match_dispatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    reason = agent_guard.dispatch(command, ".")
    _feed(monkeypatch, _event(command))
    assert agent_guard.antigravity_main() == agent_guard.ALLOW_EXIT
    expected = {"decision": "deny", "reason": reason} if reason else ALLOW
    assert _decision(capsys) == expected


@pytest.mark.parametrize("cwd_kind", ["command-cwd", "workspace", "missing", "invalid"])
def test_git_checks_use_command_cwd_then_workspace(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    cwd_kind: str,
) -> None:
    # Follow the bundled empty-rebase test: stub Git reads, never execute a push.
    seen = []

    def fake_run(args: list[str], cwd: str | None = None) -> str | None:
        seen.append(cwd)
        if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return "origin/main"
        if args[:2] == ["git", "merge-base"]:
            return "base1234"
        if args[:3] == ["git", "rev-list", "--count"]:
            return "0"
        return pytest.fail(f"Unexpected Git check: {args}")

    monkeypatch.setattr(agent_guard, "_run", fake_run)
    event = _event("git push --force-with-lease origin mybranch:mybranch", str(tmp_path / "workspace"))
    expected: str | None = str(tmp_path / "workspace")
    if cwd_kind == "command-cwd":
        event["toolCall"]["args"]["Cwd"] = str(tmp_path)
        expected = str(tmp_path)
    elif cwd_kind == "missing":
        del event["workspacePaths"]
        expected = None
    elif cwd_kind == "invalid":
        event["workspacePaths"] = [42]
        expected = None
    _feed(monkeypatch, event)
    assert agent_guard.antigravity_main() == agent_guard.ALLOW_EXIT
    assert seen == [expected] * 3
    decision = _decision(capsys)
    assert decision["decision"] == "deny"
    assert "empty-rebase" in decision["reason"]


@pytest.mark.parametrize(
    "payload",
    [
        "not JSON",
        "[]",
        "null",
        json.dumps({"toolCall": {"name": "view_file", "args": {"AbsolutePath": "/synthetic"}}}),
        json.dumps({"tool_name": "run_shell_command", "tool_input": {"command": "git commit --no-verify"}}),
        json.dumps({"toolCall": {"name": "run_command"}}),
        json.dumps({"toolCall": {"name": "run_command", "args": []}}),
        json.dumps({"toolCall": {"name": "run_command", "args": {}}}),
        json.dumps({"toolCall": {"name": "run_command", "args": {"CommandLine": None}}}),
        json.dumps({"toolCall": {"name": "run_command", "args": {"CommandLine": 42}}}),
    ],
)
def test_irrelevant_or_malformed_event_allows_without_dispatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], payload: str
) -> None:
    def unexpected_dispatch(*args: object) -> None:
        pytest.fail("Malformed or non-shell event reached the guard")

    monkeypatch.setattr(agent_guard, "dispatch", unexpected_dispatch)
    _feed(monkeypatch, payload)
    assert agent_guard.antigravity_main() == agent_guard.ALLOW_EXIT
    assert _decision(capsys) == ALLOW
