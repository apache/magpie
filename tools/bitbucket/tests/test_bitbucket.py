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

from magpie_bitbucket import cloud, datacenter
from magpie_bitbucket.cli import main
from magpie_bitbucket.client import BitbucketError, load_config, make_auth_header
from magpie_bitbucket.normalize import pull_request, pull_request_list, repository


@pytest.fixture
def cloud_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITBUCKET_KIND", "cloud")
    monkeypatch.setenv("BITBUCKET_USERNAME", "alice")
    monkeypatch.setenv("BITBUCKET_TOKEN", "token-123")
    monkeypatch.setenv("BITBUCKET_WORKSPACE", "apache")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "magpie")


@pytest.fixture
def datacenter_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITBUCKET_KIND", "datacenter")
    monkeypatch.setenv("BITBUCKET_TOKEN", "token-123")
    monkeypatch.setenv("BITBUCKET_BASE_URL", "https://bitbucket.example.test/")
    monkeypatch.setenv("BITBUCKET_PROJECT_KEY", "MAGPIE")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "magpie")


def make_mock_response(body: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(body).encode("utf-8")
    return response


def test_load_config_defaults_to_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BITBUCKET_KIND", raising=False)
    config = load_config()
    assert config.kind == "cloud"
    assert config.auth_scheme == "Basic"


def test_load_config_rejects_unknown_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITBUCKET_KIND", "server")
    with pytest.raises(BitbucketError, match="BITBUCKET_KIND must be 'cloud' or 'datacenter'"):
        load_config()


def test_make_auth_header_basic(cloud_env: None) -> None:
    config = load_config()
    assert make_auth_header(config).startswith("Basic ")


def test_make_auth_header_bearer(datacenter_env: None) -> None:
    config = load_config()
    assert make_auth_header(config) == "Bearer token-123"


@patch("urllib.request.urlopen")
def test_cloud_get_repository_url(mock_urlopen: MagicMock, cloud_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        {"name": "Magpie", "slug": "magpie"}
    )
    result = cloud.get_repository(load_config())

    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://api.bitbucket.org/2.0/repositories/apache/magpie"
    assert result["name"] == "Magpie"


@patch("urllib.request.urlopen")
def test_cloud_list_open_pull_requests_url(mock_urlopen: MagicMock, cloud_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response({"values": []})
    result = cloud.list_open_pull_requests(load_config())

    request = mock_urlopen.call_args.args[0]
    assert (
        request.full_url == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests?state=OPEN"
    )
    assert result == {"values": []}


@patch("urllib.request.urlopen")
def test_cloud_get_pull_request_url(mock_urlopen: MagicMock, cloud_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response({"id": 7, "title": "Fix docs"})
    result = cloud.get_pull_request(load_config(), "7")

    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7"
    assert result["title"] == "Fix docs"


@patch("urllib.request.urlopen")
def test_datacenter_get_repository_url(mock_urlopen: MagicMock, datacenter_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        {"name": "Magpie", "slug": "magpie"}
    )
    result = datacenter.get_repository(load_config())

    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie"
    assert result["slug"] == "magpie"


@patch("urllib.request.urlopen")
def test_datacenter_list_open_pull_requests_url(mock_urlopen: MagicMock, datacenter_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response({"values": []})
    result = datacenter.list_open_pull_requests(load_config())

    request = mock_urlopen.call_args.args[0]
    assert (
        request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests?state=OPEN"
    )
    assert result == {"values": []}


@patch("urllib.request.urlopen")
def test_datacenter_get_pull_request_url(mock_urlopen: MagicMock, datacenter_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response({"id": 9, "title": "Fix tests"})
    result = datacenter.get_pull_request(load_config(), "9")

    request = mock_urlopen.call_args.args[0]
    assert (
        request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9"
    )
    assert result["title"] == "Fix tests"


def test_normalize_cloud_repository() -> None:
    raw = {
        "uuid": "{abc}",
        "name": "Magpie",
        "slug": "magpie",
        "description": "Agent-assisted maintainership",
        "is_private": False,
        "mainbranch": {"name": "main"},
        "links": {"html": {"href": "https://bitbucket.org/apache/magpie"}},
    }

    result = repository("cloud", raw)

    assert result["backend"] == "bitbucket-cloud"
    assert result["id"] == "{abc}"
    assert result["main_branch"] == "main"
    assert result["links"]["html"] == "https://bitbucket.org/apache/magpie"


def test_normalize_datacenter_repository() -> None:
    raw = {
        "id": 101,
        "name": "Magpie",
        "slug": "magpie",
        "public": False,
        "defaultBranch": {"displayId": "main"},
        "links": {"self": [{"href": "https://bitbucket.example.test/projects/MAGPIE/repos/magpie"}]},
    }

    result = repository("datacenter", raw)

    assert result["backend"] == "bitbucket-datacenter"
    assert result["id"] == "101"
    assert result["is_private"] is True
    assert result["main_branch"] == "main"


def test_normalize_cloud_pull_request() -> None:
    raw = {
        "id": 12,
        "title": "Fix docs",
        "state": "OPEN",
        "created_on": "2026-07-01T00:00:00Z",
        "updated_on": "2026-07-02T00:00:00Z",
        "author": {"display_name": "Alice"},
        "source": {"branch": {"name": "fix-docs"}},
        "destination": {"branch": {"name": "main"}},
        "links": {"html": {"href": "https://bitbucket.org/apache/magpie/pull-requests/12"}},
        "description": "Updates docs.",
    }

    result = pull_request("cloud", raw)

    assert result["backend"] == "bitbucket-cloud"
    assert result["id"] == "12"
    assert result["state"] == "open"
    assert result["author"] == "Alice"
    assert result["source"] == "fix-docs"
    assert result["target"] == "main"
    assert result["mergeable"] == "unknown"
    assert result["checks"] == []


def test_normalize_datacenter_pull_request() -> None:
    raw = {
        "id": 13,
        "title": "Fix tests",
        "state": "OPEN",
        "createdDate": 1780000000000,
        "updatedDate": 1780000001000,
        "author": {"user": {"displayName": "Bob"}},
        "fromRef": {"displayId": "fix-tests"},
        "toRef": {"displayId": "main"},
        "links": {
            "self": [{"href": "https://bitbucket.example.test/projects/MAGPIE/repos/magpie/pull-requests/13"}]
        },
        "description": "Updates tests.",
    }

    result = pull_request("datacenter", raw)

    assert result["backend"] == "bitbucket-datacenter"
    assert result["id"] == "13"
    assert result["state"] == "open"
    assert result["author"] == "Bob"
    assert result["source"] == "fix-tests"
    assert result["target"] == "main"


def test_normalize_pull_request_list() -> None:
    raw = {
        "values": [
            {"id": 1, "title": "One", "state": "OPEN"},
            {"id": 2, "title": "Two", "state": "MERGED"},
        ]
    }

    result = pull_request_list("cloud", raw)

    assert result["backend"] == "bitbucket-cloud"
    assert [item["id"] for item in result["pull_requests"]] == ["1", "2"]
    assert [item["state"] for item in result["pull_requests"]] == ["open", "merged"]


@patch("magpie_bitbucket.cloud.get_repository")
def test_cli_auth_check_cloud(
    mock_get_repository: MagicMock, cloud_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_get_repository.return_value = {
        "uuid": "{abc}",
        "name": "Magpie",
        "slug": "magpie",
    }

    exit_code = main(["auth-check"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["ok"] is True
    assert output["backend"] == "bitbucket-cloud"
    assert output["repository"]["name"] == "Magpie"


@patch("magpie_bitbucket.cloud.list_open_pull_requests")
def test_cli_pr_list_open_cloud(
    mock_list_open_pull_requests: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_list_open_pull_requests.return_value = {"values": [{"id": 1, "title": "One", "state": "OPEN"}]}

    exit_code = main(["pr", "list-open"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["pull_requests"][0]["id"] == "1"
    assert output["pull_requests"][0]["state"] == "open"
