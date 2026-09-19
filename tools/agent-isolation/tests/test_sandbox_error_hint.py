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

"""Tests for sandbox-error-hint.sh.

The hook reads a PostToolUse JSON envelope on stdin, scans the Bash
tool's stdout + stderr for catalogued sandbox-shaped error strings, and
exits 1 with a ``[sandbox-hint] …`` line on stderr when one matches.
Everything else exits 0 silently (fail-open).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "sandbox-error-hint.sh"
DOC = "docs/setup/sandbox-troubleshooting.md"


def _run(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
    )


def _bash(stdout: str = "", stderr: str = "") -> str:
    return json.dumps(
        {"tool_name": "Bash", "tool_response": {"stdout": stdout, "stderr": stderr}}
    )


# ---------------------------------------------------------------------------
# silent paths (exit 0, no output)
# ---------------------------------------------------------------------------


class TestSilent:
    def test_benign_output_exits_zero(self) -> None:
        result = _run(_bash(stdout="hello world"))
        assert result.returncode == 0
        assert result.stderr == ""

    def test_non_bash_tool_exits_zero(self) -> None:
        payload = json.dumps(
            {"tool_name": "Read", "tool_response": "x509: OSStatus -26276"}
        )
        result = _run(payload)
        assert result.returncode == 0
        assert result.stderr == ""

    def test_invalid_json_exits_zero(self) -> None:
        result = _run("not json at all")
        assert result.returncode == 0
        assert result.stderr == ""

    def test_empty_response_exits_zero(self) -> None:
        result = _run(_bash())
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# catalogued signatures → exit 1 + anchored hint
# ---------------------------------------------------------------------------


class TestKnownSignatures:
    def test_ssh_agent_signature(self) -> None:
        result = _run(_bash(stderr="Could not open a connection to your authentication agent."))
        assert result.returncode == 1
        assert "[sandbox-hint]" in result.stderr
        assert f"{DOC}#ssh-agent--yubikey-appears-unreachable-from-inside-the-sandbox" in result.stderr

    def test_docker_signature(self) -> None:
        result = _run(_bash(stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock"))
        assert result.returncode == 1
        assert f"{DOC}#docker--podman-command-fails-with-a-socket-error" in result.stderr

    def test_tmp_signature(self) -> None:
        result = _run(
            _bash(stderr="mktemp: failed to create directory via template '/tmp/tmp.XXXXXXXXXX': Read-only file system")
        )
        assert result.returncode == 1
        assert f"{DOC}#temp-files-fail-with-read-only-file-system-under-tmp" in result.stderr

    def test_string_shaped_tool_response(self) -> None:
        payload = json.dumps(
            {"tool_name": "Bash", "tool_response": "Cannot connect to the Docker daemon"}
        )
        result = _run(payload)
        assert result.returncode == 1


class TestGhInsideSandbox:
    """`gh` that did not get excluded from the sandbox (see the catalog entry)."""

    ANCHOR = f"{DOC}#gh-fails-with-tls-osstatus--26276-or-http-401-inside-the-sandbox"

    def test_tls_osstatus_signature(self) -> None:
        stderr = 'Get "https://api.github.com/user": tls: failed to verify certificate: x509: OSStatus -26276'
        result = _run(_bash(stderr=stderr))
        assert result.returncode == 1
        assert "[sandbox-hint]" in result.stderr
        assert self.ANCHOR in result.stderr

    def test_keyring_401_signature(self) -> None:
        stderr = "HTTP 401: Requires authentication (https://api.github.com/graphql)"
        result = _run(_bash(stderr=stderr))
        assert result.returncode == 1
        assert self.ANCHOR in result.stderr

    def test_signature_in_stdout_also_matches(self) -> None:
        # `2>&1` in the tool call moves the message to stdout; the hook scans both.
        result = _run(_bash(stdout="x509: OSStatus -26276"))
        assert result.returncode == 1
        assert self.ANCHOR in result.stderr

    def test_hint_names_the_invocation_shape_rule(self) -> None:
        result = _run(_bash(stderr="x509: OSStatus -26276"))
        assert "gh" in result.stderr
        assert "sandbox" in result.stderr.lower()

    def test_unrelated_401_does_not_match(self) -> None:
        # A 401 from some other host is not the gh-in-sandbox shape.
        result = _run(_bash(stderr="HTTP 401: Unauthorized (https://example.com/api)"))
        assert result.returncode == 0
