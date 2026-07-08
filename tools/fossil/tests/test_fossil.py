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

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magpie_fossil.cli import main
from magpie_fossil.client import FossilError
from magpie_fossil.forum import list_forum_threads, parse_forum_artifact, read_forum_thread
from magpie_fossil.ticket import get_ticket, list_tickets, submit_comment, submit_ticket
from magpie_fossil.wiki import list_wiki, read_wiki

# -- manifest parser tests -------------------------------------------------


def test_parse_forum_artifact() -> None:
    manifest = (
        "U alice\n"
        "D 2026-07-02T12:34:56.789\n"
        "W Thread Title\n"
        "Z 1234567890abcdef\n"
        "This is the forum body.\n"
        "Line two.\n"
    )
    parsed = parse_forum_artifact(manifest)
    assert parsed["author"] == "alice"
    assert parsed["date"] == "2026-07-02 12:34:56.789"
    assert parsed["title"] == "Thread Title"
    assert parsed["parent"] is None
    assert parsed["body"] == "This is the forum body.\nLine two."


def test_parse_forum_artifact_reply() -> None:
    manifest = (
        "U bob\nD 2026-07-02T13:45:00.000\nI root_uuid_123\nZ abcdef1234567890\nThis is a reply body.\n"
    )
    parsed = parse_forum_artifact(manifest)
    assert parsed["author"] == "bob"
    assert parsed["date"] == "2026-07-02 13:45:00.000"
    assert parsed["title"] == ""
    assert parsed["parent"] == "root_uuid_123"
    assert parsed["body"] == "This is a reply body."


# -- ticket tests ----------------------------------------------------------


@patch("magpie_fossil.ticket.query_db")
def test_get_ticket_success(mock_query_db: MagicMock) -> None:
    mock_query_db.side_effect = [
        [
            {
                "tkt_id": 1,
                "tkt_uuid": "abcdef123456",
                "title": "Memory leak",
                "status": "Open",
                "comment": "Original body",
            }
        ],
        [{"comment": "Fix in progress", "login": "alice", "tkt_mtime": "2026-07-02 12:00:00"}],
    ]
    tkt = get_ticket(Path("repo.fossil"), "abc")
    assert tkt["tkt_id"] == 1
    assert tkt["tkt_uuid"] == "abcdef123456"
    assert len(tkt["comments"]) == 1
    assert tkt["comments"][0]["body"] == "Fix in progress"
    assert tkt["comments"][0]["author"] == "alice"


@patch("magpie_fossil.ticket.query_db")
def test_get_ticket_not_found(mock_query_db: MagicMock) -> None:
    mock_query_db.return_value = []
    with pytest.raises(FossilError, match="not found"):
        get_ticket(Path("repo.fossil"), "abc")


@patch("magpie_fossil.ticket.query_db")
def test_get_ticket_ambiguous(mock_query_db: MagicMock) -> None:
    mock_query_db.return_value = [{"tkt_uuid": "abc1"}, {"tkt_uuid": "abc2"}]
    with pytest.raises(FossilError, match="Ambiguous UUID prefix"):
        get_ticket(Path("repo.fossil"), "abc")


@patch("magpie_fossil.ticket.query_db")
def test_list_tickets(mock_query_db: MagicMock) -> None:
    mock_query_db.return_value = [{"tkt_id": 1, "title": "T1"}]
    res = list_tickets(Path("repo.fossil"))
    assert len(res) == 1
    assert res[0]["title"] == "T1"


@patch("magpie_fossil.ticket.run_fossil")
def test_submit_ticket(mock_run_fossil: MagicMock) -> None:
    mock_run_fossil.return_value = "Created new ticket 1234567890abcdef12"
    uuid = submit_ticket(Path("repo.fossil"), "T1", "Body", {"type": "Bug"})
    assert uuid == "1234567890abcdef12"
    mock_run_fossil.assert_called_once_with(
        ["ticket", "add", "-R", "repo.fossil", "--", "title", "T1", "comment", "Body", "type", "Bug"]
    )


