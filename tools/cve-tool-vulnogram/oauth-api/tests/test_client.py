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

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from vulnogram_api import client as client_mod
from vulnogram_api.client import (
    CSRFNotFound,
    RecordSaveFailed,
    SessionExpired,
    VulnogramAPIError,
    fetch_csrf_token,
    get_record,
    probe,
    update_record,
)
from vulnogram_api.credentials import Session


def _session() -> Session:
    return Session(
        host="cveprocess.apache.org",
        cookie_name="connect.sid",
        cookie_value="s%3Aabc",
        from_address=None,
    )


class _FakeResponse:
    """Mimic the urllib response context-manager surface."""

    def __init__(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def read(self) -> bytes:
        return self._body


def _fake_open(status: int, body: bytes, headers: dict[str, str] | None = None) -> Any:
    """Build a callable usable as an opener.open replacement."""
    captured: dict[str, Any] = {}

    def _open(req: Any, timeout: int = 30) -> _FakeResponse:
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["body"] = req.data
        return _FakeResponse(status, body, headers)

    _open.captured = captured  # type: ignore[attr-defined]
    return _open


def _patch_opener(open_fn: Any) -> Any:
    """Replace ``client._request``'s ``build_opener`` so the .open binds."""
    opener = MagicMock()
    opener.open = open_fn
    return patch.object(client_mod.urllib.request, "build_opener", return_value=opener)


def test_get_record_returns_first_doc():
    body = json.dumps([{"cveMetadata": {"cveId": "CVE-2026-12345"}}]).encode()
    open_fn = _fake_open(200, body)
    with _patch_opener(open_fn):
        doc = get_record(_session(), "CVE-2026-12345")
    assert doc == {"cveMetadata": {"cveId": "CVE-2026-12345"}}
    assert open_fn.captured["url"] == "https://cveprocess.apache.org/cve5/json/CVE-2026-12345"
    assert open_fn.captured["method"] == "GET"
    # Cookie attached. urllib capitalises the header name as `Cookie`.
    headers_lower = {k.lower(): v for k, v in open_fn.captured["headers"].items()}
    assert headers_lower["cookie"] == "connect.sid=s%3Aabc"


def test_get_record_session_expired_via_oauth_redirect():
    open_fn = _fake_open(302, b"", {"Location": "https://oauth.apache.org/auth?state=x"})
    with _patch_opener(open_fn), pytest.raises(SessionExpired):
        get_record(_session(), "CVE-2026-12345")


def test_get_record_session_expired_via_login_redirect():
    open_fn = _fake_open(302, b"", {"Location": "/users/login"})
    with _patch_opener(open_fn), pytest.raises(SessionExpired):
        get_record(_session(), "CVE-2026-12345")


def test_get_record_empty_list_raises():
    open_fn = _fake_open(200, b"[]")
    with _patch_opener(open_fn), pytest.raises(VulnogramAPIError, match="not found"):
        get_record(_session(), "CVE-2026-99999")


def test_get_record_non_list_raises():
    open_fn = _fake_open(200, b'{"oops": true}')
    with _patch_opener(open_fn), pytest.raises(VulnogramAPIError, match="did not return a list"):
        get_record(_session(), "CVE-2026-12345")


def test_fetch_csrf_token_scrapes_inline_var():
    body = b"""<html><head>
    <script>
        var draftsEnabled = false;
        var postUrl = "";
        var csrfToken = "abcdef-XYZ-123";
        var ajaxBase = "/";
    </script>
    </head></html>"""
    open_fn = _fake_open(200, body)
    with _patch_opener(open_fn):
        token = fetch_csrf_token(_session(), "CVE-2026-12345")
    assert token == "abcdef-XYZ-123"
    assert open_fn.captured["url"] == "https://cveprocess.apache.org/cve5/CVE-2026-12345"


def test_fetch_csrf_token_raises_when_not_found():
    open_fn = _fake_open(200, b"<html>no token here</html>")
    with _patch_opener(open_fn), pytest.raises(CSRFNotFound):
        fetch_csrf_token(_session(), "CVE-2026-12345")


def test_update_record_happy_path_posts_json_with_csrf_header():
    page = b'<html><script>var csrfToken = "tok-1";</script></html>'
    saved = b'{"type": "saved"}'
    captured_calls: list[dict[str, Any]] = []

    def _open(req: Any, timeout: int = 30) -> _FakeResponse:
        body_str = "POST-BODY" if req.data else "GET-BODY"
        captured_calls.append(
            {
                "url": req.full_url,
                "method": req.get_method(),
                "headers": dict(req.header_items()),
                "body": req.data,
                "phase": body_str,
            }
        )
        if req.get_method() == "GET":
            return _FakeResponse(200, page)
        return _FakeResponse(200, saved)

    opener = MagicMock()
    opener.open = _open
    with patch.object(client_mod.urllib.request, "build_opener", return_value=opener):
        envelope = update_record(
            _session(),
            "CVE-2026-12345",
            {"cveMetadata": {"cveId": "CVE-2026-12345"}},
        )
    assert envelope == {"type": "saved"}
    # Two HTTP round-trips: GET for CSRF, then POST.
    assert [c["method"] for c in captured_calls] == ["GET", "POST"]
    post = captured_calls[1]
    assert post["url"] == "https://cveprocess.apache.org/cve5/CVE-2026-12345"
    headers_lower = {k.lower(): v for k, v in post["headers"].items()}
    assert headers_lower["csrf-token"] == "tok-1"
    assert headers_lower["content-type"] == "application/json"
    assert headers_lower["accept"] == "application/json"
    assert headers_lower["cookie"] == "connect.sid=s%3Aabc"
    assert json.loads(post["body"]) == {"cveMetadata": {"cveId": "CVE-2026-12345"}}


def test_update_record_validation_error_raises_record_save_failed():
    page = b'<html><script>var csrfToken = "tok-1";</script></html>'
    err = b'{"type": "err", "msg": "Document ID not valid"}'

    def _open(req: Any, timeout: int = 30) -> _FakeResponse:
        if req.get_method() == "GET":
            return _FakeResponse(200, page)
        return _FakeResponse(200, err)

    opener = MagicMock()
    opener.open = _open
    with (
        patch.object(client_mod.urllib.request, "build_opener", return_value=opener),
        pytest.raises(RecordSaveFailed, match="not valid"),
    ):
        update_record(_session(), "CVE-2026-12345", {"x": 1})


def test_update_record_csrf_failure_surfaces_as_api_error():
    """csurf returns 403 with an EBADCSRFTOKEN body — must surface as
    VulnogramAPIError with the body included so callers can debug."""
    page = b'<html><script>var csrfToken = "tok-1";</script></html>'

    def _open(req: Any, timeout: int = 30) -> _FakeResponse:
        if req.get_method() == "GET":
            return _FakeResponse(200, page)
        return _FakeResponse(403, b"ForbiddenError: invalid csrf token")

    opener = MagicMock()
    opener.open = _open
    with (
        patch.object(client_mod.urllib.request, "build_opener", return_value=opener),
        pytest.raises(VulnogramAPIError, match="403"),
    ):
        update_record(_session(), "CVE-2026-12345", {"x": 1})


def test_probe_valid():
    open_fn = _fake_open(200, b"<html>ok</html>")
    with _patch_opener(open_fn):
        assert probe(_session()) == "valid"


def test_probe_expired():
    open_fn = _fake_open(302, b"", {"Location": "https://oauth.apache.org/auth?state=x"})
    with _patch_opener(open_fn):
        assert probe(_session()) == "expired"


def test_probe_unexpected_status():
    open_fn = _fake_open(500, b"server error")
    with _patch_opener(open_fn):
        result = probe(_session())
    assert result.startswith("error: HTTP 500")


def test_probe_valid_on_non_login_redirect():
    # Vulnogram now 302-redirects /cve5/new to /allocatecve. The redirect is
    # NOT to oauth.apache.org / /users/login, so it indicates the session
    # passed auth — only the post-auth landing page changed.
    open_fn = _fake_open(302, b"", {"Location": "/allocatecve"})
    with _patch_opener(open_fn):
        assert probe(_session()) == "valid"
