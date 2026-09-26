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

import urllib.error
import urllib.request as _ur
from email.message import Message

import pytest

from magpie_gitlab.client import (
    GitLabConfig,
    GitLabError,
    _auth_headers,
    _build_opener,
    _SafeRedirectHandler,
    get_json,
    get_paged_json,
    get_project,
    load_config,
    quote_path,
    require,
)

from .conftest import build_mock_response

# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_default(monkeypatch):
    monkeypatch.delenv("GITLAB_INSTANCE_URL", raising=False)
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)
    monkeypatch.delenv("GITLAB_AUTH_SCHEME", raising=False)
    monkeypatch.setenv("GITLAB_TOKEN", "token")
    cfg = load_config()
    assert cfg.instance_url == "https://gitlab.com"
    assert cfg.token == "token"
    assert cfg.token_type == "bearer"
    assert cfg.auth_scheme == ""


def test_load_config_ci_job_token(monkeypatch):
    """CI_JOB_TOKEN should be used when GITLAB_TOKEN is absent."""
    monkeypatch.delenv("GITLAB_INSTANCE_URL", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("GITLAB_AUTH_SCHEME", raising=False)
    monkeypatch.setenv("CI_JOB_TOKEN", "ci-job-tok-456")
    cfg = load_config()
    assert cfg.token == "ci-job-tok-456"
    assert cfg.token_type == "job_token"


def test_load_config_gitlab_token_takes_precedence(monkeypatch):
    """GITLAB_TOKEN wins when both are set."""
    monkeypatch.delenv("GITLAB_INSTANCE_URL", raising=False)
    monkeypatch.delenv("GITLAB_AUTH_SCHEME", raising=False)
    monkeypatch.setenv("GITLAB_TOKEN", "pat-wins")
    monkeypatch.setenv("CI_JOB_TOKEN", "ci-loses")
    cfg = load_config()
    assert cfg.token == "pat-wins"
    assert cfg.token_type == "bearer"


def test_load_config_insecure_url(monkeypatch):
    monkeypatch.delenv("GITLAB_AUTH_SCHEME", raising=False)
    monkeypatch.setenv("GITLAB_TOKEN", "token")
    monkeypatch.setenv("GITLAB_INSTANCE_URL", "http://gitlab.insecure.com")
    with pytest.raises(
        GitLabError,
        match="Insecure instance URL scheme 'http': HTTPS is required",
    ):
        load_config()


def test_load_config_localhost_http_allowed(monkeypatch):
    """HTTP is allowed for localhost / 127.0.0.1 / ::1 (local dev / testing)."""
    monkeypatch.delenv("GITLAB_AUTH_SCHEME", raising=False)
    monkeypatch.setenv("GITLAB_TOKEN", "token")
    monkeypatch.setenv("GITLAB_INSTANCE_URL", "http://localhost:8080")
    cfg = load_config()
    assert cfg.instance_url == "http://localhost:8080"

    monkeypatch.setenv("GITLAB_INSTANCE_URL", "http://127.0.0.1:8080")
    cfg2 = load_config()
    assert cfg2.instance_url == "http://127.0.0.1:8080"


def test_load_config_localhost_non_http_rejected(monkeypatch):
    """Non-HTTP schemes on localhost (ftp, file, etc.) must be rejected."""
    monkeypatch.delenv("GITLAB_AUTH_SCHEME", raising=False)
    monkeypatch.setenv("GITLAB_TOKEN", "token")
    monkeypatch.setenv("GITLAB_INSTANCE_URL", "ftp://localhost:21")
    with pytest.raises(
        GitLabError,
        match="Insecure instance URL scheme 'ftp': HTTPS is required",
    ):
        load_config()

    monkeypatch.setenv("GITLAB_INSTANCE_URL", "file://localhost/tmp")
    with pytest.raises(
        GitLabError,
        match="Insecure instance URL scheme 'file': HTTPS is required",
    ):
        load_config()


def test_load_config_custom(mock_env):
    cfg = load_config()
    assert cfg.instance_url == "https://gitlab.example.com"
    assert cfg.token == "glpat-test123"


# ---------------------------------------------------------------------------
# quote_path / require
# ---------------------------------------------------------------------------


def test_quote_path():
    assert quote_path("group/project") == "group%2Fproject"


def test_require():
    assert require("val", "VAR") == "val"
    with pytest.raises(GitLabError, match="VAR is required"):
        require(None, "VAR")
    with pytest.raises(GitLabError, match="VAR is required"):
        require("", "VAR")


# ---------------------------------------------------------------------------
# _build_opener (unmocked)
# ---------------------------------------------------------------------------


def test_build_opener_installs_safe_redirect_handler():
    opener = _build_opener()
    handlers = getattr(opener, "handlers", [])
    assert any(isinstance(h, _SafeRedirectHandler) for h in handlers)


# ---------------------------------------------------------------------------
# SafeRedirectHandler
# ---------------------------------------------------------------------------


def test_safe_redirect_blocks_https_to_http():
    """HTTPS->HTTP downgrade must be blocked."""
    handler = _SafeRedirectHandler()
    req = _ur.Request("https://gitlab.example.com/api")
    with pytest.raises(GitLabError, match="HTTPS-to-HTTP downgrade"):
        handler.redirect_request(req, None, 302, "Found", {}, "http://gitlab.example.com/api")


def test_safe_redirect_blocks_cross_origin():
    """Cross-origin host redirect must be blocked."""
    handler = _SafeRedirectHandler()
    req = _ur.Request("https://gitlab.example.com/api")
    with pytest.raises(GitLabError, match="cross-origin redirect"):
        handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example.com/steal")


def test_safe_redirect_blocks_port_mismatch():
    """Cross-port redirect on same host must be blocked."""
    handler = _SafeRedirectHandler()
    req = _ur.Request("https://gitlab.example.com/api")
    with pytest.raises(GitLabError, match="cross-origin redirect"):
        handler.redirect_request(req, None, 302, "Found", {}, "https://gitlab.example.com:8443/api")


def test_safe_redirect_allows_same_origin():
    """Same-origin same-scheme absolute redirect should be allowed."""
    handler = _SafeRedirectHandler()
    req = _ur.Request("https://gitlab.example.com/api/old")
    result = handler.redirect_request(req, None, 302, "Found", {}, "https://gitlab.example.com/api/new")
    assert result is not None
    assert result.full_url == "https://gitlab.example.com/api/new"


def test_safe_redirect_allows_relative_same_origin():
    """Relative redirect on same origin should be resolved and allowed."""
    handler = _SafeRedirectHandler()
    req = _ur.Request("https://gitlab.example.com/api/v4/projects")
    result = handler.redirect_request(req, None, 302, "Found", {}, "/api/v4/projects/1")
    assert result is not None
    assert result.full_url == "https://gitlab.example.com/api/v4/projects/1"


# ---------------------------------------------------------------------------
# _auth_headers
# ---------------------------------------------------------------------------


def test_auth_headers_unauthenticated():
    cfg = GitLabConfig(token=None, instance_url="https://gitlab.example.com")
    headers = _auth_headers(cfg)
    assert headers == {"Accept": "application/json"}


def test_auth_headers_glpat_default():
    cfg = GitLabConfig(token="glpat-secret", instance_url="https://gitlab.example.com")
    headers = _auth_headers(cfg)
    assert headers.get("PRIVATE-TOKEN") == "glpat-secret"
    assert "Authorization" not in headers


def test_auth_headers_bearer_default():
    cfg = GitLabConfig(token="oauth-token", instance_url="https://gitlab.example.com")
    headers = _auth_headers(cfg)
    assert headers.get("Authorization") == "Bearer oauth-token"
    assert "PRIVATE-TOKEN" not in headers


def test_auth_headers_job_token_default():
    cfg = GitLabConfig(token="job-tok", instance_url="https://gitlab.example.com", token_type="job_token")
    headers = _auth_headers(cfg)
    assert headers.get("JOB-TOKEN") == "job-tok"


def test_auth_headers_explicit_scheme_bearer():
    """Explicit GITLAB_AUTH_SCHEME=Bearer overrides glpat- default."""
    cfg = GitLabConfig(
        token="glpat-token",
        instance_url="https://gitlab.example.com",
        auth_scheme="Bearer",
    )
    headers = _auth_headers(cfg)
    assert headers.get("Authorization") == "Bearer glpat-token"
    assert "PRIVATE-TOKEN" not in headers


def test_auth_headers_explicit_scheme_private_token():
    cfg = GitLabConfig(
        token="custom-pat",
        instance_url="https://gitlab.example.com",
        auth_scheme="Private-Token",
    )
    headers = _auth_headers(cfg)
    assert headers.get("PRIVATE-TOKEN") == "custom-pat"


def test_auth_headers_explicit_scheme_job_token():
    cfg = GitLabConfig(
        token="custom-job-tok",
        instance_url="https://gitlab.example.com",
        auth_scheme="Job-Token",
    )
    headers = _auth_headers(cfg)
    assert headers.get("JOB-TOKEN") == "custom-job-tok"


def test_auth_headers_invalid_scheme_raises():
    cfg = GitLabConfig(
        token="token",
        instance_url="https://gitlab.example.com",
        auth_scheme="Basic",
    )
    with pytest.raises(GitLabError, match="Unsupported GITLAB_AUTH_SCHEME: 'Basic'"):
        _auth_headers(cfg)


# ---------------------------------------------------------------------------
# get_json
# ---------------------------------------------------------------------------


def test_get_json_unauthenticated(mock_urlopen, monkeypatch):
    """Unauthenticated public reads should succeed with no auth header."""
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)
    monkeypatch.delenv("GITLAB_AUTH_SCHEME", raising=False)
    monkeypatch.setenv("GITLAB_INSTANCE_URL", "https://gitlab.example.com")
    mock_urlopen.return_value = build_mock_response({"public": "repo"})
    cfg = load_config()
    res = get_json("https://gitlab.example.com/api/v4/projects/public%2Frepo", cfg)
    assert res == {"public": "repo"}
    req = mock_urlopen.call_args[0][0]
    assert "Authorization" not in req.headers
    assert "Private-token" not in req.headers
    assert "Job-token" not in req.headers
    assert req.headers.get("Accept") == "application/json"


