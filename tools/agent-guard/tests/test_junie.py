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
"""Tests for the Junie CLI PreToolUse adapter."""

from __future__ import annotations

import io
import json

import pytest

import agent_guard


def _feed(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def _event(command: object = "git status", tool: str = "Bash") -> dict[str, object]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"command": command, "run_in_background": False, "timeout": 30},
    }


def test_denied_command_exits_2_with_reason_on_stderr_and_decision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(agent_guard, "dispatch", lambda command, cwd=None: "blocked by test")
    _feed(monkeypatch, _event("git push"))

    assert agent_guard.junie_main() == agent_guard.DENY_EXIT == 2

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"decision": "deny", "reason": "blocked by test"}
    assert captured.err == "blocked by test\n"


def test_allowed_command_is_silent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(agent_guard, "dispatch", lambda command, cwd=None: None)
    _feed(monkeypatch, _event())

    assert agent_guard.junie_main() == agent_guard.ALLOW_EXIT

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cwd_is_forwarded_when_a_string(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []
    monkeypatch.setattr(agent_guard, "dispatch", lambda command, cwd=None: seen.append(cwd))
    event = _event()
    event["cwd"] = "/work"
    _feed(monkeypatch, event)

    agent_guard.junie_main()

    assert seen == ["/work"]


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        _event(tool="Read"),
        {"tool_name": "Bash"},
        {"tool_name": "Bash", "tool_input": {"command": 5}},
    ],
)
def test_malformed_or_unrelated_input_fails_open(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    def _boom(command: str, cwd: str | None = None) -> str:
        raise AssertionError("dispatch must not run")

    monkeypatch.setattr(agent_guard, "dispatch", _boom)
    _feed(monkeypatch, payload)

    assert agent_guard.junie_main() == agent_guard.ALLOW_EXIT


def test_cli_routes_junie_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_guard, "dispatch", lambda command, cwd=None: "no")
    _feed(monkeypatch, _event("git push"))

    assert agent_guard.cli(["--junie"]) == agent_guard.DENY_EXIT
