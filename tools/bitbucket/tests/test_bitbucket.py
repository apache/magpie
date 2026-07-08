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
from magpie_bitbucket.normalize import pull_request, pull_request_discussion, pull_request_list, repository


@pytest.fixture
def cloud_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITBUCKET_KIND", "cloud")
    monkeypatch.setenv("BITBUCKET_CLOUD_USER", "alice@example.test")
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
    response.read.return_value = json.dumps(body).encode()
    return response


def mock_opener(mock_build_opener: MagicMock, *bodies: dict[str, Any]) -> MagicMock:
    opener = MagicMock()
    opener.open.side_effect = [
        MagicMock(
            __enter__=MagicMock(return_value=make_mock_response(body)), __exit__=MagicMock(return_value=None)
        )
        for body in bodies
    ]
    mock_build_opener.return_value = opener
    return opener


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


def test_make_auth_header_rejects_unknown_scheme(cloud_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITBUCKET_AUTH_SCHEME", "Digest")
    config = load_config()

    with pytest.raises(BitbucketError, match="BITBUCKET_AUTH_SCHEME must be 'Basic' or 'Bearer'"):
        make_auth_header(config)


def test_make_auth_header_bearer(datacenter_env: None) -> None:
    config = load_config()
    assert make_auth_header(config) == "Bearer token-123"


@patch("urllib.request.build_opener")
def test_cloud_get_repository_url(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(mock_build_opener, {"name": "Magpie", "slug": "magpie"})
    result = cloud.get_repository(load_config())

    request = opener.open.call_args.args[0]
    assert request.full_url == "https://api.bitbucket.org/2.0/repositories/apache/magpie"
    assert opener.open.call_args.kwargs["timeout"] == 30
    assert result["name"] == "Magpie"


@patch("urllib.request.build_opener")
def test_cloud_list_open_pull_requests_follows_next(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"id": 1, "title": "One"}],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests?page=2",
        },
        {"values": [{"id": 2, "title": "Two"}]},
    )
    result = cloud.list_open_pull_requests(load_config())

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert (
        first_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests?state=OPEN"
    )
    assert (
        second_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests?page=2"
    )
    assert [item["id"] for item in result["values"]] == [1, 2]


@patch("urllib.request.build_opener")
def test_cloud_get_pull_request_url(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(mock_build_opener, {"id": 7, "title": "Fix docs"})
    result = cloud.get_pull_request(load_config(), "7")

    request = opener.open.call_args.args[0]
    assert request.full_url == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7"
    assert result["title"] == "Fix docs"


@patch("urllib.request.build_opener")
def test_datacenter_get_repository_url(mock_build_opener: MagicMock, datacenter_env: None) -> None:
    opener = mock_opener(mock_build_opener, {"name": "Magpie", "slug": "magpie"})
    result = datacenter.get_repository(load_config())

    request = opener.open.call_args.args[0]
    assert request.full_url == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie"
    assert result["slug"] == "magpie"


@patch("urllib.request.build_opener")
def test_datacenter_list_open_pull_requests_follows_next_page_start(
    mock_build_opener: MagicMock,
    datacenter_env: None,
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {"values": [{"id": 1, "title": "One"}], "isLastPage": False, "nextPageStart": 25},
        {"values": [{"id": 2, "title": "Two"}], "isLastPage": True},
    )
    result = datacenter.list_open_pull_requests(load_config())

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert (
        first_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests?state=OPEN&start=0"
    )
    assert (
        second_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests?state=OPEN&start=25"
    )
    assert [item["id"] for item in result["values"]] == [1, 2]


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_url(mock_build_opener: MagicMock, datacenter_env: None) -> None:
    opener = mock_opener(mock_build_opener, {"id": 9, "title": "Fix tests"})
    result = datacenter.get_pull_request(load_config(), "9")

    request = opener.open.call_args.args[0]
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
    assert result["capabilities"]["issues"] == "not_implemented"


def test_normalize_datacenter_repository_accepts_string_default_branch() -> None:
    raw = {
        "id": 101,
        "name": "Magpie",
        "slug": "magpie",
        "public": False,
        "defaultBranch": "refs/heads/main",
        "links": {"self": [{"href": "https://bitbucket.example.test/projects/MAGPIE/repos/magpie"}]},
    }

    result = repository("datacenter", raw)

    assert result["backend"] == "bitbucket-datacenter"
    assert result["id"] == "101"
    assert result["is_private"] is True
    assert result["main_branch"] == "refs/heads/main"


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
    assert result["checks"] == "none"
    assert result["diff"] is None
    assert result["commits"] is None
    assert result["labels"] == ["bitbucket", "read-only", "partial-change-request"]


def test_normalize_datacenter_pull_request_timestamp() -> None:
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
    assert result["created"] == "2026-05-28T20:26:40Z"
    assert result["updated"] == "2026-05-28T20:26:41Z"


def test_normalize_pull_request_list() -> None:
    raw = {
        "values": [
            {"id": 1, "title": "One", "state": "OPEN"},
            {"id": 2, "title": "Two", "state": "MERGED"},
        ]
    }

    result = pull_request_list("cloud", raw)

    assert result["backend"] == "bitbucket-cloud"
    assert result["coverage"] == "read-only-partial-change-request"
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


@patch("urllib.request.build_opener")
def test_cloud_get_pull_request_discussion_follows_next(
    mock_build_opener: MagicMock,
    cloud_env: None,
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"id": 101, "content": {"raw": "First comment"}}],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/comments?page=2",
        },
        {"values": [{"id": 102, "content": {"raw": "Second comment"}}]},
    )

    result = cloud.get_pull_request_discussion(load_config(), "7")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert (
        first_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/comments"
    )
    assert (
        second_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/comments?page=2"
    )
    assert result["pull_request_id"] == "7"
    assert [item["id"] for item in result["values"]] == [101, 102]


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_discussion_follows_next_page_start(
    mock_build_opener: MagicMock,
    datacenter_env: None,
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {"values": [{"id": 201, "comment": {"text": "First"}}], "isLastPage": False, "nextPageStart": 25},
        {"values": [{"id": 202, "comment": {"text": "Second"}}], "isLastPage": True},
    )

    result = datacenter.get_pull_request_discussion(load_config(), "9")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert (
        first_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/activities?start=0"
    )
    assert (
        second_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/activities?start=25"
    )
    assert result["pull_request_id"] == "9"
    assert [item["id"] for item in result["values"]] == [201, 202]