def test_get_json_http_error(mock_urlopen, mock_env):
    mock_urlopen.side_effect = urllib.error.HTTPError("url", 404, "Not Found", Message(), None)
    cfg = load_config()
    with pytest.raises(GitLabError, match="HTTP 404: Not Found"):
        get_json("https://gitlab.example.com/api", cfg)


# ---------------------------------------------------------------------------
# get_paged_json -- pagination & bounded limit
# ---------------------------------------------------------------------------


def test_get_paged_json_single_page(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"id": 1}], headers={"X-Next-Page": ""})
    cfg = load_config()
    items = get_paged_json("https://gitlab.example.com/api/v4/projects/test/issues", cfg)
    assert items == [{"id": 1}]
    assert mock_urlopen.call_count == 1


def test_get_paged_json_multi_page(mock_urlopen, mock_env):
    page1 = build_mock_response([{"id": 1}], headers={"X-Next-Page": "2"})
    page2 = build_mock_response([{"id": 2}], headers={"X-Next-Page": ""})
    mock_urlopen.side_effect = [page1, page2]

    cfg = load_config()
    items = get_paged_json("https://gitlab.example.com/api/v4/projects/test/issues?state=opened", cfg)
    assert items == [{"id": 1}, {"id": 2}]
    assert mock_urlopen.call_count == 2
    # Verify second request preserved query params
    req2 = mock_urlopen.call_args_list[1][0][0]
    assert "state=opened" in req2.full_url
    assert "page=2" in req2.full_url


