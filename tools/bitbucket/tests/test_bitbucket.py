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
import urllib.request
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from magpie_bitbucket import cloud, datacenter
from magpie_bitbucket.cli import main
from magpie_bitbucket.client import BitbucketError, SameHostRedirectHandler, load_config, make_auth_header
from magpie_bitbucket.normalize import (
    issue,
    issue_attachments,
    issue_comments,
    issue_list,
    pull_request,
    pull_request_commits,
    pull_request_diff,
    pull_request_discussion,
    pull_request_list,
    pull_request_merge_checks,
    pull_request_reviews,
    pull_request_status,
    repository,
    repository_restrictions,
)


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


def make_mock_text_response(
    body: str,
    content_type: str = "text/x-diff",
    url: str = "https://bitbucket.example.test/diff",
) -> MagicMock:
    response = MagicMock()
    response.read.return_value = body.encode()
    response.headers.get_content_charset.return_value = "utf-8"
    response.headers.get.return_value = content_type
    response.geturl.return_value = url
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


def urllib_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={"Authorization": "Bearer token-123"},
        method="GET",
    )


def test_same_host_redirect_handler_allows_same_origin() -> None:
    handler = SameHostRedirectHandler()
    request = urllib_request("https://bitbucket.example.test/rest/api/1.0/foo")

    redirected = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://bitbucket.example.test/rest/api/1.0/bar",
    )

    assert redirected is not None
    assert redirected.full_url == "https://bitbucket.example.test/rest/api/1.0/bar"


def test_same_host_redirect_handler_rejects_different_host() -> None:
    handler = SameHostRedirectHandler()
    request = urllib_request("https://bitbucket.example.test/rest/api/1.0/foo")

    with pytest.raises(BitbucketError, match="refusing to forward credentials"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://evil.example.test/rest/api/1.0/bar",
        )


def test_same_host_redirect_handler_rejects_different_port() -> None:
    handler = SameHostRedirectHandler()
    request = urllib_request("https://bitbucket.example.test:8443/rest/api/1.0/foo")

    with pytest.raises(BitbucketError, match="refusing to forward credentials"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://bitbucket.example.test:9443/rest/api/1.0/bar",
        )


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


@patch("urllib.request.build_opener")
def test_cloud_get_pull_request_status_follows_next(
    mock_build_opener: MagicMock,
    cloud_env: None,
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"key": "build", "state": "SUCCESSFUL"}],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/statuses?page=2",
        },
        {"values": [{"key": "lint", "state": "INPROGRESS"}]},
    )

    result = cloud.get_pull_request_status(load_config(), "7")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert (
        first_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/statuses"
    )
    assert (
        second_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/statuses?page=2"
    )
    assert result["pull_request_id"] == "7"
    assert [item["key"] for item in result["values"]] == ["build", "lint"]


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_status_uses_latest_commit_and_paginates(
    mock_build_opener: MagicMock,
    datacenter_env: None,
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {"id": 9, "fromRef": {"latestCommit": "def456"}},
        {"values": [{"key": "build", "state": "SUCCESSFUL"}], "isLastPage": False, "nextPageStart": 25},
        {"values": [{"key": "lint", "state": "FAILED"}], "isLastPage": True},
    )

    result = datacenter.get_pull_request_status(load_config(), "9")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    third_request = opener.open.call_args_list[2].args[0]
    assert (
        first_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9"
    )
    assert (
        second_request.full_url
        == "https://bitbucket.example.test/rest/build-status/1.0/commits/def456?start=0"
    )
    assert (
        third_request.full_url
        == "https://bitbucket.example.test/rest/build-status/1.0/commits/def456?start=25"
    )
    assert result["commit"] == "def456"
    assert [item["key"] for item in result["values"]] == ["build", "lint"]


def test_normalize_cloud_pull_request_status() -> None:
    raw = {
        "pull_request_id": "7",
        "commit": "abc123",
        "values": [
            {
                "key": "build",
                "name": "Build",
                "state": "SUCCESSFUL",
                "url": "https://ci.example.test/build/1",
                "description": "Build passed",
                "created_on": "2026-07-09T10:00:00+00:00",
                "updated_on": "2026-07-09T10:02:00+00:00",
            }
        ],
    }

    result = pull_request_status("cloud", raw)

    assert result["backend"] == "bitbucket-cloud"
    assert result["coverage"] == "partial-read-only"
    assert result["pull_request_id"] == "7"
    assert result["commit"] == "abc123"
    assert result["state"] == "unknown"
    assert result["checks"] == "passing"
    assert result["mergeable"] == "unknown"
    assert result["check_details"][0]["key"] == "build"
    assert result["check_details"][0]["state"] == "success"
    assert result["check_details"][0]["url"] == "https://ci.example.test/build/1"


def test_normalize_datacenter_pull_request_status_failure() -> None:
    raw = {
        "pull_request_id": "9",
        "commit": "def456",
        "values": [
            {
                "key": "build",
                "name": "Build",
                "state": "FAILED",
                "url": "https://ci.example.test/build/2",
                "description": "Build failed",
                "dateAdded": 1783428000000,
                "dateUpdated": 1783428300000,
            }
        ],
    }

    result = pull_request_status("datacenter", raw)

    assert result["backend"] == "bitbucket-datacenter"
    assert result["pull_request_id"] == "9"
    assert result["commit"] == "def456"
    assert result["state"] == "unknown"
    assert result["checks"] == "failing"
    assert result["mergeable"] == "unknown"
    assert result["check_details"][0]["state"] == "failure"
    assert result["check_details"][0]["created"] == "2026-07-07T12:40:00Z"
    assert result["check_details"][0]["updated"] == "2026-07-07T12:45:00Z"


