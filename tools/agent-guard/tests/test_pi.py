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

"""Tests for the ``--pi`` entry point used by Magpie's Pi extension.

The extension (``tools/agent-isolation/pi/magpie.ts``) forwards every bash
command as ``{"command", "cwd"}`` on stdin, the transport the OpenCode plugin
uses, and blocks the call on exit 2 with the reason on stdout.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import agent_guard


def _run(flag: str, payload: object) -> subprocess.CompletedProcess[str]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, agent_guard.__file__, flag],
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )


def test_denied_command_exits_deny_with_reason_on_stdout() -> None:
    result = _run("--pi", {"command": "git commit --dry-run --no-verify -m probe", "cwd": "."})
    assert result.returncode == agent_guard.DENY_EXIT
    assert "agent-guard[no-verify]" in result.stdout


def test_allowed_command_exits_allow_silently() -> None:
    result = _run("--pi", {"command": "git status --short", "cwd": "."})
    assert result.returncode == agent_guard.ALLOW_EXIT
    assert result.stdout == ""


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x\n\nCo-Authored-By: A <a@b.c>'",
        "git commit -m 'x' --no-verify",
        "ls -la && echo hi",
    ],
)
def test_pi_and_opencode_routes_agree(command: str) -> None:
    payload = {"command": command, "cwd": "."}
    pi = _run("--pi", payload)
    opencode = _run("--opencode", payload)
    assert (pi.returncode, pi.stdout) == (opencode.returncode, opencode.stdout)
    assert (pi.returncode == agent_guard.DENY_EXIT) == (agent_guard.dispatch(command, ".") is not None)


@pytest.mark.parametrize("payload", ["not json {{{", '["a", "list"]', '{"cwd": "/tmp"}', "null"])
def test_malformed_input_fails_open(payload: str) -> None:
    result = _run("--pi", payload)
    assert result.returncode == agent_guard.ALLOW_EXIT
    assert result.stdout == ""