@patch("magpie_fossil.ticket.run_fossil")
@patch("magpie_fossil.ticket.query_db")
def test_submit_comment(mock_query_db: MagicMock, mock_run_fossil: MagicMock) -> None:
    mock_query_db.return_value = [{"tkt_id": 1, "tkt_uuid": "abcdef123456"}]
    mock_run_fossil.return_value = ""
    uuid = submit_comment(Path("repo.fossil"), "abc", "My comment")
    assert uuid == "abcdef123456"
    mock_run_fossil.assert_called_once_with(
        ["ticket", "set", "abcdef123456", "-R", "repo.fossil", "--", "+comment", "My comment"]
    )


# -- wiki tests ------------------------------------------------------------


@patch("magpie_fossil.wiki.run_fossil")
def test_list_wiki(mock_run_fossil: MagicMock) -> None:
    mock_run_fossil.return_value = "Home\nDocs\n"
    pages = list_wiki(Path("repo.fossil"))
    assert pages == ["Home", "Docs"]
    mock_run_fossil.assert_called_once_with(["wiki", "list", "-R", "repo.fossil"])


@patch("magpie_fossil.wiki.run_fossil")
def test_read_wiki(mock_run_fossil: MagicMock) -> None:
    mock_run_fossil.return_value = "# Welcome"
    content = read_wiki(Path("repo.fossil"), "Home")
    assert content == "# Welcome"
    mock_run_fossil.assert_called_once_with(["wiki", "export", "Home", "-R", "repo.fossil"])


# -- forum tests -----------------------------------------------------------


@patch("magpie_fossil.forum.run_fossil")
@patch("magpie_fossil.forum.query_db")
def test_list_forum_threads(mock_query_db: MagicMock, mock_run_fossil: MagicMock) -> None:
    mock_query_db.return_value = [{"root_uuid": "uuid1"}]
    mock_run_fossil.return_value = "U alice\nD 2026-07-02T12:00:00.000\nW Thread 1\nZ checksum\nBody content"
    threads = list_forum_threads(Path("repo.fossil"))
    assert len(threads) == 1
    assert threads[0]["title"] == "Thread 1"
    assert threads[0]["author"] == "alice"


@patch("magpie_fossil.forum.run_fossil")
@patch("magpie_fossil.forum.query_db")
def test_read_forum_thread(mock_query_db: MagicMock, mock_run_fossil: MagicMock) -> None:
    mock_query_db.side_effect = [[{"rid": 10}], [{"uuid": "uuid1", "parent_uuid": None}]]
    mock_run_fossil.return_value = "U bob\nD 2026-07-02T12:00:00.000\nW Thread 1\nZ checksum\nPost content"
    posts = read_forum_thread(Path("repo.fossil"), "uuid1")
    assert len(posts) == 1
    assert posts[0]["author"] == "bob"
    assert posts[0]["body"] == "Post content"


# -- CLI and client tests --------------------------------------------------


@patch("magpie_fossil.cli.find_repo_db")
@patch("magpie_fossil.cli.ticket.list_tickets")
def test_cli_ticket_list(
    mock_list: MagicMock, mock_find: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_find.return_value = Path("repo.fossil")
    mock_list.return_value = [{"tkt_uuid": "uuid1"}]

    with patch("pathlib.Path.exists", return_value=True):
        code = main(["ticket", "list"])
        assert code == 0
        captured = capsys.readouterr()
        assert "uuid1" in captured.out


@patch("magpie_fossil.cli.find_repo_db")
def test_cli_no_repo(mock_find: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
    mock_find.return_value = None
    code = main(["ticket", "list"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Fossil repository database file not found" in captured.err


@patch("magpie_fossil.cli.find_repo_db")
@patch("magpie_fossil.cli.wiki.read_wiki")
def test_cli_wiki_read(
    mock_read: MagicMock, mock_find: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_find.return_value = Path("repo.fossil")
    mock_read.return_value = "# Markdown Content"

    with patch("pathlib.Path.exists", return_value=True):
        code = main(["wiki", "read", "Home"])
        assert code == 0
        captured = capsys.readouterr()
        assert captured.out == "# Markdown Content"