@patch("urllib.request.build_opener")
def test_cloud_get_pull_request_reviews_url(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(
        mock_build_opener,
        {"id": 7, "reviewers": [{"display_name": "Reviewer One"}]},
        {
            "values": [
                {
                    "approval": {
                        "user": {"display_name": "Reviewer One"},
                        "date": "2026-07-01T00:00:00+00:00",
                    }
                }
            ]
        },
    )

    result = cloud.get_pull_request_reviews(load_config(), "7")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert first_request.full_url == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7"
    assert (
        second_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/activity"
    )
    assert result["pull_request"]["id"] == 7
    assert result["values"][0]["approval"]["user"]["display_name"] == "Reviewer One"


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_reviews_url(mock_build_opener: MagicMock, datacenter_env: None) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "id": 9,
            "reviewers": [
                {
                    "user": {"displayName": "Reviewer One"},
                    "approved": True,
                    "status": "APPROVED",
                }
            ],
        },
        {
            "values": [
                {
                    "action": "APPROVED",
                    "user": {"displayName": "Reviewer One"},
                    "createdDate": 1710000000000,
                }
            ],
            "isLastPage": True,
        },
    )

    result = datacenter.get_pull_request_reviews(load_config(), "9")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert (
        first_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9"
    )
    assert (
        second_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/activities?start=0"
    )
    assert result["pull_request"]["reviewers"][0]["user"]["displayName"] == "Reviewer One"
    assert result["values"][0]["action"] == "APPROVED"


def test_normalize_pull_request_reviews_cloud() -> None:
    normalized = pull_request_reviews(
        "cloud",
        {
            "pull_request_id": "7",
            "pull_request": {"reviewers": [{"display_name": "Reviewer One"}]},
            "values": [
                {
                    "approval": {
                        "user": {"display_name": "Reviewer One"},
                        "date": "2026-07-01T00:00:00+00:00",
                    }
                },
                {
                    "changes_requested": {
                        "user": {"display_name": "Reviewer Two"},
                        "date": "2026-07-02T00:00:00+00:00",
                    }
                },
            ],
        },
    )

    assert normalized["backend"] == "bitbucket-cloud"
    assert normalized["review_decision"] == "changes_requested"
    assert normalized["reviewers"][0]["user"] == "Reviewer One"
    assert normalized["approvals"][0]["author"] == "Reviewer One"
    assert normalized["changes_requested"][0]["author"] == "Reviewer Two"


def test_normalize_pull_request_reviews_datacenter() -> None:
    normalized = pull_request_reviews(
        "datacenter",
        {
            "pull_request_id": "9",
            "pull_request": {
                "reviewers": [
                    {
                        "user": {"displayName": "Reviewer One"},
                        "approved": True,
                        "status": "APPROVED",
                    }
                ]
            },
            "values": [
                {
                    "action": "APPROVED",
                    "user": {"displayName": "Reviewer One"},
                    "createdDate": 1710000000000,
                }
            ],
        },
    )

    assert normalized["backend"] == "bitbucket-datacenter"
    assert normalized["review_decision"] == "approved"
    assert normalized["reviewers"][0]["user"] == "Reviewer One"
    assert normalized["approvals"][0]["author"] == "Reviewer One"