def test_normalize_cloud_pull_request_discussion() -> None:
    raw = {
        "pull_request_id": "7",
        "values": [
            {
                "id": 101,
                "content": {"raw": "Looks good."},
                "user": {"display_name": "Alice"},
                "created_on": "2026-07-01T00:00:00Z",
                "updated_on": "2026-07-01T01:00:00Z",
                "state": "active",
                "deleted": False,
                "inline": {"path": "README.md", "to": 10},
            }
        ],
    }

    result = pull_request_discussion("cloud", raw)

    assert result["backend"] == "bitbucket-cloud"
    assert result["coverage"] == "partial-read-only"
    assert result["pull_request_id"] == "7"
    assert result["comments"][0]["id"] == "101"
    assert result["comments"][0]["author"] == "Alice"
    assert result["comments"][0]["body"] == "Looks good."
    assert result["comments"][0]["date"] == "2026-07-01T00:00:00Z"
    assert result["comments"][0]["kind"] == "comment"
    assert result["comments"][0]["deleted"] is False
    assert result["comments"][0]["inline"] == {"path": "README.md", "to_line": 10}
    assert result["participants"] == ["Alice"]
    assert result["unresolved_count"] is None


def test_normalize_datacenter_pull_request_discussion() -> None:
    raw = {
        "pull_request_id": "9",
        "values": [
            {
                "id": 201,
                "action": "COMMENTED",
                "createdDate": 1780000000000,
                "user": {"displayName": "Bob"},
                "comment": {
                    "id": 301,
                    "text": "Please update tests.",
                    "author": {"displayName": "Bob"},
                    "createdDate": 1780000000000,
                    "updatedDate": 1780000001000,
                    "anchor": {"path": "tests/test_bitbucket.py", "line": 42},
                    "deleted": False,
                },
            }
        ],
    }

    result = pull_request_discussion("datacenter", raw)

    assert result["backend"] == "bitbucket-datacenter"
    assert result["coverage"] == "partial-read-only"
    assert result["pull_request_id"] == "9"
    assert result["comments"][0]["id"] == "301"
    assert result["comments"][0]["author"] == "Bob"
    assert result["comments"][0]["body"] == "Please update tests."
    assert result["comments"][0]["created"] == "2026-05-28T20:26:40Z"
    assert result["comments"][0]["updated"] == "2026-05-28T20:26:41Z"
    assert result["comments"][0]["date"] == "2026-05-28T20:26:40Z"
    assert result["comments"][0]["kind"] == "comment"
    assert result["comments"][0]["deleted"] is False
    assert result["comments"][0]["inline"] == {"path": "tests/test_bitbucket.py", "to_line": 42}
    assert result["participants"] == ["Bob"]
    assert result["unresolved_count"] is None


