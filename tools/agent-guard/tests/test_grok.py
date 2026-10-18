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

"""Tests for Grok Build's PreToolUse adapter."""

from __future__ import annotations

import io
import json
import os
import subprocess
from pathlib import Path

import pytest

import agent_guard


def _feed(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


# Captured verbatim from Grok Build 1.0.46 (2765805b9442) on 2026-10-08.
# Trigger: "Run pwd in the terminal and tell me the output."
# No payload fields were normalized or reconstructed.
_REAL_PRE_TOOL_USE = r"""{"hookEventName":"pre_tool_use","sessionId":"01a11c20-860b-7ea1-b883-16fdf069a238","cwd":"/private/tmp/magpie-grok-hook-capture","workspaceRoot":"/private/tmp/magpie-grok-hook-capture/","timestamp":"2026-10-08T15:27:41.895713+00:00","transcriptPath":"/Users/kavyakatal/.grok/sessions/%2Fprivate%2Ftmp%2Fmagpie-grok-hook-capture/01a11c20-860b-7ea1-b883-16fdf069a238/updates.jsonl","permissionMode":"default","toolName":"run_terminal_command","toolUseId":"call-7804e01f-ea34-41f2-999f-93ec4bd87d88-0","toolInput":{"command":"pwd","description":"Print the current working directory"},"toolInputTruncated":false,"hook_event_name":"PreToolUse","session_id":"01a11c20-860b-7ea1-b883-16fdf069a238","transcript_path":"/Users/kavyakatal/.grok/sessions/%2Fprivate%2Ftmp%2Fmagpie-grok-hook-capture/01a11c20-860b-7ea1-b883-16fdf069a238/updates.jsonl","permission_mode":"default","tool_name":"run_terminal_command","tool_input":{"command":"pwd","description":"Print the current working directory"},"tool_use_id":"call-7804e01f-ea34-41f2-999f-93ec4bd87d88-0"}"""


def _captured_event(
    *,
    command: str = "pwd",
    cwd: object = "/private/tmp/magpie-grok-hook-capture",
) -> dict[str, object]:
    """Return the captured event with only test-specific command/cwd changes."""
    event = json.loads(_REAL_PRE_TOOL_USE)
    event["toolInput"]["command"] = command
    if cwd is None:
        event.pop("cwd", None)
    else:
        event["cwd"] = cwd
    return event


def test_denied_command_emits_exact_grok_decision(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        agent_guard,
        "dispatch",
        lambda command, cwd=None: "blocked by test",
    )
    _feed(monkeypatch, _captured_event(command="git push"))

    assert agent_guard.grok_main() == agent_guard.DENY_EXIT

    captured = capsys.readouterr()
    assert captured.out == '{"decision": "deny", "reason": "blocked by test"}\n'
    assert captured.err == ""


def test_allowed_command_emits_exact_grok_decision(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(agent_guard, "dispatch", lambda command, cwd=None: None)
    _feed(monkeypatch, _captured_event(command="git status"))

    assert agent_guard.grok_main() == agent_guard.ALLOW_EXIT

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_real_captured_pre_tool_use_payload_reaches_dispatch(monkeypatch):
    """The verbatim Grok 1.0.46 capture reaches the shared dispatcher unchanged."""
    seen = []

    def fake_dispatch(command, cwd=None):
        seen.append((command, cwd))
        return None

    monkeypatch.setattr("agent_guard.dispatch", fake_dispatch)
    _feed(monkeypatch, _REAL_PRE_TOOL_USE)

    assert agent_guard.grok_main() == agent_guard.ALLOW_EXIT
    assert seen == [
        ("pwd", "/private/tmp/magpie-grok-hook-capture"),
    ]


def test_captured_shell_tool_reaches_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str | None]] = []

    def fake_dispatch(command: str, cwd: str | None = None) -> str | None:
        seen.append((command, cwd))
        return None

    monkeypatch.setattr(agent_guard, "dispatch", fake_dispatch)
    _feed(
        monkeypatch,
        _captured_event(command="git status", cwd="/repo"),
    )

    assert agent_guard.grok_main() == agent_guard.ALLOW_EXIT
    assert seen == [("git status", "/repo")]


