# SPDX-License-Identifier: Apache-2.0
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

"""Exercise full-text search through the CLI with an offline Discourse transport."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from typing import Any

import pytest

from magpie_discourse import client, topics
from magpie_discourse import main as package_main

BASE = "https://forum.example.test/community"
QUERY = "packaging"
DATE = "2026-10-20T12:34:56Z"


def post(post_id: int, topic_id: int, number: int = 1, **fields: Any) -> dict[str, Any]:
    return {
        "id": post_id,
        "topic_id": topic_id,
        "post_number": number,
        "username": "alice",
        "created_at": DATE,
        "blurb": "A <span class='search-highlight'>match</span> 🐦",
        **fields,
    }


def page(*posts: dict[str, Any], more: bool | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"posts": list(posts), "grouped_search_result": {"more_full_page_results": more}}
    if posts:
        # Sideloaded topic order need not match post ranking.
        result["topics"] = [
            {"id": n, "title": f"Topic {n}"} for n in reversed(dict.fromkeys(p["topic_id"] for p in posts))
        ]
    return result


def serve(monkeypatch: pytest.MonkeyPatch, *pages: Any, query: str = QUERY) -> list[int]:
    monkeypatch.setenv("DISCOURSE_URL", BASE)
    monkeypatch.delenv("DISCOURSE_API_KEY", raising=False)
    monkeypatch.delenv("DISCOURSE_API_USERNAME", raising=False)
    requested: list[int] = []

    def open_request(request: urllib.request.Request, timeout: float, *, base_url: str) -> io.BytesIO:
        assert request.get_method() == "GET"
        assert request.full_url.partition("?")[0] == f"{BASE}/search.json"
        assert base_url == BASE
        assert not request.has_header("Api-key")
        number = len(requested) + 1
        assert urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query) == {
            "q": [query],
            "page": [str(number)],
        }
        requested.append(number)
        reply = pages[number - 1]
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(reply if isinstance(reply, bytes) else json.dumps(reply).encode())

    monkeypatch.setattr(client, "_urlopen", open_request)
    return requested


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = package_main(["topic", "search", *args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_search_joins_hits_in_native_order_and_preserves_the_query(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    query = "  封装 & C++ #core after:2025-01-01 order:latest  "
    first = post(61, 8, 4)
    last = post(73, 8, 11, username=None, blurb="")
    # Include a later hit for an already retained topic on the last fetched page.
    requested = serve(
        monkeypatch,
        page(first, post(72, 3), more=True),
        page(first, post(80, 6), last, more=True),
        query=query,
    )
    code, out, err = run(capsys, query, "--limit", "2")
    assert (code, err, requested) == (0, "", [1, 2])
    result = json.loads(out)
    assert result["query"] == query
    assert (result["truncated"], result["server_limit_reached"]) == (True, False)
    assert [row["thread_id"] for row in result["threads"]] == ["8", "3"]
    thread = result["threads"][0]
    assert thread == {
        "thread_id": "8",
        "subject": "Topic 8",
        "permalink": f"{BASE}/t/8",
        "matches": [
            {
                "message_id": "61",
                "post_number": 4,
                "from": "@alice",
                "date": DATE,
                "excerpt": first["blurb"],
                "url": f"{BASE}/t/8/4",
            },
            {
                "message_id": "73",
                "post_number": 11,
                "from": None,
                "date": DATE,
                "excerpt": "",
                "url": f"{BASE}/t/8/11",
            },
        ],
    }
    assert out.isascii()
    config = client.load_config()
    assert topics.parse_topic_ref(thread["permalink"], config) == 8
    assert topics.parse_topic_ref(thread["matches"][0]["url"], config) == 8


def test_query_starting_with_dash_after_option_terminator(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    query = "-tags:foo"
    requested = serve(monkeypatch, page(), query=query)
    code, out, err = run(capsys, "--limit", "5", "--", query)
    assert (code, err, requested) == (0, "", [1])
    assert json.loads(out)["query"] == query


@pytest.mark.parametrize("query", ["a b c", "in:title"])
def test_null_group_on_first_page_suggests_adding_or_lengthening_a_keyword(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, query: str
) -> None:
    requested = serve(monkeypatch, {"grouped_search_result": None}, query=query)
    code, out, err = run(capsys, query)
    assert (code, out, requested) == (1, "", [1])
    assert err == (
        "magpie-discourse error: No searchable terms remain in this query. "
        "Try adding a keyword or using a longer one.\n"
    )


def test_null_group_during_lookahead_reports_the_page(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    requested = serve(monkeypatch, page(post(1, 1), more=True), {"grouped_search_result": None})
    code, out, err = run(capsys, QUERY, "--limit", "1")
    assert (code, out, requested) == (1, "", [1, 2])
    assert err == "magpie-discourse error: Discourse returned a null search result group on page 2.\n"


@pytest.mark.parametrize("payload", [{}, {"grouped_search_result": []}])
def test_missing_or_malformed_group_is_a_response_error(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, payload: dict[str, Any]
) -> None:
    serve(monkeypatch, payload)
    code, out, err = run(capsys, QUERY)
    assert (code, out, err) == (
        1,
        "",
        "magpie-discourse error: Discourse returned invalid grouped search results\n",
    )


@pytest.mark.parametrize("more", [None, False])
def test_empty_search_allows_omitted_topics(monkeypatch: pytest.MonkeyPatch, capsys: Any, more: Any) -> None:
    query = "鸟"
    requested = serve(monkeypatch, page(more=more), query=query)
    code, out, err = run(capsys, query)
    assert (code, err, requested) == (0, "", [1])
    assert json.loads(out) == {
        "query": query,
        "threads": [],
        "truncated": False,
        "server_limit_reached": False,
    }


def test_exact_limit_counts_topics_across_pages(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    requested = serve(monkeypatch, page(post(4, 3), more=True), page(post(4, 3), post(7, 3, 2)))
    code, out, err = run(capsys, QUERY, "--limit", "1")
    assert (code, err, requested) == (0, "", [1, 2])
    data = json.loads(out)
    assert not data["truncated"] and not data["server_limit_reached"]
    assert [hit["message_id"] for hit in data["threads"][0]["matches"]] == ["4", "7"]


def test_default_limit_is_one_hundred_topics(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    requested = serve(monkeypatch, page(*(post(n, n) for n in range(1, 102)), more=True))
    code, out, err = run(capsys, QUERY)
    assert (code, err, requested) == (0, "", [1])
    result = json.loads(out)
    assert len(result["threads"]) == 100
    assert result["truncated"] and not result["server_limit_reached"]


@pytest.mark.parametrize("more", [True, False])
@pytest.mark.parametrize("extra_topic", [True, False])
def test_tenth_page_reports_independent_limits(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, more: bool, extra_topic: bool
) -> None:
    pages = [page(post(n, 1, n), more=True) for n in range(1, 10)]
    pages.append(page(post(10, 2 if extra_topic else 1, 10), more=more))
    requested = serve(monkeypatch, *pages)
    code, out, err = run(capsys, QUERY, "--limit", "1")
    assert (code, err, requested) == (0, "", list(range(1, 11)))
    data = json.loads(out)
    assert data["truncated"] is extra_topic
    assert data["server_limit_reached"] is more
    assert len(data["threads"][0]["matches"]) == (9 if extra_topic else 10)


@pytest.mark.parametrize("args", [["  "], [QUERY, "--limit", "0"], [QUERY, "--limit", "-1"]])
def test_bad_input_fails_before_http(monkeypatch: pytest.MonkeyPatch, capsys: Any, args: list[str]) -> None:
    requested = serve(monkeypatch)
    code, out, err = run(capsys, *args)
    assert (code, out, requested) == (1, "", [])
    assert err


@pytest.mark.parametrize(
    "bad",
    [
        {"posts": []},
        {"grouped_search_result": {"more_full_page_results": None}},
        {**page(), "topics": None},
        {**page(), "grouped_search_result": {"more_full_page_results": "true"}},
        page(more=True),
        {**page(post(3, 2)), "topics": []},
        {**page(post(3, 2)), "topics": [{"id": True, "title": "invalid"}]},
        {**page(post(3, 2)), "topics": [{"id": 2, "title": 8}]},
        {**page(post(3, 2)), "posts": [None]},
    ],
)
def test_unusable_lookahead_page_fails_without_output(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, bad: Any
) -> None:
    requested = serve(monkeypatch, page(post(1, 1), more=True), bad)
    code, out, err = run(capsys, QUERY, "--limit", "1")
    assert (code, out, requested) == (1, "", [1, 2])
    assert err


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", True),
        ("topic_id", True),
        ("post_number", 0),
        ("username", []),
        ("created_at", None),
        ("blurb", None),
    ],
)
def test_malformed_hit_after_extra_topic_fails_the_entire_page(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, field: str, value: Any
) -> None:
    payload = page(post(1, 1), post(2, 2), post(3, 1, 3))
    payload["posts"][-1][field] = value
    serve(monkeypatch, payload)
    code, out, err = run(capsys, QUERY, "--limit", "1")
    assert (code, out) == (1, "")
    assert err


def test_repeated_nonconsecutive_page_with_continuation_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    first = page(post(1, 1), more=True)
    requested = serve(monkeypatch, first, page(post(2, 1, 2), more=True), first)
    code, out, err = run(capsys, QUERY)
    assert (code, out, requested) == (1, "", [1, 2, 3])
    assert "repeated" in err


@pytest.mark.parametrize("status", [403, 404, 429])
def test_http_errors_during_default_limit_lookahead(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, status: int
) -> None:
    headers = Message()
    headers["Retry-After"] = "12"
    failure = urllib.error.HTTPError(BASE, status, "error", headers, io.BytesIO(b"{}"))
    first = page(*(post(n, n) for n in range(1, 51)), more=True)
    second = page(*(post(n, n) for n in range(51, 101)), more=True)
    requested = serve(monkeypatch, first, second, failure)
    code, out, err = run(capsys, QUERY)
    assert (code, out, requested) == (1, "", [1, 2, 3])
    assert str(status) in err
    if status == 429:
        assert "12 seconds" in err


@pytest.mark.parametrize(
    "reply,reason",
    [
        (TimeoutError(), "Timed out"),
        (b"not JSON", "not JSON"),
        (
            {
                **page(),
                "grouped_search_result": {"error": "Search is overloaded", "more_full_page_results": None},
            },
            "Search is overloaded",
        ),
    ],
)
def test_read_failures_are_distinct_from_no_matches(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, reply: Any, reason: str
) -> None:
    serve(monkeypatch, reply)
    code, out, err = run(capsys, QUERY)
    assert (code, out) == (1, "")
    assert reason in err
