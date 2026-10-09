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

"""Regression tests for reference.paginated_search.

Guards the cursor-insertion bug (PR #348 review blocker): the old code did
``cmd.insert(4, "-F"); cmd.insert(5, f"after={cursor}")`` which produced two
``-F`` flags in a row and silently stopped pagination after page 1. Also
covers the retry/backoff and partial-fetch signalling added alongside the fix.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from pr_management.stats import reference


def _resp(returncode=0, payload=None, stderr=""):
    stdout = json.dumps(payload) if payload is not None else ""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _page(numbers, *, has_next, cursor=None):
    return {
        "data": {
            "search": {
                "nodes": [{"number": n} for n in numbers],
                "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
            }
        }
    }


def test_paginates_all_pages_and_builds_clean_cursor_argv(monkeypatch):
    """Page 2 must carry exactly one well-formed `-F after=<cursor>` pair."""
    pages = [
        _resp(payload=_page([1, 2], has_next=True, cursor="CURSOR1")),
        _resp(payload=_page([3], has_next=False)),
    ]
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return pages[len(calls) - 1]

    monkeypatch.setattr(reference.subprocess, "run", fake_run)

    nodes = reference.paginated_search("QUERY", "search q", page_size=30, max_pages=5)

    # All pages fetched — the bug truncated this to just [1, 2].
    assert [n["number"] for n in nodes] == [1, 2, 3]

    page2 = calls[1]
    # Exactly one cursor field, immediately preceded by its -F flag.
    assert page2.count("after=CURSOR1") == 1
    assert page2[page2.index("after=CURSOR1") - 1] == "-F"
    # The old bug produced two consecutive -F tokens; assert that never happens.
    assert not any(page2[i] == "-F" and page2[i + 1] == "-F" for i in range(len(page2) - 1))
    # Page 1 carries no cursor at all.
    assert not any(tok.startswith("after=") for tok in calls[0])


def test_partial_flag_set_on_hard_error(monkeypatch):
    monkeypatch.setattr(
        reference.subprocess,
        "run",
        lambda cmd, capture_output, text: _resp(returncode=1, stderr="fatal: nope"),
    )
    status: dict[str, bool] = {}
    nodes = reference.paginated_search("Q", "q", max_retries=0, status=status)
    assert nodes == []
    assert status["partial"] is True


def test_partial_flag_set_when_max_pages_hit(monkeypatch):
    # Every page claims there is another page → we cap out and must flag partial.
    monkeypatch.setattr(
        reference.subprocess,
        "run",
        lambda cmd, capture_output, text: _resp(payload=_page([1], has_next=True, cursor="C")),
    )
    status: dict[str, bool] = {}
    nodes = reference.paginated_search("Q", "q", max_pages=3, status=status)
    assert len(nodes) == 3
    assert status["partial"] is True


def test_partial_false_on_clean_finish(monkeypatch):
    monkeypatch.setattr(
        reference.subprocess,
        "run",
        lambda cmd, capture_output, text: _resp(payload=_page([1], has_next=False)),
    )
    status: dict[str, bool] = {}
    reference.paginated_search("Q", "q", status=status)
    assert status["partial"] is False


def test_retry_on_transient_then_success(monkeypatch):
    responses = iter(
        [
            _resp(returncode=1, stderr="HTTP 502 Bad Gateway"),
            _resp(payload=_page([7], has_next=False)),
        ]
    )
    monkeypatch.setattr(
        reference.subprocess,
        "run",
        lambda cmd, capture_output, text: next(responses),
    )
    slept = []
    monkeypatch.setattr(reference.time, "sleep", lambda s: slept.append(s))

    status: dict[str, bool] = {}
    nodes = reference.paginated_search("Q", "q", max_retries=1, backoff=0.5, status=status)

    assert [n["number"] for n in nodes] == [7]
    assert status["partial"] is False
    assert slept == [0.5]  # one backoff before the successful retry


def test_rate_limited_graphql_error_is_retried(monkeypatch):
    responses = iter(
        [
            _resp(payload={"errors": [{"type": "RATE_LIMITED", "message": "slow down"}]}),
            _resp(payload=_page([9], has_next=False)),
        ]
    )
    monkeypatch.setattr(
        reference.subprocess,
        "run",
        lambda cmd, capture_output, text: next(responses),
    )
    monkeypatch.setattr(reference.time, "sleep", lambda s: None)

    nodes = reference.paginated_search("Q", "q", max_retries=1, backoff=0)
    assert [n["number"] for n in nodes] == [9]


def test_non_transient_error_not_retried(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return _resp(returncode=1, stderr="permission denied")

    monkeypatch.setattr(reference.subprocess, "run", fake_run)
    monkeypatch.setattr(reference.time, "sleep", lambda s: None)

    status: dict[str, bool] = {}
    reference.paginated_search("Q", "q", max_retries=3, status=status)
    # No retries for a non-transient failure → exactly one subprocess call.
    assert len(calls) == 1
    assert status["partial"] is True
