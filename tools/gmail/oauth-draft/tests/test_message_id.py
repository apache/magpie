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

import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from oauth_draft.message_id import main, parse_args, root_message_id


def test_parse_args_collects_thread_ids():
    args = parse_args(["t1", "t2", "t3"])
    assert args.thread_ids == ["t1", "t2", "t3"]
    assert args.json is False


def test_parse_args_requires_at_least_one_thread():
    with pytest.raises(SystemExit):
        parse_args([])


# --- network-mocked helpers ------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def _thread_payload(message_id: str | None, *, messages: bool = True) -> bytes:
    if not messages:
        return json.dumps({"messages": []}).encode()
    headers = [{"name": "Subject", "value": "report"}]
    if message_id is not None:
        # Mixed-case header name on purpose — lookup is case-insensitive.
        headers.append({"name": "Message-Id", "value": message_id})
    return json.dumps({"messages": [{"payload": {"headers": headers}}]}).encode()


def test_root_message_id_extracts_header_case_insensitively():
    payload = _thread_payload("<abc@example.com>")
    with patch(
        "oauth_draft.message_id.urllib.request.urlopen",
        return_value=_FakeResponse(payload),
    ) as mock_open:
        mid = root_message_id("token", "tid-1")
    assert mid == "<abc@example.com>"
    request = mock_open.call_args.args[0]
    assert "/threads/tid-1" in request.full_url
    assert "format=metadata" in request.full_url
    assert "metadataHeaders=Message-ID" in request.full_url


def test_root_message_id_uses_first_message_as_root():
    payload = json.dumps(
        {
            "messages": [
                {"payload": {"headers": [{"name": "Message-ID", "value": "<root@x>"}]}},
                {"payload": {"headers": [{"name": "Message-ID", "value": "<reply@x>"}]}},
            ]
        }
    ).encode()
    with patch(
        "oauth_draft.message_id.urllib.request.urlopen",
        return_value=_FakeResponse(payload),
    ):
        assert root_message_id("token", "tid") == "<root@x>"


def test_root_message_id_returns_none_when_no_messages():
    with patch(
        "oauth_draft.message_id.urllib.request.urlopen",
        return_value=_FakeResponse(_thread_payload(None, messages=False)),
    ):
        assert root_message_id("token", "tid") is None


def test_root_message_id_returns_none_when_header_absent():
    with patch(
        "oauth_draft.message_id.urllib.request.urlopen",
        return_value=_FakeResponse(_thread_payload(None)),
    ):
        assert root_message_id("token", "tid") is None


def test_root_message_id_raises_on_http_error():
    err = urllib.error.HTTPError(
        url="https://x",
        code=404,
        msg="Not Found",
        hdrs=None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        fp=io.BytesIO(b'{"error": "missing"}'),
    )
    with patch(
        "oauth_draft.message_id.urllib.request.urlopen",
        side_effect=err,
    ):
        with pytest.raises(SystemExit) as excinfo:
            root_message_id("token", "tid-x")
    assert "threads.get failed (404) for tid-x" in str(excinfo.value)


# --- main ------------------------------------------------------------------


def _make_creds_file(tmp_path):
    p = tmp_path / "creds.json"
    p.write_text(
        json.dumps(
            {
                "client_id": "cid",
                "client_secret": "secret",
                "refresh_token": "refresh",
            }
        )
    )
    return p


def test_main_tsv_output(tmp_path, capsys):
    creds = _make_creds_file(tmp_path)
    with (
        patch("oauth_draft.message_id.refresh_access_token", return_value="tok"),
        patch(
            "oauth_draft.message_id.root_message_id",
            side_effect=["<a@x>", None],
        ),
    ):
        rc = main(["--credentials", str(creds), "t1", "t2"])
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["t1\t<a@x>", "t2\t"]


def test_main_json_output(tmp_path, capsys):
    creds = _make_creds_file(tmp_path)
    with (
        patch("oauth_draft.message_id.refresh_access_token", return_value="tok"),
        patch("oauth_draft.message_id.root_message_id", return_value="<a@x>"),
    ):
        rc = main(["--credentials", str(creds), "--json", "t1"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {"t1": "<a@x>"}
