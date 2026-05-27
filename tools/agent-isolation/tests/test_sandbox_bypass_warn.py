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

"""Tests for sandbox-bypass-warn.sh.

The hook reads a JSON tool-use payload on stdin and exits 1 (banner on
stderr) when ``dangerouslyDisableSandbox: true`` is present, or 0
(silent) otherwise.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "sandbox-bypass-warn.sh"


def _run(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# normal (no bypass)
# ---------------------------------------------------------------------------


class TestNormalInput:
    def test_empty_object_exits_zero(self) -> None:
        result = _run("{}")
        assert result.returncode == 0

    def test_normal_bash_call_exits_zero(self) -> None:
        payload = '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}'
        result = _run(payload)
        assert result.returncode == 0
        assert result.stderr == ""

    def test_bypass_false_exits_zero(self) -> None:
        payload = '{"tool_name":"Bash","tool_input":{"dangerouslyDisableSandbox":false,"command":"ls"}}'
        result = _run(payload)
        assert result.returncode == 0

    def test_read_tool_exits_zero(self) -> None:
        payload = '{"tool_name":"Read","tool_input":{"file_path":"/etc/hosts"}}'
        result = _run(payload)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# bypass detected → exit 1 + banner
# ---------------------------------------------------------------------------


class TestBypassDetected:
    def test_exits_one_on_bypass_true(self) -> None:
        payload = '{"tool_input":{"dangerouslyDisableSandbox":true,"command":"rm -rf /"}}'
        result = _run(payload)
        assert result.returncode == 1

    def test_banner_on_stderr(self) -> None:
        payload = '{"tool_input":{"dangerouslyDisableSandbox":true,"command":"ls","description":"test reason"}}'
        result = _run(payload)
        assert "SANDBOX BYPASS REQUESTED" in result.stderr

    def test_command_shown_in_banner(self) -> None:
        payload = '{"tool_input":{"dangerouslyDisableSandbox":true,"command":"cat /etc/shadow","description":"read shadow"}}'
        result = _run(payload)
        assert "cat /etc/shadow" in result.stderr

    def test_description_shown_in_banner(self) -> None:
        payload = '{"tool_input":{"dangerouslyDisableSandbox":true,"command":"ls","description":"my stated reason"}}'
        result = _run(payload)
        assert "my stated reason" in result.stderr

    def test_no_stdout_on_bypass(self) -> None:
        """Warning must go to stderr, not stdout (callers read stdout)."""
        payload = '{"tool_input":{"dangerouslyDisableSandbox":true,"command":"ls"}}'
        result = _run(payload)
        assert result.stdout == ""


# ---------------------------------------------------------------------------
# pattern robustness
# ---------------------------------------------------------------------------


class TestPatternRobustness:
    def test_spaces_around_colon(self) -> None:
        """grep pattern handles optional whitespace on both sides of ':'."""
        payload = '{"dangerouslyDisableSandbox" : true}'
        result = _run(payload)
        assert result.returncode == 1

    def test_no_spaces_around_colon(self) -> None:
        payload = '{"dangerouslyDisableSandbox":true}'
        result = _run(payload)
        assert result.returncode == 1

    def test_tab_before_colon(self) -> None:
        payload = '{"dangerouslyDisableSandbox"\t:\ttrue}'
        result = _run(payload)
        assert result.returncode == 1

    def test_does_not_match_dangerously_disable_sandbox_false(self) -> None:
        """Must not trigger on the string 'false'."""
        payload = '{"dangerouslyDisableSandbox":false}'
        result = _run(payload)
        assert result.returncode == 0

    def test_does_not_match_random_true_field(self) -> None:
        """A different boolean field must not trigger the hook."""
        payload = '{"someOtherField":true,"command":"ls"}'
        result = _run(payload)
        assert result.returncode == 0
