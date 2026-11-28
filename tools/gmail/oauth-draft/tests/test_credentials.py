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
from email.message import Message
from unittest.mock import patch

import pytest

from oauth_draft.credentials import (
    Credentials,
    locate_credentials,
    refresh_access_token,
)


def write_creds(path, **overrides):
    data = {
        "client_id": "id-123",
        "client_secret": "secret-456",
        "refresh_token": "refresh-789",
        "from_address": "you@example.com",
    }
    data.update(overrides)
    path.write_text(json.dumps(data))
    return path


def test_load_full_record(tmp_path):
    p = write_creds(tmp_path / "c.json")
    creds = Credentials.load(p)
    assert creds.client_id == "id-123"
    assert creds.client_secret == "secret-456"
    assert creds.refresh_token == "refresh-789"
    assert creds.from_address == "you@example.com"


def test_load_missing_required_field(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"client_id": "x", "client_secret": "y"}))
    with pytest.raises(SystemExit) as excinfo:
        Credentials.load(p)
    assert "refresh_token" in str(excinfo.value)
    assert "from_address" in str(excinfo.value)


def test_load_without_from_address_when_not_required(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"client_id": "x", "client_secret": "y", "refresh_token": "z"}))
    creds = Credentials.load(p, require_from_address=False)
    assert creds.from_address is None


def test_load_empty_value_treated_as_missing(tmp_path):
    p = write_creds(tmp_path / "c.json", refresh_token="")
    with pytest.raises(SystemExit) as excinfo:
        Credentials.load(p)
    assert "refresh_token" in str(excinfo.value)


def test_locate_explicit_wins(tmp_path, monkeypatch):
    explicit = tmp_path / "explicit.json"
    explicit.write_text("{}")
    other = tmp_path / "other.json"
    other.write_text("{}")
    monkeypatch.setenv("GMAIL_OAUTH_CREDENTIALS", str(other))
    assert locate_credentials(str(explicit)) == explicit


def test_locate_falls_back_to_env(tmp_path, monkeypatch):
    env_path = tmp_path / "env.json"
    env_path.write_text("{}")
    monkeypatch.setenv("GMAIL_OAUTH_CREDENTIALS", str(env_path))
    assert locate_credentials(None) == env_path


def test_locate_raises_when_nothing_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("GMAIL_OAUTH_CREDENTIALS", raising=False)
    monkeypatch.setattr(
        "oauth_draft.credentials.DEFAULT_CREDENTIALS_PATH",
        tmp_path / "does-not-exist.json",
    )
    with pytest.raises(SystemExit) as excinfo:
        locate_credentials(None)
    assert "No Gmail OAuth credentials found" in str(excinfo.value)


# --- refresh_access_token --------------------------------------------------


CREDS = Credentials(
    client_id="cid",
    client_secret="secret",
    refresh_token="refresh",
    from_address="me@example.com",
)


class _FakeResponse:
    """Minimal context-manager stand-in for urllib.request.urlopen()."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def test_refresh_access_token_returns_access_token():
    with patch("oauth_draft.credentials.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(b'{"access_token": "abc-123"}')
        token = refresh_access_token(CREDS)
    assert token == "abc-123"
    # The POST body must include all four OAuth refresh-flow params.
    request = mock_open.call_args.args[0]
    assert request.method == "POST"
    assert request.full_url == "https://oauth2.googleapis.com/token"
    body = request.data.decode()
    assert "client_id=cid" in body
    assert "client_secret=secret" in body
    assert "refresh_token=refresh" in body
    assert "grant_type=refresh_token" in body


def test_refresh_access_token_raises_on_http_error():
    err = urllib.error.HTTPError(
        url="https://oauth2.googleapis.com/token",
        code=400,
        msg="Bad Request",
        hdrs=Message(),
        fp=io.BytesIO(b'{"error": "invalid_grant"}'),
    )
    with patch("oauth_draft.credentials.urllib.request.urlopen", side_effect=err):
        with pytest.raises(SystemExit) as excinfo:
            refresh_access_token(CREDS)
    assert "OAuth token refresh failed (400)" in str(excinfo.value)
    assert "invalid_grant" in str(excinfo.value)


def test_refresh_access_token_raises_when_no_token_in_payload():
    with patch("oauth_draft.credentials.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(b'{"expires_in": 3600}')
        with pytest.raises(SystemExit) as excinfo:
            refresh_access_token(CREDS)
    assert "no access_token" in str(excinfo.value)