@pytest.mark.parametrize("cwd", [None, [], 42])
def test_invalid_or_missing_cwd_forwards_none(
    monkeypatch: pytest.MonkeyPatch,
    cwd: object,
) -> None:
    seen: list[str | None] = []

    def fake_dispatch(command: str, cwd: str | None = None) -> str | None:
        seen.append(cwd)
        return None

    monkeypatch.setattr(agent_guard, "dispatch", fake_dispatch)

    event = _captured_event(command="git status", cwd=cwd)

    _feed(monkeypatch, event)

    assert agent_guard.grok_main() == agent_guard.ALLOW_EXIT
    assert seen == [None]


@pytest.mark.parametrize(
    "payload",
    [
        "not JSON",
        "[]",
        "null",
        json.dumps(
            {
                "toolName": "read_file",
                "toolInput": {"path": "README.md"},
            }
        ),
        json.dumps({"toolName": "run_terminal_command"}),
        json.dumps(
            {
                "toolName": "run_terminal_command",
                "toolInput": [],
            }
        ),
        json.dumps(
            {
                "toolName": "run_terminal_command",
                "toolInput": {},
            }
        ),
        json.dumps(
            {
                "toolName": "run_terminal_command",
                "toolInput": {"command": None},
            }
        ),
        json.dumps(
            {
                "toolName": "run_terminal_command",
                "toolInput": {"command": 42},
            }
        ),
    ],
)
def test_irrelevant_or_malformed_event_fails_open_silently(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: str,
) -> None:
    def unexpected_dispatch(*args: object) -> None:
        pytest.fail("Malformed or irrelevant Grok event reached dispatch")

    monkeypatch.setattr(agent_guard, "dispatch", unexpected_dispatch)
    _feed(monkeypatch, payload)

    assert agent_guard.grok_main() == agent_guard.ALLOW_EXIT
    assert capsys.readouterr() == ("", "")


def test_cli_routes_grok_flag_to_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent_guard, "grok_main", lambda: 37)

    assert agent_guard.cli(["--grok"]) == 37


def test_default_invocation_routes_real_grok_payload_by_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _feed(monkeypatch, _REAL_PRE_TOOL_USE)
    monkeypatch.setattr(agent_guard, "_grok_event", lambda event: 41)
    monkeypatch.setattr(
        agent_guard,
        "_claude_event",
        lambda event: pytest.fail("Grok payload must not route to Claude"),
    )

    assert agent_guard.cli([]) == 41


def test_default_invocation_routes_claude_payload_by_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _feed(
        monkeypatch,
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}),
    )
    monkeypatch.setenv("GROK_HOOK_EVENT", "pre_tool_use")
    monkeypatch.setattr(agent_guard, "_claude_event", lambda event: 43)
    monkeypatch.setattr(
        agent_guard,
        "_grok_event",
        lambda event: pytest.fail("Inherited GROK_HOOK_EVENT must not reroute a Claude payload"),
    )

    assert agent_guard.cli([]) == 43


def test_project_hook_template_runs_grok_adapter_end_to_end() -> None:
    """The setup template must invoke this adapter, not the tool command."""
    repo_root = Path(agent_guard.__file__).resolve().parents[4]
    hook_file = repo_root / "plugins" / "magpie-setup" / "templates" / "grok-agent-guard-hook.json"

    config = json.loads(hook_file.read_text())
    groups = config["hooks"]["PreToolUse"]

    assert len(groups) == 1
    assert groups[0]["matcher"] == "Bash"

    handlers = groups[0]["hooks"]
    assert len(handlers) == 1

    handler = handlers[0]
    assert handler["type"] == "command"
    assert handler["timeout"] == 30
    assert handler["command"].endswith('tools/agent-guard/src/agent_guard/__init__.py" --grok')

    event = _captured_event(
        command="git commit -m 'x\\n\\nCo-Authored-By: A <a@b.c>'",
        cwd=str(repo_root),
    )

    result = subprocess.run(
        handler["command"],
        shell=True,
        cwd=repo_root,
        env={
            **os.environ,
            "GROK_WORKSPACE_ROOT": str(repo_root),
        },
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == agent_guard.DENY_EXIT
    assert result.stderr == ""

    response = json.loads(result.stdout)
    assert response["decision"] == "deny"
    assert "commit-trailer" in response["reason"]
