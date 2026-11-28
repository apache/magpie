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

from oauth_draft.mark_threads_read import (
    list_thread_ids,
    main,
    modify_thread,
    parse_args,
)


def test_default_action_is_remove_unread():
    args = parse_args(["--query", "in:inbox"])
    assert args.add_label == []
    assert args.remove_label == ["UNREAD"]
    assert args.execute is False
    assert args.max is None


def test_explicit_add_label_does_not_inject_unread_default():
    args = parse_args(["--query", "in:inbox", "--add-label", "STARRED"])
    assert args.add_label == ["STARRED"]
    assert args.remove_label == []


def test_explicit_remove_label_does_not_inject_unread_default():
    args = parse_args(["--query", "in:inbox", "--remove-label", "INBOX"])
    assert args.add_label == []
    assert args.remove_label == ["INBOX"]


def test_repeat_label_flags_accumulate():
    args = parse_args(
        [
            "--query",
            "in:inbox",
            "--add-label",
            "A",
            "--add-label",
            "B",
            "--remove-label",
            "C",
        ]
    )
    assert args.add_label == ["A", "B"]
    assert args.remove_label == ["C"]


def test_execute_and_max_flags():
    args = parse_args(["--query", "x", "--execute", "--max", "5"])
    assert args.execute is True
    assert args.max == 5


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


def test_list_thread_ids_paginates_until_no_token():
    pages = [
        _FakeResponse(
            json.dumps(
                {
                    "threads": [{"id": "t1"}, {"id": "t2"}],
                    "nextPageToken": "page2",
                }
            ).encode()
        ),
        _FakeResponse(json.dumps({"threads": [{"id": "t3"}]}).encode()),
    ]
    with patch(
        "oauth_draft.mark_threads_read.urllib.request.urlopen",
        side_effect=pages,
    ) as mock_open:
        ids = list_thread_ids("token", "in:inbox")
    assert ids == ["t1", "t2", "t3"]
    # Second call must include the pageToken from the first response.
    _, second_call = mock_open.call_args_list
    second_url = second_call.args[0].full_url
    assert "pageToken=page2" in second_url


def test_list_thread_ids_raises_on_http_error():
    err = urllib.error.HTTPError(
        url="https://x",
        code=429,
        msg="Too Many",
        hdrs=None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        fp=io.BytesIO(b'{"error": "rate"}'),
    )
    with patch(
        "oauth_draft.mark_threads_read.urllib.request.urlopen",
        side_effect=err,
    ):
        with pytest.raises(SystemExit) as excinfo:
            list_thread_ids("token", "q")
    assert "threads.list failed (429)" in str(excinfo.value)


def test_modify_thread_sends_label_payload():
    with patch("oauth_draft.mark_threads_read.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(b"{}")
        modify_thread("token", "tid-1", ["STARRED"], ["UNREAD"])
    request = mock_open.call_args.args[0]
    assert request.method == "POST"
    assert "/threads/tid-1/modify" in request.full_url
    payload = json.loads(request.data)
    assert payload == {"addLabelIds": ["STARRED"], "removeLabelIds": ["UNREAD"]}


def test_modify_thread_omits_empty_label_lists():
    with patch("oauth_draft.mark_threads_read.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(b"{}")
        modify_thread("token", "tid-2", [], ["UNREAD"])
    payload = json.loads(mock_open.call_args.args[0].data)
    assert payload == {"removeLabelIds": ["UNREAD"]}


def test_modify_thread_raises_on_http_error():
    err = urllib.error.HTTPError(
        url="https://x",
        code=500,
        msg="Boom",
        hdrs=None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        fp=io.BytesIO(b'{"error": "server"}'),
    )
    with patch(
        "oauth_draft.mark_threads_read.urllib.request.urlopen",
        side_effect=err,
    ):
        with pytest.raises(SystemExit) as excinfo:
            modify_thread("token", "tid", [], ["UNREAD"])
    assert "threads.modify failed (500) for tid" in str(excinfo.value)


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


def test_main_dry_run_lists_ids_and_skips_modify(tmp_path, capsys):
    creds = _make_creds_file(tmp_path)
    with (
        patch(
            "oauth_draft.mark_threads_read.refresh_access_token",
            return_value="tok",
        ),
        patch(
            "oauth_draft.mark_threads_read.list_thread_ids",
            return_value=["t1", "t2"],
        ),
        patch("oauth_draft.mark_threads_read.modify_thread") as modify,
    ):
        rc = main(
            [
                "--credentials",
                str(creds),
                "--query",
                "in:inbox is:unread",
            ]
        )
    assert rc == 0
    modify.assert_not_called()
    out = capsys.readouterr().out
    assert "t1" in out and "t2" in out


def test_main_execute_calls_modify_per_thread(tmp_path):
    creds = _make_creds_file(tmp_path)
    with (
        patch(
            "oauth_draft.mark_threads_read.refresh_access_token",
            return_value="tok",
        ),
        patch(
            "oauth_draft.mark_threads_read.list_thread_ids",
            return_value=["t1", "t2", "t3"],
        ),
        patch("oauth_draft.mark_threads_read.modify_thread") as modify,
    ):
        rc = main(
            [
                "--credentials",
                str(creds),
                "--query",
                "q",
                "--execute",
            ]
        )
    assert rc == 0
    assert modify.call_count == 3
    # default action: remove UNREAD
    for call in modify.call_args_list:
        _, _, add, remove = call.args
        assert add == []
        assert remove == ["UNREAD"]


def test_main_max_truncates(tmp_path):
    creds = _make_creds_file(tmp_path)
    with (
        patch(
            "oauth_draft.mark_threads_read.refresh_access_token",
            return_value="tok",
        ),
        patch(
            "oauth_draft.mark_threads_read.list_thread_ids",
            return_value=["t1", "t2", "t3", "t4", "t5"],
        ),
        patch("oauth_draft.mark_threads_read.modify_thread") as modify,
    ):
        rc = main(
            [
                "--credentials",
                str(creds),
                "--query",
                "q",
                "--execute",
                "--max",
                "2",
            ]
        )
    assert rc == 0
    assert modify.call_count == 2


def test_main_returns_1_when_modify_fails(tmp_path):
    creds = _make_creds_file(tmp_path)
    with (
        patch(
            "oauth_draft.mark_threads_read.refresh_access_token",
            return_value="tok",
        ),
        patch(
            "oauth_draft.mark_threads_read.list_thread_ids",
            return_value=["t1"],
        ),
        patch(
            "oauth_draft.mark_threads_read.modify_thread",
            side_effect=SystemExit("boom"),
        ),
    ):
        rc = main(
            [
                "--credentials",
                str(creds),
                "--query",
                "q",
                "--execute",
            ]
        )
    assert rc == 1