@patch("magpie_bitbucket.cloud.get_pull_request_discussion")
def test_cli_pr_discussion_cloud(
    mock_get_pull_request_discussion: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_pull_request_discussion.return_value = {
        "pull_request_id": "7",
        "values": [{"id": 101, "content": {"raw": "Looks good."}}],
    }

    exit_code = main(["pr", "discussion", "7"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["pull_request_id"] == "7"
    assert output["comments"][0]["id"] == "101"
    assert output["comments"][0]["body"] == "Looks good."


@patch("magpie_bitbucket.cli.load_config")
def test_cli_pr_discussion_datacenter(
    mock_load_config: MagicMock,
    datacenter_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = load_config()
    mock_load_config.return_value = config

    with patch.object(datacenter, "get_pull_request_discussion") as mock_discussion:
        mock_discussion.return_value = {
            "pull_request_id": "9",
            "values": [
                {
                    "action": "COMMENTED",
                    "comment": {
                        "id": 1,
                        "text": "Looks good",
                        "author": {"displayName": "Asha"},
                    },
                }
            ],
        }

        exit_code = main(["pr", "discussion", "9"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    mock_discussion.assert_called_once_with(config, "9")
    assert exit_code == 0
    assert output["backend"] == "bitbucket-datacenter"
    assert output["comments"][0]["body"] == "Looks good"


def test_normalize_datacenter_discussion_includes_threaded_replies() -> None:
    raw = {
        "pull_request_id": "9",
        "values": [
            {
                "action": "COMMENTED",
                "comment": {
                    "id": 1,
                    "text": "Parent comment",
                    "author": {"displayName": "Asha"},
                    "createdDate": 1783428000000,
                    "comments": [
                        {
                            "id": 2,
                            "text": "Reply comment",
                            "author": {"displayName": "Ravi"},
                            "createdDate": 1783428300000,
                        }
                    ],
                },
            }
        ],
    }

    result = pull_request_discussion("datacenter", raw)

    assert [comment["body"] for comment in result["comments"]] == [
        "Parent comment",
        "Reply comment",
    ]
    assert result["comments"][1]["parent_id"] == "1"
    assert result["participants"] == ["Asha", "Ravi"]


def test_normalize_datacenter_discussion_filters_non_comment_activities() -> None:
    raw = {
        "pull_request_id": "9",
        "values": [
            {"id": 1, "action": "APPROVED", "user": {"displayName": "Reviewer"}},
            {
                "id": 2,
                "action": "COMMENTED",
                "comment": {
                    "id": 302,
                    "text": "Real comment.",
                    "author": {"displayName": "Alice"},
                    "createdDate": 1780000000000,
                },
            },
        ],
    }

    result = pull_request_discussion("datacenter", raw)

    assert len(result["comments"]) == 1
    assert result["comments"][0]["id"] == "302"
    assert result["comments"][0]["body"] == "Real comment."
    assert result["participants"] == ["Alice"]


def test_normalize_cloud_discussion_preserves_empty_raw_body() -> None:
    raw = {
        "pull_request_id": "7",
        "values": [
            {
                "id": 101,
                "content": {"raw": "", "markup": "markdown fallback", "html": "<p>fallback</p>"},
                "user": {"display_name": "Alice"},
            }
        ],
    }

    result = pull_request_discussion("cloud", raw)

    assert result["comments"][0]["body"] == ""


@patch("urllib.request.build_opener")
def test_cloud_discussion_rejects_next_url_host_change(
    mock_build_opener: MagicMock,
    cloud_env: None,
) -> None:
    mock_opener(
        mock_build_opener,
        {
            "values": [],
            "next": "https://evil.example.test/steal-token",
        },
    )

    with pytest.raises(BitbucketError, match="pagination URL changed scheme or host"):
        cloud.get_pull_request_discussion(load_config(), "7")


@patch("urllib.request.build_opener")
def test_cloud_discussion_rejects_repeated_next_url(
    mock_build_opener: MagicMock,
    cloud_env: None,
) -> None:
    repeated_url = "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/comments?page=2"
    mock_opener(
        mock_build_opener,
        {
            "values": [],
            "next": repeated_url,
        },
        {
            "values": [],
            "next": repeated_url,
        },
    )

    with pytest.raises(BitbucketError, match="pagination returned a repeated URL"):
        cloud.get_pull_request_discussion(load_config(), "7")


@patch("urllib.request.build_opener")
def test_datacenter_discussion_stops_on_non_advancing_next_page_start(
    mock_build_opener: MagicMock,
    datacenter_env: None,
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"id": 201, "comment": {"text": "First"}}],
            "isLastPage": False,
            "nextPageStart": 0,
        },
    )

    result = datacenter.get_pull_request_discussion(load_config(), "9")

    assert opener.open.call_count == 1
    assert result["values"][0]["id"] == 201
