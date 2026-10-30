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
from __future__ import annotations

import base64
import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from oauth_draft.credentials import Credentials
from oauth_draft.fetch_message import fetch_raw, main, parse_args, summarize

RAW = (
    b"Subject: [Anthropic OSS Scanner] Disclosing 2 security vulnerabilities in widget\r\n"
    b"From: oss-scanner <scanner@example.com>\r\n"
    b"Date: Tue, 20 Oct 2026 19:25:28 -0400\r\n"
    b"Message-ID: <scan@example.com>\r\n"
    b"\r\n"
    b"Body with a NUL byte \x00 that a text rendering would drop.\r\n"
)


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def _payload(raw: bytes) -> bytes:
    # Gmail returns base64url without padding.
    return json.dumps({"threadId": "t-1", "raw": base64.urlsafe_b64encode(raw).decode().rstrip("=")}).encode()


def test_parse_args_requires_out():
    with pytest.raises(SystemExit):
        parse_args(["m-1"])
    assert parse_args(["m-1", "--out", "x.eml"]).message_id == "m-1"


def test_fetch_raw_decodes_unpadded_base64url_byte_for_byte():
    with patch(
        "oauth_draft.fetch_message.urllib.request.urlopen", return_value=_FakeResponse(_payload(RAW))
    ) as mock_open:
        raw, thread_id = fetch_raw("token", "m-1")
    assert raw == RAW and thread_id == "t-1"
    request = mock_open.call_args.args[0]
    assert request.full_url.endswith("/messages/m-1?format=raw")
    assert request.get_method() == "GET"


def test_fetch_raw_surfaces_http_errors():
    err = urllib.error.HTTPError(
        url="https://x",
        code=404,
        msg="Not Found",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b"no such message"),
    )
    with (
        patch("oauth_draft.fetch_message.urllib.request.urlopen", side_effect=err),
        pytest.raises(SystemExit, match="404"),
    ):
        fetch_raw("token", "m-1")


def test_summarize_reports_headers_never_the_body():
    summary = summarize(RAW)
    assert summary["Message-ID"] == "<scan@example.com>"
    assert "NUL" not in json.dumps(summary)


def test_main_writes_the_eml_and_prints_a_summary(tmp_path, capsys):
    out = tmp_path / "nested" / "scan.eml"
    creds = Credentials(client_id="c", client_secret="s", refresh_token="r")
    with (
        patch("oauth_draft.fetch_message.locate_credentials", return_value=tmp_path / "creds.json"),
        patch("oauth_draft.fetch_message.Credentials.load", return_value=creds),
        patch("oauth_draft.fetch_message.refresh_access_token", return_value="token"),
        patch("oauth_draft.fetch_message.urllib.request.urlopen", return_value=_FakeResponse(_payload(RAW))),
    ):
        assert main(["m-1", "--out", str(out)]) == 0
    assert out.read_bytes() == RAW
    assert out.stat().st_mode & 0o077 == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["bytes"] == len(RAW) and printed["thread_id"] == "t-1"
    assert printed["headers"]["Subject"].startswith("[Anthropic OSS Scanner]")