def test_get_paged_json_max_pages(mock_urlopen, mock_env, capsys):
    """Pagination must halt when max_pages ceiling is reached."""
    page1 = build_mock_response([{"id": 1}], headers={"X-Next-Page": "2"})
    page2 = build_mock_response([{"id": 2}], headers={"X-Next-Page": "3"})
    page3 = build_mock_response([{"id": 3}], headers={"X-Next-Page": ""})
    mock_urlopen.side_effect = [page1, page2, page3]

    cfg = load_config()
    items = get_paged_json("https://gitlab.example.com/api/v4/projects/test/issues", cfg, max_pages=2)
    assert items == [{"id": 1}, {"id": 2}]
    assert mock_urlopen.call_count == 2
    err = capsys.readouterr().err
    assert "Results capped at 2 items (2 pages)" in err


def test_get_paged_json_with_limit_fewer_than_page(mock_urlopen, mock_env, capsys):
    """Limit fewer than page size fetches only 1 page, caps items, and emits notice if more exist."""
    data = [{"id": i} for i in range(100)]
    mock_urlopen.return_value = build_mock_response(data, headers={"X-Next-Page": "2"})

    cfg = load_config()
    items = get_paged_json("https://gitlab.example.com/api/v4/projects/test/issues", cfg, limit=5)
    assert len(items) == 5
    assert mock_urlopen.call_count == 1
    err = capsys.readouterr().err
    assert "Results capped at 5 items; use --limit to fetch more." in err


def test_get_paged_json_with_limit_multi_page(mock_urlopen, mock_env):
    """Limit spanning multiple pages only fetches the required number of pages."""
    page1 = build_mock_response([{"id": i} for i in range(100)], headers={"X-Next-Page": "2"})
    page2 = build_mock_response([{"id": i} for i in range(100, 200)], headers={"X-Next-Page": "3"})
    mock_urlopen.side_effect = [page1, page2]

    cfg = load_config()
    items = get_paged_json("https://gitlab.example.com/api/v4/projects/test/issues", cfg, limit=150)
    assert len(items) == 150
    assert mock_urlopen.call_count == 2


def test_get_paged_json_non_list_single(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response({"single": "object"})
    cfg = load_config()
    items = get_paged_json("https://gitlab.example.com/api/v4/projects/test/resource", cfg)
    assert items == [{"single": "object"}]


def test_get_paged_json_non_list_subsequent_raises(mock_urlopen, mock_env):
    page1 = build_mock_response([{"id": 1}], headers={"X-Next-Page": "2"})
    page2 = build_mock_response({"error": "invalid"}, headers={"X-Next-Page": ""})
    mock_urlopen.side_effect = [page1, page2]

    cfg = load_config()
    with pytest.raises(GitLabError, match="Unexpected non-list response"):
        get_paged_json("https://gitlab.example.com/api/v4/projects/test/issues", cfg)


# ---------------------------------------------------------------------------
# get_project
# ---------------------------------------------------------------------------


def test_get_project(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response({"id": 42, "name": "my-project"})
    cfg = load_config()
    project = get_project("group/my-project", cfg)
    assert project == {"id": 42, "name": "my-project"}
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == "https://gitlab.example.com/api/v4/projects/group%2Fmy-project"
