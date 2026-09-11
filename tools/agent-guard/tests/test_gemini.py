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

"""Tests for Gemini CLI's BeforeTool adapter.

Like the OpenCode and Kiro suites, these check the hook's transport and its
agreement with the harness-neutral guard core. Guard rule details remain in
test_guards.py and test_skill_guards.py.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import agent_guard
from agent_guard import ALLOW_EXIT, DENY_EXIT, cli, dispatch, gemini_main


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


def _event(command: str) -> dict:
    return {
        "hook_event_name": "BeforeTool",
        "cwd": ".",
        "tool_name": "run_shell_command",
        "tool_input": {"command": command},
    }


def test_cli_blocks_prohibited_trailer_without_executing_command(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    event = _event(f"git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'; touch '{marker}'")
    event["cwd"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, agent_guard.__file__, "--gemini"],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == DENY_EXIT
    assert "commit-trailer" in result.stderr
    assert result.stdout == ""
    assert not marker.exists()


def test_allowed_command_is_silent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _feed(monkeypatch, _event("git status"))
    assert cli(["--gemini"]) == ALLOW_EXIT
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "command, expected, reason",
    [
        ("git status --short", ALLOW_EXIT, ""),
        ("git commit --dry-run --no-verify -m hook-probe", DENY_EXIT, "agent-guard[no-verify]"),
    ],
)
def test_project_settings_hook_runs_from_a_checkout_path_with_spaces(
    tmp_path: Path, command: str, expected: int, reason: str
) -> None:
    repo_root = Path(agent_guard.__file__).resolve().parents[4]
    project = tmp_path / "checkout with spaces"
    project.symlink_to(repo_root, target_is_directory=True)
    settings = json.loads((project / ".gemini" / "settings.json").read_text())
    event = _event(command)
    event["cwd"] = str(project)
    hooks = [
        hook
        for group in settings["hooks"]["BeforeTool"]
        if re.search(group["matcher"], event["tool_name"])
        for hook in group["hooks"]
    ]
    assert len(hooks) == 1
    # Execute the registered command, never the proposed tool command.
    result = subprocess.run(
        hooks[0]["command"],
        shell=True,
        cwd=tmp_path,
        env={**os.environ, "GEMINI_PROJECT_DIR": str(project)},
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == expected
    assert result.stdout == ""
    if reason:
        assert reason in result.stderr
    else:
        assert result.stderr == ""


@pytest.mark.parametrize(
    "command, expected",
    [
        ("git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'", DENY_EXIT),
        ("git commit -m 'x' --no-verify", DENY_EXIT),
        ("git commit -m 'x\n\nGenerated-by: Gemini CLI'", ALLOW_EXIT),
        ("ls -la && echo hi", ALLOW_EXIT),
    ],
)
def test_decision_and_reason_match_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    expected: int,
) -> None:
    # The adapter preserves the core's decision and emits its reason on stderr.
    reason = dispatch(command, ".")
    assert (reason is not None) == (expected == DENY_EXIT)

    _feed(monkeypatch, _event(command))
    assert gemini_main() == expected
    gemini_output = capsys.readouterr()
    assert gemini_output.err == (reason + "\n" if reason else "")
    assert gemini_output.out == ""


@pytest.mark.parametrize("cwd_kind", ["workspace", "missing", "invalid"])
def test_git_checks_use_event_workspace(
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
        pytest.fail(f"Unexpected Git check: {args}")

    monkeypatch.setattr(agent_guard, "_run", fake_run)
    event = _event("git push --force-with-lease origin mybranch:mybranch")
    if cwd_kind == "workspace":
        event["cwd"] = str(tmp_path)
    elif cwd_kind == "missing":
        del event["cwd"]
    else:
        event["cwd"] = []
    _feed(monkeypatch, event)
    assert gemini_main() == DENY_EXIT
    assert seen == [str(tmp_path) if cwd_kind == "workspace" else None] * 3
    captured = capsys.readouterr()
    assert "empty-rebase" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "payload",
    [
        "not JSON",
        "[]",
        "null",
        json.dumps({"tool_name": "read_file", "tool_input": {"file_path": "/synthetic"}}),
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit --no-verify"}}),
        json.dumps({"tool_name": "run_shell_command"}),
        json.dumps({"tool_name": "run_shell_command", "tool_input": []}),
        json.dumps({"tool_name": "run_shell_command", "tool_input": {}}),
        json.dumps({"tool_name": "run_shell_command", "tool_input": {"command": None}}),
        json.dumps({"tool_name": "run_shell_command", "tool_input": {"command": 42}}),
    ],
)
def test_irrelevant_or_malformed_event_does_not_dispatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], payload: str
) -> None:
    def unexpected_dispatch(*args: object) -> None:
        pytest.fail("Malformed or non-shell event reached the guard")

    monkeypatch.setattr(agent_guard, "dispatch", unexpected_dispatch)
    _feed(monkeypatch, payload)
    assert gemini_main() == ALLOW_EXIT
    assert capsys.readouterr() == ("", "")
