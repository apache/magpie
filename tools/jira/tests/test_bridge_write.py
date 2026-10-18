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

"""Tests for bridge.groovy write subcommands.

Strategy: spin up a lightweight HTTP mock server that records requests
and returns canned JIRA API responses, then invoke bridge.groovy via
subprocess against it.  Requires ``groovy`` on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

BRIDGE = Path(__file__).parent.parent / "bridge.groovy"
GROOVY = shutil.which("groovy")

pytestmark = pytest.mark.skipif(GROOVY is None, reason="groovy not found on PATH")


# ---------------------------------------------------------------------------
# Mock JIRA server
# ---------------------------------------------------------------------------


class _RequestLog:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def clear(self) -> None:
        self.requests.clear()


_log = _RequestLog()
_canned_responses: dict[str, tuple[int, Any]] = {}


class _JiraHandler(BaseHTTPRequestHandler):
    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _handle(self, method: str) -> None:
        body = self._read_body()
        entry: dict[str, Any] = {
            "method": method,
            "path": self.path,
            "headers": dict(self.headers),
        }
        if body:
            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type:
                entry["body"] = json.loads(body)
            else:
                entry["body_raw"] = body
        _log.requests.append(entry)

        key = f"{method} {self.path.split('?')[0]}"
        if key in _canned_responses:
            status, payload = _canned_responses[key]
        else:
            status, payload = 200, {}
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if status != 204 and payload is not None:
            self.wfile.write(json.dumps(payload).encode())

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_PUT(self) -> None:
        self._handle("PUT")

    def log_message(self, format: str, *args: Any) -> None:
        pass  # suppress console noise


@pytest.fixture(scope="module")
def mock_server():
    server = HTTPServer(("127.0.0.1", 0), _JiraHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def _clear_state():
    _log.clear()
    _canned_responses.clear()
    yield
    _log.clear()
    _canned_responses.clear()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(
    mock_url: str,
    args: list[str],
    *,
    token: str = "dGVzdDp0b2tlbg==",
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "ISSUE_TRACKER_URL": mock_url,
        "ISSUE_TRACKER_PROJECT": "TEST",
    }
    # The agent sandbox refuses IPv6 loopback sockets, so keep the JVM on IPv4 to reach the mock server; harmless elsewhere.
    java_options = os.environ.get("JAVA_TOOL_OPTIONS", "")
    if "-Djava.net.preferIPv4Stack=true" not in java_options:
        java_options = f"{java_options} -Djava.net.preferIPv4Stack=true".strip()
    env["JAVA_TOOL_OPTIONS"] = java_options
    if token:
        env["JIRA_API_TOKEN"] = token
    if env_extra:
        env.update(env_extra)
    assert GROOVY is not None
    return subprocess.run(
        [GROOVY, str(BRIDGE)] + args,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# comment
# ---------------------------------------------------------------------------


class TestComment:
    def test_post_comment(self, mock_server: str, tmp_path: Path) -> None:
        body_file = tmp_path / "comment.txt"
        body_file.write_text("This is a test comment.")
        _canned_responses["POST /rest/api/2/issue/FOO-1/comment"] = (
            201,
            {"id": "12345", "body": "This is a test comment."},
        )
        result = _run(mock_server, ["comment", "FOO-1", "--body-file", str(body_file)])
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["ok"] is True
        assert out["key"] == "FOO-1"
        assert out["commentId"] == "12345"
        req = _log.requests[-1]
        assert req["method"] == "POST"
        assert req["body"]["body"] == "This is a test comment."

    def test_missing_body_file_flag(self, mock_server: str) -> None:
        result = _run(mock_server, ["comment", "FOO-1"])
        assert result.returncode != 0
        assert "--body-file" in result.stderr

    def test_nonexistent_body_file(self, mock_server: str) -> None:
        result = _run(mock_server, ["comment", "FOO-1", "--body-file", "/no/such/file"])
        assert result.returncode != 0
        assert "not found" in result.stderr

    def test_invalid_key(self, mock_server: str, tmp_path: Path) -> None:
        body_file = tmp_path / "c.txt"
        body_file.write_text("x")
        result = _run(
            mock_server, ["comment", "bad-key", "--body-file", str(body_file)]
        )
        assert result.returncode != 0
        assert "not a valid" in result.stderr


# ---------------------------------------------------------------------------
# transition
# ---------------------------------------------------------------------------


class TestTransition:
    def test_transition_by_name(self, mock_server: str) -> None:
        _canned_responses["GET /rest/api/2/issue/FOO-2/transitions"] = (
            200,
            {
                "transitions": [
                    {"id": "11", "name": "Start Progress"},
                    {"id": "21", "name": "Resolve Issue"},
                ]
            },
        )
        _canned_responses["POST /rest/api/2/issue/FOO-2/transitions"] = (204, None)
        result = _run(mock_server, ["transition", "FOO-2", "Resolve Issue"])
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["ok"] is True
        assert out["transition"] == "Resolve Issue"
        assert out["transitionId"] == "21"

    def test_case_insensitive_match(self, mock_server: str) -> None:
        _canned_responses["GET /rest/api/2/issue/FOO-2/transitions"] = (
            200,
            {"transitions": [{"id": "11", "name": "Start Progress"}]},
        )
        _canned_responses["POST /rest/api/2/issue/FOO-2/transitions"] = (204, None)
        result = _run(mock_server, ["transition", "FOO-2", "start progress"])
        assert result.returncode == 0

    def test_unknown_transition(self, mock_server: str) -> None:
        _canned_responses["GET /rest/api/2/issue/FOO-2/transitions"] = (
            200,
            {"transitions": [{"id": "11", "name": "Start Progress"}]},
        )
        result = _run(mock_server, ["transition", "FOO-2", "NoSuchTransition"])
        assert result.returncode != 0
        assert "not found" in result.stderr

    def test_missing_transition_name(self, mock_server: str) -> None:
        result = _run(mock_server, ["transition", "FOO-2"])
        assert result.returncode != 0
        assert "transition requires" in result.stderr


# ---------------------------------------------------------------------------
# label
# ---------------------------------------------------------------------------


class TestLabel:
    def test_add_label(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-3"] = (204, None)
        result = _run(mock_server, ["label", "FOO-3", "--add", "new-label"])
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["added"] == ["new-label"]
        assert out["removed"] == []
        req = _log.requests[-1]
        assert req["method"] == "PUT"
        assert req["body"]["update"]["labels"] == [{"add": "new-label"}]

    def test_remove_label(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-3"] = (204, None)
        result = _run(mock_server, ["label", "FOO-3", "--remove", "drop"])
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["removed"] == ["drop"]
        req = _log.requests[-1]
        assert req["body"]["update"]["labels"] == [{"remove": "drop"}]

    def test_add_and_remove(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-3"] = (204, None)
        result = _run(mock_server, ["label", "FOO-3", "--add", "c", "--remove", "a"])
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["added"] == ["c"]
        assert out["removed"] == ["a"]
        req = _log.requests[-1]
        assert req["body"]["update"]["labels"] == [{"add": "c"}, {"remove": "a"}]

    def test_no_flags(self, mock_server: str) -> None:
        result = _run(mock_server, ["label", "FOO-3"])
        assert result.returncode != 0
        assert "--add or --remove" in result.stderr


# ---------------------------------------------------------------------------
# assign
# ---------------------------------------------------------------------------


class TestAssign:
    def test_assign_user(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-4/assignee"] = (204, None)
        result = _run(mock_server, ["assign", "FOO-4", "jdoe"])
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["ok"] is True
        assert out["assignee"] == "jdoe"
        req = _log.requests[-1]
        assert req["body"]["name"] == "jdoe"

    def test_missing_username(self, mock_server: str) -> None:
        result = _run(mock_server, ["assign", "FOO-4"])
        assert result.returncode != 0
        assert "username" in result.stderr


# ---------------------------------------------------------------------------
# field
# ---------------------------------------------------------------------------


class TestField:
    def test_set_field(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-5"] = (204, None)
        result = _run(
            mock_server, ["field", "FOO-5", "customfield_10100", "--value", "high"]
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["field"] == "customfield_10100"
        assert out["value"] == "high"
        req = _log.requests[-1]
        assert req["body"]["fields"]["customfield_10100"] == "high"

    def test_missing_field_name(self, mock_server: str) -> None:
        result = _run(mock_server, ["field", "FOO-5"])
        assert result.returncode != 0
        assert "field requires" in result.stderr

    def test_missing_value(self, mock_server: str) -> None:
        result = _run(mock_server, ["field", "FOO-5", "customfield_10100"])
        assert result.returncode != 0
        assert "--value" in result.stderr

    def test_value_json_object(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-5"] = (204, None)
        result = _run(
            mock_server,
            ["field", "FOO-5", "priority", "--value-json", '{"name":"High"}'],
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["value"] == {"name": "High"}
        req = _log.requests[-1]
        assert req["body"]["fields"]["priority"] == {"name": "High"}

    def test_value_json_array(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-5"] = (204, None)
        result = _run(
            mock_server,
            ["field", "FOO-5", "fixVersions", "--value-json", '[{"name":"1.2.3"}]'],
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["value"] == [{"name": "1.2.3"}]
        req = _log.requests[-1]
        assert req["body"]["fields"]["fixVersions"] == [{"name": "1.2.3"}]


# ---------------------------------------------------------------------------
# attach
# ---------------------------------------------------------------------------


class TestAttach:
    def test_attach_file(self, mock_server: str, tmp_path: Path) -> None:
        attachment = tmp_path / "report.txt"
        attachment.write_text("file content here")
        _canned_responses["POST /rest/api/2/issue/FOO-6/attachments"] = (
            200,
            [{"id": "99", "filename": "report.txt"}],
        )
        result = _run(mock_server, ["attach", "FOO-6", str(attachment)])
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["ok"] is True
        assert out["attachments"][0]["filename"] == "report.txt"
        req = _log.requests[-1]
        assert req["method"] == "POST"
        assert "X-Atlassian-Token" in req["headers"]

    def test_nonexistent_file(self, mock_server: str) -> None:
        result = _run(mock_server, ["attach", "FOO-6", "/no/such/file.txt"])
        assert result.returncode != 0
        assert "not found" in result.stderr

    def test_missing_file_arg(self, mock_server: str) -> None:
        result = _run(mock_server, ["attach", "FOO-6"])
        assert result.returncode != 0
        assert "file path" in result.stderr


# ---------------------------------------------------------------------------
# auth requirement for writes
# ---------------------------------------------------------------------------


class TestAuth:
    def test_comment_requires_token(self, mock_server: str, tmp_path: Path) -> None:
        body_file = tmp_path / "c.txt"
        body_file.write_text("x")
        result = _run(
            mock_server, ["comment", "FOO-1", "--body-file", str(body_file)], token=""
        )
        assert result.returncode != 0
        assert "JIRA_API_TOKEN" in result.stderr

    def test_assign_requires_token(self, mock_server: str) -> None:
        result = _run(mock_server, ["assign", "FOO-1", "user"], token="")
        assert result.returncode != 0
        assert "JIRA_API_TOKEN" in result.stderr

    def test_basic_auth_header(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-1/assignee"] = (204, None)
        result = _run(
            mock_server, ["assign", "FOO-1", "jdoe"], token="dGVzdDp0b2tlbg=="
        )
        assert result.returncode == 0
        req = _log.requests[-1]
        assert req["headers"]["Authorization"] == "Basic dGVzdDp0b2tlbg=="

    def test_bearer_auth_scheme(self, mock_server: str) -> None:
        _canned_responses["PUT /rest/api/2/issue/FOO-1/assignee"] = (204, None)
        result = _run(
            mock_server,
            ["assign", "FOO-1", "jdoe"],
            token="my-pat-token",
            env_extra={"JIRA_AUTH_SCHEME": "Bearer"},
        )
        assert result.returncode == 0
        req = _log.requests[-1]
        assert req["headers"]["Authorization"] == "Bearer my-pat-token"


# ---------------------------------------------------------------------------
# unknown subcommand
# ---------------------------------------------------------------------------


class TestUnknown:
    def test_unknown_subcommand(self, mock_server: str) -> None:
        result = _run(mock_server, ["bogus"])
        assert result.returncode != 0
        assert "unknown subcommand" in result.stderr

    def test_no_args(self, mock_server: str) -> None:
        result = _run(mock_server, [])
        assert result.returncode != 0
