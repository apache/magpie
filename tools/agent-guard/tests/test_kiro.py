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

"""Tests for the Kiro CLI adapter entry point.

Kiro's ``preToolUse`` hook feeds ``{"tool_name", "tool_input": {"command"},
"cwd"}`` on stdin and blocks a tool call on exit code 2 with the reason on
STDERR. These tests drive the ``--kiro`` I/O shell and assert it reaches the
same guard decisions as the shared :func:`agent_guard.dispatch` core that
backs the Claude Code hook and the OpenCode adapter.
"""

from __future__ import annotations

import io
import json

import pytest

from agent_guard import ALLOW_EXIT, DENY_EXIT, kiro_main, opencode_main


def _feed(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def _event(command: str, tool_name: str = "execute_bash") -> dict:
    return {
        "hook_event_name": "preToolUse",
        "cwd": ".",
        "tool_name": tool_name,
        "tool_input": {"command": command},
    }


def test_denied_command_exits_deny_with_reason_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A Co-Authored-By trailer is one of the bundled deny rules.
    _feed(monkeypatch, _event("git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'"))
    rc = kiro_main()
    captured = capsys.readouterr()
    assert rc == DENY_EXIT
    # Kiro surfaces STDERR (not STDOUT) to the model.
    assert "commit-trailer" in captured.err
    assert captured.out == ""


def test_allowed_command_exits_allow_silently(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _feed(monkeypatch, _event("git status"))
    rc = kiro_main()
    captured = capsys.readouterr()
    assert rc == ALLOW_EXIT
    assert captured.out == "" and captured.err == ""


def test_shell_alias_is_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed(monkeypatch, _event("git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'", tool_name="shell"))
    assert kiro_main() == DENY_EXIT


def test_execute_cmd_alias_is_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed(monkeypatch, _event("git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'", tool_name="execute_cmd"))
    assert kiro_main() == DENY_EXIT


def test_non_shell_tool_is_fast_path_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed(monkeypatch, {"tool_name": "fs_read", "tool_input": {"path": "/x"}})
    assert kiro_main() == ALLOW_EXIT


def test_malformed_stdin_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed(monkeypatch, "not json {{{")
    assert kiro_main() == ALLOW_EXIT


def test_missing_tool_input_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed(monkeypatch, {"tool_name": "execute_bash"})
    assert kiro_main() == ALLOW_EXIT


def test_verdict_matches_opencode_core(monkeypatch: pytest.MonkeyPatch) -> None:
    """Differential: --kiro and --opencode reach the same dispatch() verdict."""
    cmd = "git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'"
    _feed(monkeypatch, _event(cmd))
    kiro_rc = kiro_main()
    _feed(monkeypatch, {"command": cmd})
    opencode_rc = opencode_main()
    assert kiro_rc == opencode_rc == DENY_EXIT
