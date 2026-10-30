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

"""Offline CLI regressions for category discovery and recent-topic pagination."""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from typing import Any

import pytest

from magpie_discourse import client
from magpie_discourse import main as package_main

BASE = "https://forum.example.test"
DATE = "2026-10-20T12:00:00.000Z"
CATEGORY = {"id": 7, "slug": "dev", "name": "Development"}


def topic(topic_id: int, **fields: Any) -> dict[str, Any]:
    return {
        "id": topic_id,
        "title": f"Proposal {topic_id}",
        "created_at": "2026-10-01T00:00:00Z",
        "bumped_at": DATE,
        "last_posted_at": "2026-10-02T00:00:00Z",
        "posts_count": 2,
        "tags": ["python", {"id": 1, "name": "design", "slug": "design"}],
        "pinned": False,
        "closed": False,
        "archived": False,
        **fields,
    }


def page(rows: Any, more: Any = None) -> dict[str, Any]:
    return {"topic_list": {"topics": rows, "more_topics_url": more}}


def next_url(number: int, category: int = 7) -> str:
    return f"/latest?category={category}&order=activity&ascending=false&no_subcategories=false&page={number}"


@pytest.fixture(autouse=True)
def forum_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCOURSE_URL", BASE)
    monkeypatch.delenv("DISCOURSE_API_KEY", raising=False)
    monkeypatch.delenv("DISCOURSE_API_USERNAME", raising=False)