@patch("urllib.request.build_opener")
def test_cloud_get_pull_request_reviews_follows_next(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(
        mock_build_opener,
        {"id": 7, "reviewers": [{"display_name": "Reviewer One"}]},
        {
            "values": [
                {"approval": {"user": {"display_name": "Reviewer One"}, "date": "2026-07-01T00:00:00+00:00"}}
            ],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/activity?page=2",
        },
        {
            "values": [
                {
                    "changes_requested": {
                        "user": {"display_name": "Reviewer Two"},
                        "date": "2026-07-02T00:00:00+00:00",
                    }
                }
            ]
        },
    )

    result = cloud.get_pull_request_reviews(load_config(), "7")

    third_request = opener.open.call_args_list[2].args[0]
    assert (
        third_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/activity?page=2"
    )
    assert len(result["values"]) == 2


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_reviews_paginates(
    mock_build_opener: MagicMock, datacenter_env: None
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {"id": 9, "reviewers": []},
        {
            "values": [
                {"action": "APPROVED", "user": {"displayName": "Reviewer One"}, "createdDate": 1710000000000}
            ],
            "isLastPage": False,
            "nextPageStart": 25,
        },
        {
            "values": [
                {
                    "action": "NEEDS_WORK",
                    "user": {"displayName": "Reviewer Two"},
                    "createdDate": 1710000100000,
                }
            ],
            "isLastPage": True,
        },
    )

    result = datacenter.get_pull_request_reviews(load_config(), "9")

    third_request = opener.open.call_args_list[2].args[0]
    assert (
        third_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/activities?start=25"
    )
    assert len(result["values"]) == 2


def test_normalize_pull_request_reviews_prefers_current_approval_over_old_changes_requested() -> None:
    normalized = pull_request_reviews(
        "cloud",
        {
            "pull_request_id": "7",
            "pull_request": {
                "reviewers": [
                    {
                        "display_name": "Reviewer One",
                        "approved": True,
                    }
                ]
            },
            "values": [
                {
                    "changes_requested": {
                        "user": {"display_name": "Reviewer One"},
                        "date": "2026-07-01T00:00:00+00:00",
                    }
                }
            ],
        },
    )

    assert normalized["review_decision"] == "approved"
    assert normalized["approvals"][0]["author"] == "Reviewer One"
    assert normalized["changes_requested"] == []


def test_normalize_pull_request_reviews_datacenter_needs_work_is_not_pending_request() -> None:
    normalized = pull_request_reviews(
        "datacenter",
        {
            "pull_request_id": "9",
            "pull_request": {
                "reviewers": [
                    {
                        "user": {"displayName": "Reviewer One"},
                        "status": "NEEDS_WORK",
                    }
                ]
            },
            "values": [],
        },
    )

    assert normalized["review_decision"] == "changes_requested"
    assert normalized["changes_requested"][0]["author"] == "Reviewer One"
    assert normalized["review_requests"] == []


def test_normalize_pull_request_reviews_cloud_pending_reviewer_survives_participant_merge() -> None:
    # A requested reviewer who has not acted appears in BOTH reviewers[] (pending)
    # and participants[] (approved:false, state:null → "unknown"). The participant
    # merge must not downgrade the pending request to "unknown", or the reviewer
    # drops out of review_requests and review_decision collapses to "unknown".
    normalized = pull_request_reviews(
        "cloud",
        {
            "pull_request_id": "7",
            "pull_request": {
                "reviewers": [{"display_name": "Reviewer One"}],
                "participants": [
                    {
                        "user": {"display_name": "Reviewer One"},
                        "role": "REVIEWER",
                        "approved": False,
                        "state": None,
                    }
                ],
            },
            "values": [],
        },
    )

    assert normalized["review_decision"] == "review_required"
    assert [r["user"] for r in normalized["review_requests"]] == ["Reviewer One"]
    assert [r["review_state"] for r in normalized["reviewers"]] == ["pending"]


def test_normalize_pull_request_reviews_cloud_participant_approval_refines_pending() -> None:
    # The complement of the case above: when the participant carries a definite
    # signal (approved), it SHOULD refine the pending request to approved.
    normalized = pull_request_reviews(
        "cloud",
        {
            "pull_request_id": "7",
            "pull_request": {
                "reviewers": [{"display_name": "Reviewer One"}],
                "participants": [
                    {"user": {"display_name": "Reviewer One"}, "role": "REVIEWER", "approved": True}
                ],
            },
            "values": [],
        },
    )

    assert normalized["review_decision"] == "approved"
    assert normalized["approvals"][0]["author"] == "Reviewer One"
    assert normalized["review_requests"] == []


def test_normalize_pull_request_reviews_latest_event_overrides_old_request_changes() -> None:
    normalized = pull_request_reviews(
        "cloud",
        {
            "pull_request_id": "7",
            "pull_request": {},
            "values": [
                {
                    "changes_requested": {
                        "user": {"display_name": "Reviewer One"},
                        "date": "2026-07-01T00:00:00+00:00",
                    }
                },
                {
                    "approval": {
                        "user": {"display_name": "Reviewer One"},
                        "date": "2026-07-02T00:00:00+00:00",
                    }
                },
            ],
        },
    )

    assert normalized["review_decision"] == "approved"
    assert normalized["approvals"][0]["author"] == "Reviewer One"
    assert normalized["changes_requested"] == []


def test_normalize_pull_request_reviews_approval_removed_clears_fallback_approval() -> None:
    normalized = pull_request_reviews(
        "datacenter",
        {
            "pull_request_id": "9",
            "pull_request": {},
            "values": [
                {
                    "action": "APPROVED",
                    "user": {"displayName": "Reviewer One"},
                    "createdDate": 1710000000000,
                },
                {
                    "action": "UNAPPROVED",
                    "user": {"displayName": "Reviewer One"},
                    "createdDate": 1710000100000,
                },
            ],
        },
    )

    assert normalized["review_decision"] == "review_required"
    assert normalized["approvals"] == []
    assert normalized["changes_requested"] == []


def test_cli_pr_reviews_cloud(cloud_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "magpie_bitbucket.cloud.get_pull_request_reviews",
        return_value={
            "pull_request_id": "7",
            "pull_request": {"reviewers": [{"display_name": "Reviewer One"}]},
            "values": [
                {
                    "approval": {
                        "user": {"display_name": "Reviewer One"},
                        "date": "2026-07-01T00:00:00+00:00",
                    }
                }
            ],
        },
    ) as get_reviews:
        assert main(["pr", "reviews", "7"]) == 0

    get_reviews.assert_called_once()
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-cloud"
    assert output["review_decision"] == "approved"


def test_cli_pr_reviews_datacenter(datacenter_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "magpie_bitbucket.datacenter.get_pull_request_reviews",
        return_value={
            "pull_request_id": "9",
            "pull_request": {
                "reviewers": [
                    {
                        "user": {"displayName": "Reviewer One"},
                        "approved": True,
                    }
                ]
            },
            "values": [
                {
                    "action": "APPROVED",
                    "user": {"displayName": "Reviewer One"},
                    "createdDate": 1710000000000,
                }
            ],
        },
    ) as get_reviews:
        assert main(["pr", "reviews", "9"]) == 0

    get_reviews.assert_called_once()
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-datacenter"
    assert output["review_decision"] == "approved"


@patch("magpie_bitbucket.cloud.get_pull_request_status")
def test_cli_pr_status_cloud(
    mock_get_pull_request_status: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_pull_request_status.return_value = {
        "pull_request_id": "7",
        "commit": "abc123",
        "values": [{"key": "build", "state": "SUCCESSFUL"}],
    }

    exit_code = main(["pr", "status", "7"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["pull_request_id"] == "7"
    assert output["commit"] == "abc123"
    assert output["checks"] == "passing"
    assert output["check_details"][0]["key"] == "build"


def test_normalize_pull_request_status_aggregate_values() -> None:
    assert pull_request_status("cloud", {"values": []})["checks"] == "none"
    assert pull_request_status("cloud", {"values": [{"state": "SUCCESSFUL"}]})["checks"] == "passing"
    assert pull_request_status("cloud", {"values": [{"state": "FAILED"}]})["checks"] == "failing"
    assert pull_request_status("cloud", {"values": [{"state": "INPROGRESS"}]})["checks"] == "pending"


@patch("magpie_bitbucket.datacenter.get_pull_request_status")
def test_cli_pr_status_datacenter(
    mock_get_pull_request_status: MagicMock,
    datacenter_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_pull_request_status.return_value = {
        "pull_request_id": "9",
        "commit": "def456",
        "values": [{"key": "build", "state": "SUCCESSFUL"}],
    }

    exit_code = main(["pr", "status", "9"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["backend"] == "bitbucket-datacenter"
    assert output["pull_request_id"] == "9"
    assert output["checks"] == "passing"
    assert output["check_details"][0]["key"] == "build"


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_status_requires_latest_commit(
    mock_build_opener: MagicMock,
    datacenter_env: None,
) -> None:
    mock_opener(mock_build_opener, {"id": 9, "fromRef": {}})

    with pytest.raises(BitbucketError, match=r"fromRef\.latestCommit"):
        datacenter.get_pull_request_status(load_config(), "9")


@patch("urllib.request.build_opener")
def test_cloud_get_pull_request_commits_follows_next(
    mock_build_opener: MagicMock,
    cloud_env: None,
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"hash": "abc123", "message": "First commit"}],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/commits?page=2",
        },
        {"values": [{"hash": "def456", "message": "Second commit"}]},
    )

    result = cloud.get_pull_request_commits(load_config(), "7")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert (
        first_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/commits"
    )
    assert (
        second_request.full_url
        == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/commits?page=2"
    )
    assert result["pull_request_id"] == "7"
    assert [item["hash"] for item in result["values"]] == ["abc123", "def456"]


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_commits_follows_next_page_start(
    mock_build_opener: MagicMock,
    datacenter_env: None,
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {"values": [{"id": "abc123", "message": "First commit"}], "isLastPage": False, "nextPageStart": 25},
        {"values": [{"id": "def456", "message": "Second commit"}], "isLastPage": True},
    )

    result = datacenter.get_pull_request_commits(load_config(), "9")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert (
        first_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/commits?start=0"
    )
    assert (
        second_request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/commits?start=25"
    )
    assert result["pull_request_id"] == "9"
    assert [item["id"] for item in result["values"]] == ["abc123", "def456"]


def test_normalize_cloud_pull_request_commits() -> None:
    raw = {
        "pull_request_id": "7",
        "values": [
            {
                "hash": "abc123",
                "message": "Fix docs",
                "author": {"raw": "Alice <alice@example.test>", "user": {"display_name": "Alice"}},
                "date": "2026-07-09T10:00:00+00:00",
                "links": {"html": {"href": "https://bitbucket.org/apache/magpie/commits/abc123"}},
            }
        ],
    }

    result = pull_request_commits("cloud", raw)

    assert result["backend"] == "bitbucket-cloud"
    assert result["coverage"] == "partial-read-only"
    assert result["pull_request_id"] == "7"
    assert result["commits"][0]["hash"] == "abc123"
    assert result["commits"][0]["message"] == "Fix docs"
    assert result["commits"][0]["author"] == "Alice"
    assert result["commits"][0]["date"] == "2026-07-09T10:00:00+00:00"
    assert result["commits"][0]["links"]["html"] == "https://bitbucket.org/apache/magpie/commits/abc123"


def test_normalize_datacenter_pull_request_commits() -> None:
    raw = {
        "pull_request_id": "9",
        "values": [
            {
                "id": "def456789",
                "displayId": "def4567",
                "message": "Fix tests",
                "author": {"displayName": "Bob"},
                "authorTimestamp": 1783428000000,
                "links": {"self": [{"href": "https://bitbucket.example.test/commits/def456789"}]},
            }
        ],
    }

    result = pull_request_commits("datacenter", raw)

    assert result["backend"] == "bitbucket-datacenter"
    assert result["pull_request_id"] == "9"
    assert result["commits"][0]["hash"] == "def456789"
    assert result["commits"][0]["display_hash"] == "def4567"
    assert result["commits"][0]["message"] == "Fix tests"
    assert result["commits"][0]["author"] == "Bob"
    assert result["commits"][0]["date"] == "2026-07-07T12:40:00Z"
    assert result["commits"][0]["links"]["self"] == "https://bitbucket.example.test/commits/def456789"


@patch("magpie_bitbucket.cloud.get_pull_request_commits")
def test_cli_pr_commits_cloud(
    mock_get_pull_request_commits: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_pull_request_commits.return_value = {
        "pull_request_id": "7",
        "values": [{"hash": "abc123", "message": "Fix docs"}],
    }

    exit_code = main(["pr", "commits", "7"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["backend"] == "bitbucket-cloud"
    assert output["pull_request_id"] == "7"
    assert output["commits"][0]["hash"] == "abc123"


@patch("magpie_bitbucket.datacenter.get_pull_request_commits")
def test_cli_pr_commits_datacenter(
    mock_get_pull_request_commits: MagicMock,
    datacenter_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_pull_request_commits.return_value = {
        "pull_request_id": "9",
        "values": [{"id": "def456789", "message": "Fix tests"}],
    }

    exit_code = main(["pr", "commits", "9"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["backend"] == "bitbucket-datacenter"
    assert output["pull_request_id"] == "9"
    assert output["commits"][0]["hash"] == "def456789"


@patch("urllib.request.build_opener")
def test_cloud_get_pull_request_diff_url(
    mock_build_opener: MagicMock,
    cloud_env: None,
) -> None:
    response = make_mock_text_response(
        "diff --git a/a.txt b/a.txt\n",
        url="https://api.bitbucket.org/2.0/repositories/apache/magpie/diff/source..dest",
    )
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value = response
    mock_build_opener.return_value = opener

    result = cloud.get_pull_request_diff(load_config(), "7")

    request = opener.open.call_args.args[0]
    assert request.full_url == "https://api.bitbucket.org/2.0/repositories/apache/magpie/pullrequests/7/diff"
    assert request.headers["Accept"] == "text/x-diff"
    assert result["pull_request_id"] == "7"
    assert result["body"] == "diff --git a/a.txt b/a.txt\n"
    assert result["content_type"] == "text/x-diff"


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_diff_url(
    mock_build_opener: MagicMock,
    datacenter_env: None,
) -> None:
    response = make_mock_text_response(
        "diff --git a/a.txt b/a.txt\n",
        url="https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/diff",
    )
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value = response
    mock_build_opener.return_value = opener

    result = datacenter.get_pull_request_diff(load_config(), "9")

    request = opener.open.call_args.args[0]
    assert (
        request.full_url
        == "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/diff"
    )
    assert request.headers["Accept"] == "text/plain"
    assert result["pull_request_id"] == "9"
    assert result["body"] == "diff --git a/a.txt b/a.txt\n"
    assert result["content_type"] == "text/x-diff"


def test_normalize_pull_request_diff() -> None:
    raw = {
        "pull_request_id": "7",
        "body": "diff --git a/a.txt b/a.txt\n",
        "content_type": "text/x-diff",
        "url": "https://api.bitbucket.org/example",
    }

    result = pull_request_diff("cloud", raw)

    assert result["backend"] == "bitbucket-cloud"
    assert result["coverage"] == "partial-read-only"
    assert result["pull_request_id"] == "7"
    assert result["diff"] == "diff --git a/a.txt b/a.txt\n"
    assert result["content_type"] == "text/x-diff"
    assert result["url"] == "https://api.bitbucket.org/example"


@patch("magpie_bitbucket.cloud.get_pull_request_diff")
def test_cli_pr_diff_cloud(
    mock_get_pull_request_diff: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_pull_request_diff.return_value = {
        "pull_request_id": "7",
        "body": "diff --git a/a.txt b/a.txt\n",
        "content_type": "text/x-diff",
        "url": "https://api.bitbucket.org/example",
    }

    exit_code = main(["pr", "diff", "7"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["backend"] == "bitbucket-cloud"
    assert output["pull_request_id"] == "7"
    assert output["diff"] == "diff --git a/a.txt b/a.txt\n"


@patch("magpie_bitbucket.datacenter.get_pull_request_diff")
def test_cli_pr_diff_datacenter(
    mock_get_pull_request_diff: MagicMock,
    datacenter_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_pull_request_diff.return_value = {
        "pull_request_id": "9",
        "body": "diff --git a/a.txt b/a.txt\n",
        "content_type": "text/x-diff",
        "url": "https://bitbucket.example.test/example",
    }

    exit_code = main(["pr", "diff", "9"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["backend"] == "bitbucket-datacenter"
    assert output["pull_request_id"] == "9"
    assert output["diff"] == "diff --git a/a.txt b/a.txt\n"


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


def test_normalize_datacenter_discussion_allows_null_threaded_replies() -> None:
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
                    "comments": None,
                },
            }
        ],
    }

    result = pull_request_discussion("datacenter", raw)

    assert len(result["comments"]) == 1
    assert result["comments"][0]["body"] == "Parent comment"
    assert result["comments"][0]["parent_id"] is None
    assert result["participants"] == ["Asha"]


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


def test_cloud_get_pull_request_merge_checks_composes_status_and_reviews(cloud_env: None) -> None:
    with (
        patch("magpie_bitbucket.cloud.get_pull_request_status") as get_status,
        patch("magpie_bitbucket.cloud.get_pull_request_reviews") as get_reviews,
    ):
        get_status.return_value = {
            "pull_request_id": "7",
            "pull_request": {"id": 7, "state": "OPEN"},
            "values": [],
        }
        get_reviews.return_value = {
            "pull_request_id": "7",
            "pull_request": {"id": 7, "state": "OPEN"},
            "values": [],
        }

        result = cloud.get_pull_request_merge_checks(load_config(), "7")

    get_status.assert_called_once()
    get_reviews.assert_called_once()
    assert result["pull_request_id"] == "7"
    assert result["pull_request"]["id"] == 7


def test_datacenter_get_pull_request_merge_checks_composes_status_and_reviews(
    datacenter_env: None,
) -> None:
    with (
        patch("magpie_bitbucket.datacenter.get_pull_request_merge_status") as get_merge,
        patch("magpie_bitbucket.datacenter.get_pull_request_status") as get_status,
        patch("magpie_bitbucket.datacenter.get_pull_request_reviews") as get_reviews,
    ):
        get_merge.return_value = {"canMerge": True, "conflicted": False, "vetoes": []}
        get_status.return_value = {
            "pull_request_id": "9",
            "pull_request": {"id": 9, "state": "OPEN"},
            "values": [],
        }
        get_reviews.return_value = {
            "pull_request_id": "9",
            "pull_request": {"id": 9, "state": "OPEN"},
            "values": [],
        }

        result = datacenter.get_pull_request_merge_checks(load_config(), "9")

    get_merge.assert_called_once()
    get_status.assert_called_once()
    get_reviews.assert_called_once()
    assert result["pull_request_id"] == "9"
    assert result["pull_request"]["id"] == 9
    assert result["merge"]["canMerge"] is True


def test_normalize_pull_request_merge_checks_blocks_on_known_signals() -> None:
    normalized = pull_request_merge_checks(
        "cloud",
        {
            "pull_request_id": "7",
            "pull_request": {
                "state": "OPEN",
                "mergeable": False,
                "conflicted": True,
            },
            "status": {
                "pull_request_id": "7",
                "pull_request": {"state": "OPEN"},
                "values": [{"state": "FAILED"}],
            },
            "reviews": {
                "pull_request_id": "7",
                "pull_request": {},
                "values": [
                    {
                        "changes_requested": {
                            "user": {"display_name": "Reviewer One"},
                            "date": "2026-07-01T00:00:00+00:00",
                        }
                    }
                ],
            },
        },
    )

    assert normalized["backend"] == "bitbucket-cloud"
    assert normalized["merge_check_state"] == "blocked"
    assert normalized["has_known_blockers"] is True
    assert normalized["mergeable"] == "conflicting"
    assert normalized["can_merge"] is False
    assert normalized["conflicted"] is True
    assert normalized["checks"] == "failing"
    assert normalized["review_decision"] == "changes_requested"
    assert {blocker["kind"] for blocker in normalized["blockers"]} == {
        "mergeability",
        "merge_conflict",
        "status_checks",
        "reviews",
    }


def test_normalize_pull_request_merge_checks_unknown_without_backend_signal() -> None:
    normalized = pull_request_merge_checks(
        "datacenter",
        {
            "pull_request_id": "9",
            "pull_request": {"state": "OPEN"},
            "status": {"pull_request_id": "9", "values": []},
            "reviews": {"pull_request_id": "9", "pull_request": {}, "values": []},
        },
    )

    assert normalized["backend"] == "bitbucket-datacenter"
    assert normalized["merge_check_state"] == "unknown"
    assert normalized["has_known_blockers"] is False
    assert normalized["mergeable"] == "unknown"
    assert normalized["can_merge"] is None
    assert normalized["conflicted"] is None
    assert normalized["blockers"] == []


def test_cli_pr_merge_checks_cloud(cloud_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "magpie_bitbucket.cloud.get_pull_request_merge_checks",
        return_value={
            "pull_request_id": "7",
            "pull_request": {"state": "OPEN", "mergeable": False},
            "status": {"pull_request_id": "7", "values": [{"state": "FAILED"}]},
            "reviews": {"pull_request_id": "7", "pull_request": {}, "values": []},
        },
    ) as get_merge_checks:
        assert main(["pr", "merge-checks", "7"]) == 0

    get_merge_checks.assert_called_once()
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-cloud"
    assert output["merge_check_state"] == "blocked"
    assert output["has_known_blockers"] is True


@patch("urllib.request.build_opener")
def test_datacenter_get_pull_request_merge_status_url(
    mock_build_opener: MagicMock, datacenter_env: None
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {"canMerge": False, "conflicted": True, "vetoes": []},
    )

    result = datacenter.get_pull_request_merge_status(load_config(), "9")

    request = opener.open.call_args.args[0]
    assert request.full_url == (
        "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/pull-requests/9/merge"
    )
    assert request.get_method() == "GET"
    assert result["canMerge"] is False


def test_datacenter_get_pull_request_merge_checks_includes_merge_status(
    datacenter_env: None,
) -> None:
    with (
        patch("magpie_bitbucket.datacenter.get_pull_request_merge_status") as get_merge,
        patch("magpie_bitbucket.datacenter.get_pull_request_status") as get_status,
        patch("magpie_bitbucket.datacenter.get_pull_request_reviews") as get_reviews,
    ):
        get_merge.return_value = {
            "canMerge": False,
            "conflicted": True,
            "vetoes": [{"summaryMessage": "Needs one more approval"}],
        }
        get_status.return_value = {
            "pull_request_id": "9",
            "pull_request": {"id": 9, "state": "OPEN"},
            "values": [],
        }
        get_reviews.return_value = {
            "pull_request_id": "9",
            "pull_request": {"id": 9, "state": "OPEN"},
            "values": [],
        }

        result = datacenter.get_pull_request_merge_checks(load_config(), "9")

    get_merge.assert_called_once()
    get_status.assert_called_once()
    get_reviews.assert_called_once()
    assert result["merge"]["canMerge"] is False
    assert result["merge"]["conflicted"] is True


def test_normalize_pull_request_merge_checks_datacenter_vetoes() -> None:
    normalized = pull_request_merge_checks(
        "datacenter",
        {
            "pull_request_id": "9",
            "pull_request": {"state": "OPEN"},
            "merge": {
                "canMerge": False,
                "conflicted": False,
                "outcome": "VETOED",
                "vetoes": [
                    {
                        "summaryMessage": "Needs one more approval",
                        "detailedMessage": "Project policy requires another reviewer.",
                    }
                ],
            },
            "status": {"pull_request_id": "9", "values": []},
            "reviews": {"pull_request_id": "9", "pull_request": {}, "values": []},
        },
    )

    assert normalized["merge_check_state"] == "blocked"
    assert normalized["has_known_blockers"] is True
    assert normalized["mergeable"] == "unknown"
    assert normalized["can_merge"] is False
    assert normalized["conflicted"] is False
    assert any(blocker["kind"] == "merge_veto" for blocker in normalized["blockers"])


def test_cli_pr_merge_checks_datacenter(datacenter_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "magpie_bitbucket.datacenter.get_pull_request_merge_checks",
        return_value={
            "pull_request_id": "9",
            "pull_request": {"state": "OPEN"},
            "merge": {"canMerge": True, "conflicted": False, "vetoes": []},
            "status": {"pull_request_id": "9", "values": []},
            "reviews": {"pull_request_id": "9", "pull_request": {}, "values": []},
        },
    ) as get_merge_checks:
        assert main(["pr", "merge-checks", "9"]) == 0

    get_merge_checks.assert_called_once()
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-datacenter"
    assert output["merge_check_state"] == "passing"
    assert output["mergeable"] == "clean"


@patch("urllib.request.build_opener")
def test_cloud_get_repository_restrictions_follows_next(
    mock_build_opener: MagicMock, cloud_env: None
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"id": 1, "kind": "push", "pattern": "main"}],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/branch-restrictions?page=2",
        },
        {"values": [{"id": 2, "kind": "force", "pattern": "release/*"}]},
    )

    result = cloud.get_repository_restrictions(load_config())

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert first_request.full_url == (
        "https://api.bitbucket.org/2.0/repositories/apache/magpie/branch-restrictions"
    )
    assert second_request.full_url.endswith("branch-restrictions?page=2")
    assert result["values"] == [
        {"id": 1, "kind": "push", "pattern": "main"},
        {"id": 2, "kind": "force", "pattern": "release/*"},
    ]


@patch("urllib.request.build_opener")
def test_datacenter_get_repository_restrictions_paginates(
    mock_build_opener: MagicMock, datacenter_env: None
) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"id": 1, "type": "read-only"}],
            "isLastPage": False,
            "nextPageStart": 25,
        },
        {"values": [{"id": 2, "type": "pull-request-only"}], "isLastPage": True},
    )

    result = datacenter.get_repository_restrictions(load_config())

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert first_request.full_url == (
        "https://bitbucket.example.test/rest/api/1.0/projects/MAGPIE/repos/magpie/"
        "branch-permissions/search?start=0"
    )
    assert second_request.full_url.endswith("branch-permissions/search?start=25")
    assert result["permission_required"] == "REPO_ADMIN"
    assert result["values"] == [
        {"id": 1, "type": "read-only"},
        {"id": 2, "type": "pull-request-only"},
    ]


def test_normalize_cloud_repository_restrictions() -> None:
    normalized = repository_restrictions(
        "cloud",
        {
            "values": [
                {
                    "id": 1,
                    "kind": "push",
                    "pattern": "main",
                    "users": [{"display_name": "Reviewer One"}],
                    "groups": [{"name": "admins"}],
                }
            ]
        },
    )

    assert normalized["backend"] == "bitbucket-cloud"
    assert normalized["coverage"] == "partial-read-only"
    assert normalized["restrictions"][0]["kind"] == "push"
    assert normalized["restrictions"][0]["pattern"] == "main"
    assert normalized["restrictions"][0]["users"] == ["Reviewer One"]
    assert normalized["restrictions"][0]["groups"] == ["admins"]


def test_normalize_datacenter_repository_restrictions() -> None:
    normalized = repository_restrictions(
        "datacenter",
        {
            "permission_required": "REPO_ADMIN",
            "values": [
                {
                    "id": 9,
                    "type": "pull-request-only",
                    "matcher": {
                        "id": "refs/heads/main",
                        "displayId": "main",
                        "type": {"id": "BRANCH", "name": "Branch"},
                    },
                    "users": [{"displayName": "Reviewer One"}],
                    "groups": [{"name": "admins"}],
                    "accessKeys": [{"key": "deploy-key"}],
                }
            ],
        },
    )

    assert normalized["backend"] == "bitbucket-datacenter"
    assert normalized["permission_required"] == "REPO_ADMIN"
    restriction = normalized["restrictions"][0]
    assert restriction["kind"] == "pull-request-only"
    assert restriction["pattern"] == "main"
    assert restriction["branch_match_kind"] == "BRANCH"
    assert restriction["branch_type"] == "refs/heads/main"
    assert restriction["users"] == ["Reviewer One"]
    assert restriction["groups"] == ["admins"]
    assert restriction["access_keys"] == ["deploy-key"]


@patch("magpie_bitbucket.cloud.get_repository_restrictions")
def test_cli_repo_restrictions_cloud(
    mock_get_repository_restrictions: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_repository_restrictions.return_value = {"values": [{"id": 1, "kind": "push", "pattern": "main"}]}

    exit_code = main(["repo", "restrictions"])

    assert exit_code == 0
    mock_get_repository_restrictions.assert_called_once()
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-cloud"
    assert output["restrictions"][0]["pattern"] == "main"


@patch("magpie_bitbucket.datacenter.get_repository_restrictions")
def test_cli_repo_restrictions_datacenter(
    mock_get_repository_restrictions: MagicMock,
    datacenter_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_repository_restrictions.return_value = {
        "permission_required": "REPO_ADMIN",
        "values": [{"id": 9, "type": "read-only"}],
    }

    exit_code = main(["repo", "restrictions"])

    assert exit_code == 0
    mock_get_repository_restrictions.assert_called_once()
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-datacenter"
    assert output["permission_required"] == "REPO_ADMIN"


@patch("urllib.request.build_opener")
def test_cloud_list_open_issues_follows_next(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"id": 1, "title": "First issue", "state": "open"}],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues?page=2",
        },
        {"values": [{"id": 2, "title": "Second issue", "state": "open"}]},
    )

    result = cloud.list_open_issues(load_config())

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert first_request.full_url == (
        "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues?q=state%3D%22new%22%20OR%20state%3D%22open%22%20OR%20state%3D%22on%20hold%22"
    )
    assert second_request.full_url.endswith("/issues?page=2")
    assert result["values"] == [
        {"id": 1, "title": "First issue", "state": "open"},
        {"id": 2, "title": "Second issue", "state": "open"},
    ]


@patch("urllib.request.build_opener")
def test_cloud_get_issue_url(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(mock_build_opener, {"id": 7, "title": "Fix issue"})

    result = cloud.get_issue(load_config(), "7")

    request = opener.open.call_args.args[0]
    assert request.full_url == "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues/7"
    assert result == {"id": 7, "title": "Fix issue"}


def test_datacenter_list_open_issues_unsupported(datacenter_env: None) -> None:
    with pytest.raises(BitbucketError, match="Data Center native issue reads are not supported"):
        datacenter.list_open_issues(load_config())


def test_datacenter_get_issue_unsupported(datacenter_env: None) -> None:
    with pytest.raises(BitbucketError, match="Data Center native issue reads are not supported"):
        datacenter.get_issue(load_config(), "7")


def test_normalize_cloud_issue() -> None:
    normalized = issue(
        "cloud",
        {
            "id": 7,
            "title": "Fix docs",
            "state": "new",
            "kind": "bug",
            "priority": "major",
            "reporter": {"display_name": "Reporter One"},
            "assignee": {"display_name": "Assignee One"},
            "created_on": "2026-07-01T12:00:00+00:00",
            "updated_on": "2026-07-02T12:00:00+00:00",
            "content": {"raw": "Issue body"},
            "links": {"html": {"href": "https://bitbucket.org/apache/magpie/issues/7"}},
        },
    )

    assert normalized["backend"] == "bitbucket-cloud"
    assert normalized["id"] == "7"
    assert normalized["title"] == "Fix docs"
    assert normalized["state"] == "open"
    assert normalized["kind"] == "bug"
    assert normalized["priority"] == "major"
    assert normalized["reporter"] == "Reporter One"
    assert normalized["assignee"] == "Assignee One"
    assert normalized["description"] == "Issue body"
    assert normalized["permalink"] == "https://bitbucket.org/apache/magpie/issues/7"
    assert "partial-tracker" in normalized["labels"]


def test_normalize_cloud_issue_list() -> None:
    normalized = issue_list(
        "cloud",
        {
            "values": [
                {"id": 1, "title": "First issue", "state": "new"},
                {"id": 2, "title": "Second issue", "state": "resolved"},
            ]
        },
    )

    assert normalized["backend"] == "bitbucket-cloud"
    assert normalized["coverage"] == "partial-read-only"
    assert [item["state"] for item in normalized["issues"]] == ["open", "closed"]


@patch("magpie_bitbucket.cloud.list_open_issues")
def test_cli_issue_list_open_cloud(
    mock_list_open_issues: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_list_open_issues.return_value = {"values": [{"id": 1, "title": "First issue", "state": "new"}]}

    exit_code = main(["issue", "list-open"])

    assert exit_code == 0
    mock_list_open_issues.assert_called_once()
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-cloud"
    assert output["issues"][0]["title"] == "First issue"


@patch("magpie_bitbucket.cloud.get_issue")
def test_cli_issue_get_cloud(
    mock_get_issue: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_issue.return_value = {"id": 7, "title": "Fix docs", "state": "new"}

    exit_code = main(["issue", "get", "7"])

    assert exit_code == 0
    mock_get_issue.assert_called_once_with(load_config(), "7")
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-cloud"
    assert output["id"] == "7"
    assert output["state"] == "open"


@patch("urllib.request.build_opener")
def test_cloud_get_issue_comments_follows_next(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"id": 101, "content": {"raw": "First comment"}}],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues/7/comments?page=2",
        },
        {"values": [{"id": 102, "content": {"raw": "Second comment"}}]},
    )

    result = cloud.get_issue_comments(load_config(), "7")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert first_request.full_url == (
        "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues/7/comments"
    )
    assert second_request.full_url.endswith("/issues/7/comments?page=2")
    assert result["issue_id"] == "7"
    assert result["values"] == [
        {"id": 101, "content": {"raw": "First comment"}},
        {"id": 102, "content": {"raw": "Second comment"}},
    ]


def test_datacenter_get_issue_comments_unsupported(datacenter_env: None) -> None:
    with pytest.raises(BitbucketError, match="Data Center native issue comments are not supported"):
        datacenter.get_issue_comments(load_config(), "7")


def test_normalize_cloud_issue_comments() -> None:
    normalized = issue_comments(
        "cloud",
        {
            "issue_id": "7",
            "values": [
                {
                    "id": 101,
                    "user": {"display_name": "Alice"},
                    "content": {"raw": "Looks good."},
                    "created_on": "2026-07-01T00:00:00Z",
                    "updated_on": "2026-07-01T01:00:00Z",
                    "deleted": False,
                    "links": {"html": {"href": "https://bitbucket.org/apache/magpie/issues/7#comment-101"}},
                }
            ],
        },
    )

    assert normalized["backend"] == "bitbucket-cloud"
    assert normalized["coverage"] == "partial-read-only"
    assert normalized["issue_id"] == "7"
    assert normalized["participants"] == ["Alice"]
    assert normalized["comments"][0]["id"] == "101"
    assert normalized["comments"][0]["author"] == "Alice"
    assert normalized["comments"][0]["body"] == "Looks good."
    assert normalized["comments"][0]["date"] == "2026-07-01T00:00:00Z"
    assert normalized["comments"][0]["kind"] == "comment"
    assert normalized["comments"][0]["deleted"] is False

    deleted_normalized = issue_comments(
        "cloud",
        {"issue_id": "7", "values": [{"id": 102, "deleted": True}]},
    )
    assert deleted_normalized["comments"][0]["deleted"] is True


@patch("magpie_bitbucket.cloud.get_issue_comments")
def test_cli_issue_comments_cloud(
    mock_get_issue_comments: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_issue_comments.return_value = {
        "issue_id": "7",
        "values": [{"id": 101, "user": {"display_name": "Alice"}, "content": {"raw": "Looks good."}}],
    }

    exit_code = main(["issue", "comments", "7"])

    assert exit_code == 0
    mock_get_issue_comments.assert_called_once()
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-cloud"
    assert output["issue_id"] == "7"
    assert output["comments"][0]["body"] == "Looks good."


@patch("urllib.request.build_opener")
def test_cloud_get_issue_attachments_follows_next(mock_build_opener: MagicMock, cloud_env: None) -> None:
    opener = mock_opener(
        mock_build_opener,
        {
            "values": [{"id": 201, "name": "screenshot.png"}],
            "next": "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues/7/attachments?page=2",
        },
        {"values": [{"id": 202, "name": "trace.log"}]},
    )

    result = cloud.get_issue_attachments(load_config(), "7")

    first_request = opener.open.call_args_list[0].args[0]
    second_request = opener.open.call_args_list[1].args[0]
    assert first_request.full_url == (
        "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues/7/attachments"
    )
    assert second_request.full_url.endswith("/issues/7/attachments?page=2")
    assert result["issue_id"] == "7"
    assert result["values"] == [
        {"id": 201, "name": "screenshot.png"},
        {"id": 202, "name": "trace.log"},
    ]


def test_datacenter_get_issue_attachments_unsupported(datacenter_env: None) -> None:
    with pytest.raises(BitbucketError, match="Data Center native issue attachments are not supported"):
        datacenter.get_issue_attachments(load_config(), "7")


def test_normalize_cloud_issue_attachments() -> None:
    normalized = issue_attachments(
        "cloud",
        {
            "issue_id": "7",
            "values": [
                {
                    "id": 201,
                    "name": "screenshot.png",
                    "filename": "screenshot.png",
                    "size": 12345,
                    "user": {"display_name": "Alice"},
                    "created_on": "2026-07-01T00:00:00Z",
                    "updated_on": "2026-07-01T01:00:00Z",
                    "links": {
                        "self": {
                            "href": "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues/7/attachments/201"
                        },
                        "html": {"href": "https://bitbucket.org/apache/magpie/issues/7/attachments/201"},
                    },
                }
            ],
        },
    )

    assert normalized["backend"] == "bitbucket-cloud"
    assert normalized["coverage"] == "partial-read-only"
    assert normalized["issue_id"] == "7"
    assert normalized["attachments"][0]["id"] == "201"
    assert normalized["attachments"][0]["name"] == "screenshot.png"
    assert normalized["attachments"][0]["filename"] == "screenshot.png"
    assert normalized["attachments"][0]["size"] == 12345
    assert normalized["attachments"][0]["user"] == "Alice"
    assert normalized["attachments"][0]["created"] == "2026-07-01T00:00:00Z"
    assert normalized["attachments"][0]["download_url"].endswith("/attachments/201")

    documented_payload = issue_attachments(
        "cloud",
        {
            "issue_id": "7",
            "values": [
                {
                    "name": "documented.txt",
                    "links": {
                        "self": {
                            "href": "https://api.bitbucket.org/2.0/repositories/apache/magpie/issues/7/attachments/documented.txt"
                        }
                    },
                }
            ],
        },
    )
    assert documented_payload["attachments"][0]["id"] == "documented.txt"
    assert documented_payload["attachments"][0]["name"] == "documented.txt"
    assert documented_payload["attachments"][0]["filename"] == "documented.txt"
    assert documented_payload["attachments"][0]["size"] is None
    assert documented_payload["attachments"][0]["download_url"].endswith("/attachments/documented.txt")


@patch("magpie_bitbucket.cloud.get_issue_attachments")
def test_cli_issue_attachments_cloud(
    mock_get_issue_attachments: MagicMock,
    cloud_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_get_issue_attachments.return_value = {
        "issue_id": "7",
        "values": [{"id": 201, "name": "screenshot.png", "user": {"display_name": "Alice"}}],
    }

    exit_code = main(["issue", "attachments", "7"])

    assert exit_code == 0
    mock_get_issue_attachments.assert_called_once_with(load_config(), "7")
    output = json.loads(capsys.readouterr().out)
    assert output["backend"] == "bitbucket-cloud"
    assert output["issue_id"] == "7"
    assert output["attachments"][0]["name"] == "screenshot.png"
