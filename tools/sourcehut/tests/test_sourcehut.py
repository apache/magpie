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

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from magpie_sourcehut.builds import get_job
from magpie_sourcehut.cli import main
from magpie_sourcehut.client import SourceHutError, query_graphql
from magpie_sourcehut.lists import get_patchset, list_patchsets, map_patchset_to_pr
from magpie_sourcehut.repo import get_repo
from magpie_sourcehut.todo import (
    get_ticket,
    label_ticket,
    submit_comment,
    submit_ticket,
    update_ticket_status,
)


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SRHT_TOKEN", "mock_token_123")


def make_mock_response(status_code: int, body_dict: dict[str, Any]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body_dict).encode("utf-8")
    mock_resp.status = status_code
    return mock_resp


@patch("urllib.request.urlopen")
def test_query_graphql_success(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(200, {"data": {"version": "1.0"}})
    res = query_graphql("todo", "{ version }")
    assert res == {"version": "1.0"}


def test_query_graphql_no_token() -> None:
    with pytest.raises(SourceHutError, match="SRHT_TOKEN environment variable is not set"):
        query_graphql("todo", "{ version }")


@patch("urllib.request.urlopen")
def test_query_graphql_error_in_json(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"errors": [{"message": "Invalid query syntax"}]}
    )
    with pytest.raises(SourceHutError, match=r"GraphQL error from todo\.sr\.ht: Invalid query syntax"):
        query_graphql("todo", "invalid_query")


@patch("urllib.request.urlopen")
def test_get_ticket(mock_urlopen: MagicMock, mock_env: None) -> None:
    ticket_data = {
        "id": 42,
        "title": "Fix memory leak",
        "description": "Found a leak in client",
        "status": "UNRESOLVED",
        "resolution": None,
        "labels": [{"id": 1, "name": "bug"}],
        "comments": [],
    }
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"tracker": {"ticket": ticket_data}}}
    )
    res = get_ticket("~user", "my-project", 42)
    assert res["id"] == 42
    assert res["title"] == "Fix memory leak"


@patch("urllib.request.urlopen")
def test_submit_ticket(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"submitTicket": {"id": 101, "title": "New issue"}}}
    )
    res = submit_ticket("~user", "my-project", "New issue", "Description here")
    assert res["id"] == 101


@patch("urllib.request.urlopen")
def test_submit_comment(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"submitComment": {"id": 501, "body": "Comment body"}}}
    )
    res = submit_comment("~user", "my-project", 42, "Comment body")
    assert res["id"] == 501


@patch("urllib.request.urlopen")
def test_label_ticket(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"labelTicket": {"id": 42}}}
    )
    res = label_ticket("~user", "my-project", 42, 10)
    assert res == {"id": 42}


@patch("urllib.request.urlopen")
def test_update_ticket_status(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"updateTicketStatus": {"id": 42, "status": "RESOLVED", "resolution": "FIXED"}}}
    )
    res = update_ticket_status("~user", "my-project", 42, "RESOLVED", "FIXED")
    assert res["status"] == "RESOLVED"


@patch("urllib.request.urlopen")
def test_get_patchset_and_mapping(mock_urlopen: MagicMock, mock_env: None) -> None:
    patchset_data = {
        "id": 200,
        "subject": "[PATCH 0/2] Fix some logs",
        "version": 1,
        "status": "PROPOSED",
        "patches": [
            {"id": 201, "subject": "[PATCH 1/2] Add warning log", "diff": "--- a/file\n+++ b/file\n"},
            {"id": 202, "subject": "[PATCH 2/2] Add error log", "diff": "--- a/file2\n+++ b/file2\n"},
        ],
        "thread": {
            "id": 999,
            "emails": {
                "edges": [
                    {
                        "node": {
                            "id": 1000,
                            "subject": "[PATCH 0/2] Fix some logs",
                            "body": "Here is the patch series to fix logging",
                            "sender": {"canonicalName": "Alice <alice@example.com>"},
                            "date": "2026-07-01T12:00:00Z",
                        }
                    },
                    {
                        "node": {
                            "id": 1003,
                            "subject": "Re: [PATCH 0/2] Fix some logs",
                            "body": "Looks good to me!",
                            "sender": {"canonicalName": "Bob <bob@example.com>"},
                            "date": "2026-07-01T13:00:00Z",
                        }
                    },
                ]
            },
        },
    }
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"list": {"patchset": patchset_data}}}
    )
    raw = get_patchset("~user", "my-list", 200)
    assert raw["id"] == 200

    pr = map_patchset_to_pr(raw)
    assert pr["id"] == "200"
    assert pr["title"] == "[PATCH 0/2] Fix some logs"
    assert pr["author"] == "Alice <alice@example.com>"
    assert pr["description"] == "Here is the patch series to fix logging"
    assert pr["state"] == "OPEN"
    assert len(pr["commits"]) == 2
    assert pr["commits"][0]["subject"] == "[PATCH 1/2] Add warning log"
    assert len(pr["comments"]) == 1
    assert pr["comments"][0]["author"] == "Bob <bob@example.com>"
    assert pr["comments"][0]["body"] == "Looks good to me!"


@patch("urllib.request.urlopen")
def test_list_patchsets(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200,
        {
            "data": {
                "list": {
                    "patches": {
                        "edges": [
                            {"node": {"id": 1, "subject": "P1", "status": "ACCEPTED"}},
                            {"node": {"id": 2, "subject": "P2", "status": "PROPOSED"}},
                        ]
                    }
                }
            },
        },
    )
    res = list_patchsets("~user", "my-list")
    assert len(res) == 2
    assert res[0]["subject"] == "P1"


@patch("urllib.request.urlopen")
def test_get_job(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"job": {"id": 55, "status": "SUCCESS", "tasks": []}}}
    )
    res = get_job(55)
    assert res["status"] == "SUCCESS"


@patch("urllib.request.urlopen")
def test_get_repo(mock_urlopen: MagicMock, mock_env: None) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"repository": {"id": 9, "name": "my-repo", "description": "VCS"}}}
    )
    res = get_repo("git", "~user", "my-repo")
    assert res["name"] == "my-repo"


@patch("urllib.request.urlopen")
def test_cli_dispatch(mock_urlopen: MagicMock, mock_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    mock_urlopen.return_value.__enter__.return_value = make_mock_response(
        200, {"data": {"job": {"id": 12, "status": "FAILED"}}}
    )
    code = main(["build", "get", "12"])
    assert code == 0
    captured = capsys.readouterr()
    assert "FAILED" in captured.out


def test_cli_label_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["ticket", "label", "~user", "my-project", "42"])
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "At least one of --add or --remove must be specified" in captured.err