def serve(
    monkeypatch: pytest.MonkeyPatch, pages: dict[int, Any], **routes: Any
) -> list[urllib.request.Request]:
    requests: list[urllib.request.Request] = []
    replies = {"/c/7/show.json": {"category": CATEGORY}, **routes}

    def open_request(request: urllib.request.Request, timeout: float, *, base_url: str) -> io.BytesIO:
        assert timeout == 30
        requests.append(request)
        parsed = urllib.parse.urlsplit(request.full_url)
        prefix = urllib.parse.urlsplit(base_url).path
        path = parsed.path[len(prefix) :]
        if path == "/latest.json":
            params = urllib.parse.parse_qs(parsed.query)
            reply = pages[int(params["page"][0])]
        else:
            reply = replies[path]
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(reply if isinstance(reply, bytes) else json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(client, "_urlopen", open_request)
    return requests


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    status = package_main(["topic", "list", "--category", "7", *args])
    output = capsys.readouterr()
    return status, output.out, output.err


def test_list_uses_activity_order_and_keeps_message_time_separate(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    requests = serve(monkeypatch, {0: page([topic(42, title="设计 🐦", pinned=True)])})
    status, out, err = run(capsys, "--since", "2026-10-20T20:00:00+08:00")
    assert (status, err) == (0, "")
    data = json.loads(out)
    assert data == {
        "category": CATEGORY,
        "since": "2026-10-20T12:00:00Z",
        "threads": [
            {
                "thread_id": "42",
                "subject": "设计 🐦",
                "first_message_date": "2026-10-01T00:00:00Z",
                "last_message_date": "2026-10-02T00:00:00Z",
                "bumped_at": DATE,
                "message_count": 2,
                "permalink": f"{BASE}/t/42",
                "tags": ["python", "design"],
                "pinned": True,
                "closed": False,
                "archived": False,
            }
        ],
        "truncated": False,
    }
    assert out.isascii()
    assert len(requests) == 2
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(requests[-1].full_url).query)
    assert query == {
        "category": ["7"],
        "order": ["activity"],
        "ascending": ["false"],
        "no_subcategories": ["false"],
        "page": ["0"],
    }
    assert all(request.get_method() == "GET" for request in requests)


def test_old_about_pin_counts_towards_limit_without_since(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    about = topic(1, title="About the Development category", pinned=True, bumped_at="2020-01-01T00:00:00Z")
    requests = serve(monkeypatch, {0: page([about, topic(2)])})
    status, out, err = run(capsys, "--limit", "1")
    assert (status, err) == (0, "")
    result = json.loads(out)
    assert result["since"] is None and result["truncated"] is True
    assert [row["thread_id"] for row in result["threads"]] == ["1"]
    assert result["threads"][0]["pinned"] is True
    assert [row for row in result["threads"] if not row["pinned"]] == []
    assert len(requests) == 2


def test_cutoff_after_old_pins_matches_and_overlap_stops_pagination(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    requests = serve(
        monkeypatch,
        {
            0: page([topic(1, pinned=True, bumped_at="2020-01-01T00:00:00Z"), topic(2)], next_url(1)),
            1: page([topic(2), topic(3, bumped_at="2020-01-01T00:00:00Z")], next_url(2)),
        },
    )
    status, out, err = run(capsys, "--since", "2026-10-20", "--limit", "1")
    assert (status, err) == (0, "")
    assert [t["thread_id"] for t in json.loads(out)["threads"]] == ["2"]
    assert json.loads(out)["truncated"] is False
    assert len(requests) == 3  # category + two pages, stopping at an old non-pinned topic


@pytest.mark.parametrize("tail", [[], [topic(1)], [topic(2, bumped_at="2020-01-01T00:00:00Z")]])
def test_exact_limit_is_not_truncated_without_an_extra_match(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, tail: Any
) -> None:
    requests = serve(monkeypatch, {0: page([topic(1)], next_url(1)), 1: page(tail)})
    status, out, err = run(capsys, "--limit", "1", "--since", "2026-10-20")
    assert (status, err) == (0, "")
    assert json.loads(out)["truncated"] is False
    assert len(requests) == 3


def test_filtering_precedes_deduplication(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    serve(
        monkeypatch,
        {
            0: page([topic(1, pinned=True, bumped_at="2020-01-01T00:00:00Z")], next_url(1)),
            1: page([topic(1, title="New activity")]),
        },
    )
    status, out, err = run(capsys, "--since", "2026-10-20")
    assert (status, err) == (0, "")
    assert json.loads(out)["threads"][0]["subject"] == "New activity"


@pytest.mark.parametrize("last", [None, "missing"])
def test_missing_message_time_never_falls_back_to_activity(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, last: Any
) -> None:
    row = topic(1, last_posted_at=last)
    if last == "missing":
        del row["last_posted_at"]
    serve(monkeypatch, {0: page([row])})
    status, out, err = run(capsys, "--since", "2026-10-20")
    assert (status, err) == (0, "")
    assert json.loads(out)["threads"][0]["last_message_date"] is None


@pytest.mark.parametrize(
    "ref",
    [
        "7",
        "dev/core/7",
        "/c/dev/7",
        "/c/dev/7/",
        "讨论/提案/7",
        BASE + "/c/dev/7",
        BASE + "/c/讨论/提案/7/?order=likes#share",
        BASE + "/c/%E8%AE%A8%E8%AE%BA/7",
    ],
)
def test_id_references_read_only_numeric_category_endpoints(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, ref: str
) -> None:
    requests = serve(monkeypatch, {0: page([])})
    status, out, err = run(capsys, "--category", ref)
    assert (status, err) == (0, "")
    assert json.loads(out)["category"] == CATEGORY
    assert [urllib.parse.urlsplit(request.full_url).path for request in requests] == [
        "/c/7/show.json",
        "/latest.json",
    ]


@pytest.mark.parametrize("ref", ["讨论", "%E8%AE%A8%E8%AE%BA"])
def test_unicode_top_level_slug_is_matched_without_entering_request_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, ref: str
) -> None:
    selected = {**CATEGORY, "slug": "%E8%AE%A8%E8%AE%BA", "name": "讨论"}
    catalog = {"category_list": {"categories": [selected]}}
    requests = serve(monkeypatch, {0: page([])}, **{"/categories.json": catalog})
    status, out, err = run(capsys, "--category", ref)
    assert (status, err) == (0, "")
    assert json.loads(out)["category"] == selected
    assert [urllib.parse.urlsplit(request.full_url).path for request in requests] == [
        "/categories.json",
        "/latest.json",
    ]


def test_bare_slug_selects_only_a_confirmed_top_level_category(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    selected = {**CATEGORY, "slug": "core"}
    catalog = {
        "category_list": {
            "categories": [
                {
                    "id": 1,
                    "slug": "dev",
                    "name": "Parent",
                    "subcategory_list": [{"id": 2, "slug": "core", "name": "Child"}],
                },
                {"id": 3, "slug": "core", "name": "Orphan", "parent_category_id": 99},
                selected,
            ]
        }
    }
    serve(monkeypatch, {0: page([])}, **{"/categories.json": catalog})
    status, out, err = run(capsys, "--category", "core")
    assert (status, err) == (0, "")
    assert json.loads(out)["category"] == selected


@pytest.mark.parametrize(
    "categories",
    [
        [],
        [{"id": 1, "slug": "parent", "name": "Parent", "subcategory_list": [CATEGORY]}],
        [{**CATEGORY, "parent_category_id": 99}],
        [CATEGORY, {**CATEGORY, "id": 8}],
    ],
)
def test_incomplete_or_ambiguous_root_catalog_suggests_an_id(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, categories: list[dict[str, Any]]
) -> None:
    catalog = {"category_list": {"categories": categories}}
    requests = serve(monkeypatch, {}, **{"/categories.json": catalog})
    status, out, err = run(capsys, "--category", "dev")
    assert status == 1 and out == "" and "numeric id" in err.lower()
    assert len(requests) == 1


def test_unusable_catalog_slugs_do_not_block_an_independent_root(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    categories = [
        {**CATEGORY, "id": i, "slug": slug}
        for i, slug in enumerate(["", "bad%zz", "encoded%2fseparator"], start=10)
    ] + [CATEGORY]
    serve(monkeypatch, {0: page([])}, **{"/categories.json": {"category_list": {"categories": categories}}})
    status, out, err = run(capsys, "--category", "dev")
    assert (status, err) == (0, "") and json.loads(out)["category"] == CATEGORY


def test_numeric_id_does_not_require_a_slug(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    selected = {**CATEGORY, "slug": ""}
    requests = serve(monkeypatch, {0: page([])}, **{"/c/7/show.json": {"category": selected}})
    status, out, err = run(capsys)
    assert (status, err) == (0, "") and json.loads(out)["category"] == selected
    assert len(requests) == 2


def test_manual_path_without_id_fails_with_migration_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    catalog = {
        "category_list": {
            "categories": [
                {"id": 1, "slug": "dev", "name": "Dev", "subcategory_list": [{**CATEGORY, "slug": "core"}]}
            ]
        }
    }
    requests = serve(monkeypatch, {0: page([])}, **{"/categories.json": catalog})
    status, out, err = run(capsys, "--category", "dev/core")
    assert status == 1 and out == "" and "numeric id" in err.lower()
    assert requests == []


@pytest.mark.parametrize(
    "args",
    [
        ["--limit", "0"],
        ["--limit", "-1"],
        ["--category", "0"],
        ["--category", "\uff14\uff12"],
        ["--category", "-7"],
        ["--category", "dev%2fcore"],
        ["--category", "%2564ev"],
        ["--category", "%zz"],
        ["--since", "2026-02-30"],
        ["--since", "2026-10-20T12:00:00"],
        ["--since", "2026-10-20T12:00:00.1234567Z"],
    ],
)
def test_invalid_list_inputs_fail_before_any_request(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, args: list[str]
) -> None:
    requests = serve(monkeypatch, {})
    status, out, err = run(capsys, *args)
    assert status == 1 and out == "" and "magpie-discourse error:" in err
    assert requests == []


@pytest.mark.parametrize(
    "ref",
    [
        "https://other.example/c/dev/7",
        "//evil.example/c/x/7",
        "://bad/c/dev/7",
        BASE + "/t/dev/7",
        BASE + "/c/dev/0",
    ],
)
def test_invalid_category_urls_fail_before_any_request(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, ref: str
) -> None:
    requests = serve(monkeypatch, {})
    status, out, err = run(capsys, "--category", ref)
    assert status == 1 and out == "" and "magpie-discourse error:" in err
    assert requests == []


@pytest.mark.parametrize("ref", [BASE + "/c/dev/7", BASE + "/forum-other/c/dev/7", "/forum-other/c/dev/7"])
def test_category_url_cannot_leave_the_configured_subfolder(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, ref: str
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", BASE + "/forum")
    requests = serve(monkeypatch, {})
    status, out, err = run(capsys, "--category", ref)
    assert status == 1 and out == "" and "magpie-discourse error:" in err
    assert requests == []


@pytest.mark.parametrize(
    "bumped,expected",
    [
        ("2026-10-20T00:00:00Z", True),
        ("2026-10-19T23:59:59.999999Z", False),
        ("2026-10-20T08:00:00+08:00", True),
    ],
)
def test_since_is_inclusive_utc_midnight(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, bumped: str, expected: bool
) -> None:
    serve(monkeypatch, {0: page([topic(1, bumped_at=bumped)])})
    status, out, err = run(capsys, "--since", "2026-10-20")
    assert (status, err) == (0, "")
    assert bool(json.loads(out)["threads"]) is expected


@pytest.mark.parametrize(
    "target",
    [
        "/latest?ascending=false&category=7&no_subcategories=false&order=activity&page=1",
        next_url(1) + "&new_server_option=value",
        "https://other.example/ignored?category=8&order=likes&page=99#fragment",
    ],
)
def test_continuation_is_only_a_signal_and_requests_keep_fixed_scope(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, target: str
) -> None:
    requests = serve(monkeypatch, {0: page([topic(1)], target), 1: page([])})
    status, out, err = run(capsys, "--limit", "1")
    assert (status, err) == (0, "") and json.loads(out)["truncated"] is False
    assert len(requests) == 3
    for number, request in enumerate(requests[1:]):
        parsed = urllib.parse.urlsplit(request.full_url)
        assert parsed.scheme == "https" and parsed.netloc == "forum.example.test"
        assert parsed.path == "/latest.json"
        assert urllib.parse.parse_qs(parsed.query) == {
            "category": ["7"],
            "order": ["activity"],
            "ascending": ["false"],
            "no_subcategories": ["false"],
            "page": [str(number)],
        }


@pytest.mark.parametrize("ending", [None, "", "missing"])
def test_absent_continuation_ends_the_list(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, ending: str | None
) -> None:
    reply = page([topic(1)], ending)
    if ending == "missing":
        del reply["topic_list"]["more_topics_url"]
    requests = serve(monkeypatch, {0: reply})
    status, out, err = run(capsys)
    assert (status, err) == (0, "") and json.loads(out)["truncated"] is False
    assert len(requests) == 2


def test_continuation_type_is_checked_even_with_an_extra_match(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    serve(monkeypatch, {0: page([topic(1), topic(2)], True)})
    status, out, err = run(capsys, "--limit", "1")
    assert status == 1 and out == "" and "magpie-discourse error:" in err


@pytest.mark.parametrize("ref", [BASE + "/forum/c/dev/core/7/?share=1", "/forum/c/dev/7", "/c/dev/7"])
def test_subfolder_category_url_and_pagination_keep_credentials_on_the_forum(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, ref: str
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", BASE + "/forum")
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "reader")
    requests = serve(monkeypatch, {0: page([topic(1)], "https://other.example/ignored"), 1: page([])})
    status, out, err = run(capsys, "--category", ref, "--limit", "1")
    assert (status, err) == (0, "")
    assert json.loads(out)["threads"][0]["permalink"] == BASE + "/forum/t/1"
    assert len(requests) == 3
    assert all(request.full_url.startswith(BASE + "/forum/") for request in requests)
    assert all(request.get_method() == "GET" for request in requests)
    assert all(
        request.get_header("Api-key") == "test-key" and request.get_header("Api-username") == "reader"
        for request in requests
    )


@pytest.mark.parametrize("suffix", ["/none", "/l/latest", ".json"])
def test_category_view_suffixes_fail_with_a_clear_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, suffix: str
) -> None:
    requests = serve(monkeypatch, {})
    status, out, err = run(capsys, "--category", "/c/dev/7" + suffix)
    assert status == 1 and out == "" and "not supported" in err
    assert "/c/" in err and "numeric id" in err
    assert requests == []


@pytest.mark.parametrize("ids", [[[1], [1]], [[1], [2], [1]], [[]]])
def test_empty_or_replayed_pages_cannot_continue(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, ids: list[list[int]]
) -> None:
    pages = {
        number: page([topic(i) for i in items], next_url(number + 1)) for number, items in enumerate(ids)
    }
    requests = serve(monkeypatch, pages)
    status, out, err = run(capsys, "--limit", "5")
    assert status == 1 and out == "" and "paginat" in err.lower()
    assert len(requests) == len(ids) + 1


@pytest.mark.parametrize("code", [403, 404, 429])
def test_lookahead_http_failure_is_not_partial_success(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, code: int
) -> None:
    headers = Message()
    headers["Retry-After"] = "10"
    failure = urllib.error.HTTPError(
        BASE + "/latest.json", code, "failure", headers, io.BytesIO(b'{"errors":["unavailable"]}')
    )
    requests = serve(monkeypatch, {0: page([topic(1)], next_url(1)), 1: failure})
    status, out, err = run(capsys, "--limit", "1")
    assert status == 1 and out == "" and str(code) in err
    if code == 429:
        assert "10 seconds" in err
    assert len(requests) == 3


@pytest.mark.parametrize("reply", [b"not JSON", {}, TimeoutError()])
def test_bad_lookahead_does_not_return_partial_success(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, reply: Any
) -> None:
    serve(monkeypatch, {0: page([topic(1)], next_url(1)), 1: reply})
    status, out, err = run(capsys, "--limit", "1")
    assert status == 1 and out == "" and "magpie-discourse error:" in err


@pytest.mark.parametrize(
    "field,value",
    [("bumped_at", "bad"), ("title", None), ("created_at", "missing"), ("tags", [{}]), ("pinned", "false")],
)
def test_invalid_summary_fields_fail_the_read(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, field: str, value: Any
) -> None:
    row = topic(1, **{field: value})
    if value == "missing":
        del row[field]
    serve(monkeypatch, {0: page([row])})
    status, out, err = run(capsys)
    assert status == 1 and out == "" and "magpie-discourse error:" in err


def test_received_records_beyond_the_limit_are_still_validated(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    serve(monkeypatch, {0: page([topic(1), topic(2), topic(3, posts_count=None)])})
    status, out, err = run(capsys, "--limit", "1")
    assert status == 1 and out == "" and "magpie-discourse error:" in err


def test_default_limit_looks_for_one_extra_unique_match(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    serve(monkeypatch, {0: page([topic(i) for i in range(1, 102)])})
    status, out, err = run(capsys)
    assert (status, err) == (0, "")
    data = json.loads(out)
    assert len(data["threads"]) == 100 and data["truncated"] is True and data["since"] is None


def test_list_permalink_can_be_viewed_by_pr1(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    serve(
        monkeypatch,
        {0: page([topic(42)])},
        **{
            "/t/42.json": {
                "id": 42,
                "title": "Proposal",
                "slug": "proposal",
                "posts_count": 0,
                "post_stream": {"stream": [], "posts": []},
            }
        },
    )
    assert package_main(["topic", "list", "--category", "7"]) == 0
    permalink = json.loads(capsys.readouterr().out)["threads"][0]["permalink"]
    assert package_main(["topic", "view", permalink]) == 0
    assert json.loads(capsys.readouterr().out)["thread_id"] == "42"


@pytest.mark.parametrize("category", [{**CATEGORY, "id": 8}, {**CATEGORY, "slug": None}])
def test_invalid_direct_category_metadata_stops_before_listing(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, category: dict[str, Any]
) -> None:
    requests = serve(monkeypatch, {}, **{"/c/7/show.json": {"category": category}})
    status, out, err = run(capsys)
    assert status == 1 and out == "" and "magpie-discourse error:" in err
    assert len(requests) == 1


@pytest.mark.parametrize("reply", [{}, {"category_list": {"categories": [None]}}])
def test_bad_catalog_is_not_an_empty_result(monkeypatch: pytest.MonkeyPatch, capsys: Any, reply: Any) -> None:
    serve(monkeypatch, {}, **{"/categories.json": reply})
    status, out, err = run(capsys, "--category", "dev")
    assert status == 1 and out == "" and "magpie-discourse error:" in err


def test_optional_flags_and_tags_have_documented_defaults(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    row = topic(1, tags=None)
    for field in ("pinned", "closed", "archived"):
        del row[field]
    serve(monkeypatch, {0: page([row])})
    status, out, err = run(capsys)
    assert (status, err) == (0, "")
    summary = json.loads(out)["threads"][0]
    assert summary["tags"] == []
    assert all(summary[field] is False for field in ("pinned", "closed", "archived"))


def test_empty_category_has_no_threads(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    serve(monkeypatch, {0: page([])})
    status, out, err = run(capsys)
    assert (status, err) == (0, "")
    assert json.loads(out) == {"category": CATEGORY, "since": None, "threads": [], "truncated": False}


def test_large_category_scan_ends_at_the_since_boundary(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    pages = {}
    for number in range(100):
        rows = [
            topic(index + 1, bumped_at=DATE if index < 2 else "2019-01-01T00:00:00Z")
            for index in range(number * 30, (number + 1) * 30)
        ]
        pages[number] = page(rows, next_url(number + 1) if number < 99 else None)
    requests = serve(monkeypatch, pages)
    status, out, err = run(capsys, "--since", "2026-10-20")
    assert (status, err) == (0, "")
    assert [row["thread_id"] for row in json.loads(out)["threads"]] == ["1", "2"]
    assert json.loads(out)["truncated"] is False
    assert len(requests) == 2


def test_missing_pinned_evidence_does_not_trigger_cutoff(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    unknown = topic(1, bumped_at="2019-01-01T00:00:00Z")
    del unknown["pinned"]
    requests = serve(monkeypatch, {0: page([unknown], next_url(1)), 1: page([topic(2), topic(3)])})
    status, out, err = run(capsys, "--since", "2026-10-20", "--limit", "1")
    assert (status, err) == (0, "")
    assert [row["thread_id"] for row in json.loads(out)["threads"]] == ["2"]
    assert json.loads(out)["truncated"] is True
    assert len(requests) == 3


def test_since_equality_and_old_pin_are_not_cutoffs(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    requests = serve(
        monkeypatch,
        {
            0: page(
                [
                    topic(1, pinned=True, bumped_at="2019-01-01T00:00:00Z"),
                    topic(2),
                    topic(3, bumped_at="2026-10-20T11:59:59.999999Z"),
                ],
                next_url(1),
            )
        },
    )
    status, out, err = run(capsys, "--since", DATE, "--limit", "1")
    assert (status, err) == (0, "")
    assert [row["thread_id"] for row in json.loads(out)["threads"]] == ["2"]
    assert json.loads(out)["truncated"] is False
    assert len(requests) == 2


def test_extra_match_before_cutoff_still_proves_truncation(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    requests = serve(monkeypatch, {0: page([topic(1), topic(2), topic(3, bumped_at="2019-01-01T00:00:00Z")])})
    status, out, err = run(capsys, "--since", "2026-10-20", "--limit", "1")
    assert (status, err) == (0, "")
    assert json.loads(out)["truncated"] is True
    assert len(requests) == 2


def test_cutoff_does_not_bypass_received_page_validation(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    serve(monkeypatch, {0: page([topic(1, bumped_at="2019-01-01T00:00:00Z"), topic(2, posts_count=None)])})
    status, out, err = run(capsys, "--since", "2026-10-20")
    assert status == 1 and out == "" and "magpie-discourse error:" in err


def test_oversized_ascii_id_uses_the_conversion_error_channel(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    requests = serve(monkeypatch, {})
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(4300)
        status, out, err = run(capsys, "--category", "9" * 4301)
    finally:
        sys.set_int_max_str_digits(previous)
    assert status == 1 and out == "" and "Invalid category id" in err
    assert requests == []
