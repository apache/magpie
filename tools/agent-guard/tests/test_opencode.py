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

"""Tests for the OpenCode adapter entry point.

The point of the OpenCode integration is that it enforces the *same* guard
decisions as the Claude Code hook by sharing :func:`agent_guard.dispatch`.
These tests drive the ``--opencode`` I/O shell and assert the exit-code
protocol the OpenCode plugin relies on (2 = deny, 0 = allow).
"""

from __future__ import annotations

import io
import json

import pytest

import agent_guard
from agent_guard import ALLOW_EXIT, DENY_EXIT, cli, opencode_main


def _feed(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_denied_command_exits_deny_with_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    # A Co-Authored-By trailer is one of the bundled deny rules.
    _feed(monkeypatch, {"command": "git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'"})
    rc = opencode_main()
    out = capsys.readouterr().out
    assert rc == DENY_EXIT
    assert "commit-trailer" in out


def test_allowed_command_exits_allow_silently(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _feed(monkeypatch, {"command": "git status"})
    rc = opencode_main()
    assert rc == ALLOW_EXIT
    assert capsys.readouterr().out == ""


def test_non_git_gh_command_is_fast_path_allow(monkeypatch: pytest.MonkeyPatch):
    _feed(monkeypatch, {"command": "ls -la && echo hi"})
    assert opencode_main() == ALLOW_EXIT


def test_malformed_stdin_fails_open(monkeypatch: pytest.MonkeyPatch):
    _feed(monkeypatch, "not json {{{")
    assert opencode_main() == ALLOW_EXIT


def test_non_object_event_fails_open(monkeypatch: pytest.MonkeyPatch):
    _feed(monkeypatch, ["a", "list"])
    assert opencode_main() == ALLOW_EXIT


def test_missing_command_key_allows(monkeypatch: pytest.MonkeyPatch):
    _feed(monkeypatch, {"cwd": "/tmp"})
    assert opencode_main() == ALLOW_EXIT


def test_decision_matches_claude_dispatch(monkeypatch: pytest.MonkeyPatch):
    # The OpenCode adapter must deny exactly what dispatch() denies — same core.
    command = "git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'"
    _feed(monkeypatch, {"command": command})
    opencode_denies = opencode_main() == DENY_EXIT
    dispatch_denies = agent_guard.dispatch(command) is not None
    assert opencode_denies is dispatch_denies is True


def test_cli_routes_opencode_flag(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    _feed(monkeypatch, {"command": "git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'"})
    rc = cli(["--opencode"])
    assert rc == DENY_EXIT
    assert "agent-guard" in capsys.readouterr().out


def test_cli_no_args_routes_claude(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    # No flag → the Claude PreToolUse shape; a benign event is allowed silently.
    _feed(monkeypatch, {"tool_name": "Bash", "tool_input": {"command": "git status"}})
    rc = cli([])
    assert rc == 0
    assert capsys.readouterr().out == ""
