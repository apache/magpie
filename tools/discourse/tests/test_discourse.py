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

from __future__ import annotations

import http.client
import io
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
from email.message import Message
from typing import Any

import pytest

from magpie_discourse import client, topics
from magpie_discourse import main as package_main
from magpie_discourse.client import DiscourseConfig, DiscourseError, SameOriginRedirectHandler, load_config

BASE = "https://forum.example.test"


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class FakeForum:
    """Serve canned JSON by URL path and record every request."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float, *, base_url: str) -> FakeResponse:
        self.requests.append(request)
        path = urllib.parse.urlparse(request.full_url).path
        reply = self.routes[path]
        if callable(reply):
            reply = reply(request)
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(json.dumps(reply).encode("utf-8"))


def _post(post_id: int, number: int, username: str = "alice", reply_to: int | None = None) -> dict[str, Any]:
    return {
        "id": post_id,
        "post_number": number,
        "username": username,
        "created_at": f"2026-10-0{min(number, 9)}T10:00:00.000Z",
        "updated_at": f"2026-10-0{min(number, 9)}T11:00:00.000Z",
        "cooked": f"<p>post {number}</p>",
        "reply_to_post_number": reply_to,
        "post_type": 1,
    }


def _topic(posts: list[dict[str, Any]], stream: list[int], **extra: Any) -> dict[str, Any]:
    return {
        "id": 42,
        "title": "Proposal: drop Python 3.10",
        "slug": "proposal-drop-python-3-10",
        "category_id": 7,
        "tags": [{"id": 1, "name": "governance", "slug": "governance"}],
        "created_at": "2026-10-01T10:00:00.000Z",
        "last_posted_at": "2026-10-05T10:00:00.000Z",
        "posts_count": len(stream),
        "closed": False,
        "archived": False,
        "post_stream": {"posts": posts, "stream": stream},
        **extra,
    }


@pytest.fixture
def config() -> DiscourseConfig:
    return DiscourseConfig(base_url=BASE, api_key=None, api_username=None)


@pytest.fixture
def forum_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}/")
    monkeypatch.delenv("DISCOURSE_API_KEY", raising=False)
    monkeypatch.delenv("DISCOURSE_API_USERNAME", raising=False)


def _serve(monkeypatch: pytest.MonkeyPatch, routes: dict[str, Any]) -> FakeForum:
    forum = FakeForum(routes)
    monkeypatch.setattr(client, "_urlopen", forum)
    return forum


# --- configuration ---------------------------------------------------------


def test_load_config_strips_the_trailing_slash(forum_env: None) -> None:
    assert load_config() == DiscourseConfig(base_url=BASE, api_key=None, api_username=None)


@pytest.mark.parametrize(
    "url",
    ["", "http://forum.example.test", "forum.example.test", "https://u:p@forum.example.test", f"{BASE}/?x=1"],
)
def test_load_config_rejects_unusable_urls(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DISCOURSE_URL", url)
    with pytest.raises(DiscourseError):
        load_config()


def test_api_key_needs_a_username(forum_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCOURSE_API_KEY", "secret")
    with pytest.raises(DiscourseError, match="DISCOURSE_API_USERNAME"):
        load_config()


def test_auth_headers_are_sent_only_with_a_key(config: DiscourseConfig) -> None:
    assert client.auth_headers(config) == {}
    keyed = DiscourseConfig(base_url=BASE, api_key="secret", api_username="magpie-bot")
    assert client.auth_headers(keyed) == {"Api-Key": "secret", "Api-Username": "magpie-bot"}


# --- topic references -------------------------------------------------------


@pytest.mark.parametrize(
    "ref",
    [
        "42",
        f"{BASE}/t/proposal-drop-python-3-10/42",
        f"{BASE}/t/proposal-drop-python-3-10/42/7",
        f"{BASE}/t/42",
        f"{BASE}/t/42.json",
        "https://FORUM.example.test/t/some-slug/42/",
    ],
)
def test_parse_topic_ref_accepts_ids_and_topic_urls(config: DiscourseConfig, ref: str) -> None:
    assert topics.parse_topic_ref(ref, config) == 42


@pytest.mark.parametrize(
    "ref",
    [
        "https://evil.example.test/t/slug/42",
        "http://forum.example.test/t/slug/42",
        f"{BASE}/c/governance/7",
        f"{BASE}/u/alice",
        "not a topic",
    ],
)
def test_parse_topic_ref_rejects_other_forums_and_paths(config: DiscourseConfig, ref: str) -> None:
    with pytest.raises(DiscourseError):
        topics.parse_topic_ref(ref, config)


def test_parse_topic_ref_honours_a_subfolder_install() -> None:
    sub = DiscourseConfig(base_url=f"{BASE}/forum", api_key=None, api_username=None)
    assert topics.parse_topic_ref(f"{BASE}/forum/t/slug/42", sub) == 42
    with pytest.raises(DiscourseError):
        topics.parse_topic_ref(f"{BASE}/t/slug/42", sub)


# --- topic fetch ------------------------------------------------------------


def test_fetch_topic_maps_onto_thread_data(monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig) -> None:
    posts = [_post(100, 1), _post(101, 2, "bob", reply_to=1), _post(102, 3, "alice", reply_to=2)]
    _serve(monkeypatch, {"/t/42.json": _topic(posts, [100, 101, 102])})

    thread = topics.fetch_topic(config, 42)

    assert thread["thread_id"] == "42"
    assert thread["list"] == BASE
    assert thread["subject"] == "Proposal: drop Python 3.10"
    assert thread["url"] == f"{BASE}/t/proposal-drop-python-3-10/42"
    assert thread["tags"] == ["governance"]
    assert thread["participant_handles"] == ["@alice", "@bob"]
    assert thread["truncated"] is False
    second = thread["messages"][1]
    assert second == {
        "message_id": "101",
        "post_number": 2,
        "from": "@bob",
        "date": "2026-10-02T10:00:00.000Z",
        "updated_at": "2026-10-02T11:00:00.000Z",
        "body": "<p>post 2</p>",
        "body_hidden": False,
        "body_format": "html",
        "in_reply_to": "100",
        "url": f"{BASE}/t/proposal-drop-python-3-10/42/2",
        "post_type": 1,
        "hidden": False,
        "deleted": False,
    }


def test_fetch_topic_reads_the_rest_of_the_stream_in_chunks(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig
) -> None:
    stream = list(range(1000, 1045))
    first = [_post(post_id, number) for number, post_id in enumerate(stream[:20], start=1)]

    def more(request: urllib.request.Request) -> dict[str, Any]:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        ids = [int(value) for value in query["post_ids[]"]]
        assert len(ids) <= topics.POSTS_CHUNK_SIZE
        return {"post_stream": {"posts": [_post(post_id, stream.index(post_id) + 1) for post_id in ids]}}

    forum = _serve(monkeypatch, {"/t/42.json": _topic(first, stream), "/t/42/posts.json": more})

    thread = topics.fetch_topic(config, 42)

    assert [message["message_id"] for message in thread["messages"]] == [str(post_id) for post_id in stream]
    assert thread["truncated"] is False
    assert len(forum.requests) == 3  # the topic, then 25 remaining posts in chunks of 20 and 5


def test_fetch_topic_marks_a_longer_topic_as_truncated(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig
) -> None:
    stream = list(range(1000, 1030))
    first = [_post(post_id, number) for number, post_id in enumerate(stream[:20], start=1)]
    forum = _serve(monkeypatch, {"/t/42.json": _topic(first, stream)})

    thread = topics.fetch_topic(config, 42, max_posts=5)

    assert len(thread["messages"]) == 5
    assert thread["truncated"] is True
    assert len(forum.requests) == 1


def test_fetch_topic_accepts_legacy_string_tags(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig
) -> None:
    _serve(monkeypatch, {"/t/42.json": _topic([_post(100, 1)], [100], tags=["governance", "pep"])})
    assert topics.fetch_topic(config, 42)["tags"] == ["governance", "pep"]


def test_fetch_topic_flags_hidden_and_deleted_posts(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig
) -> None:
    hidden = {**_post(100, 1), "hidden": True}
    deleted = {**_post(101, 2), "deleted_at": "2026-10-03T00:00:00.000Z"}
    _serve(monkeypatch, {"/t/42.json": _topic([hidden, deleted], [100, 101])})

    messages = topics.fetch_topic(config, 42)["messages"]

    assert (messages[0]["hidden"], messages[0]["deleted"]) == (True, False)
    assert (messages[1]["hidden"], messages[1]["deleted"]) == (False, True)


def test_fetch_topic_rejects_a_zero_post_limit(config: DiscourseConfig) -> None:
    with pytest.raises(DiscourseError):
        topics.fetch_topic(config, 42, max_posts=0)


# --- HTTP behaviour ---------------------------------------------------------


def _http_error(
    code: int, body: bytes = b"", headers: dict[str, str] | None = None
) -> urllib.error.HTTPError:
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return urllib.error.HTTPError(f"{BASE}/t/42.json", code, "error", message, io.BytesIO(body))


def test_get_json_sends_the_api_key_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    forum = _serve(monkeypatch, {"/t/42.json": {"id": 42}})
    keyed = DiscourseConfig(base_url=BASE, api_key="secret", api_username="magpie-bot")

    client.get_json(keyed, "/t/42.json")

    request = forum.requests[0]
    assert request.get_header("Api-key") == "secret"
    assert request.get_header("Api-username") == "magpie-bot"


def test_get_json_reports_discourse_errors(monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig) -> None:
    body = json.dumps({"errors": ["The requested URL or resource could not be found."]}).encode()
    _serve(monkeypatch, {"/t/42.json": _http_error(404, body)})
    with pytest.raises(DiscourseError, match=r"HTTP 404: The requested URL"):
        client.get_json(config, "/t/42.json")


def test_get_json_reports_rate_limiting(monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig) -> None:
    _serve(monkeypatch, {"/t/42.json": _http_error(429, headers={"Retry-After": "12"})})
    with pytest.raises(DiscourseError, match="retry after 12 seconds"):
        client.get_json(config, "/t/42.json")


def test_get_json_rejects_non_json(monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig) -> None:
    monkeypatch.setattr(
        client, "_urlopen", lambda request, timeout, *, base_url: FakeResponse(b"<html>login</html>")
    )
    with pytest.raises(DiscourseError, match="not JSON"):
        client.get_json(config, "/t/42.json")


def _redirect(handler: SameOriginRedirectHandler, url: str, target: str) -> urllib.request.Request | None:
    request = urllib.request.Request(url, headers={"Api-Key": "secret"})
    return handler.redirect_request(request, None, 301, "Moved", Message(), target)


def test_same_origin_redirect_keeps_the_headers() -> None:
    followed = _redirect(SameOriginRedirectHandler(BASE), f"{BASE}/t/42.json", "/t/slug/42.json")
    assert followed is not None
    assert followed.full_url == f"{BASE}/t/slug/42.json"
    assert followed.get_header("Api-key") == "secret"


@pytest.mark.parametrize(
    "target", ["https://evil.example.test/t/42.json", "http://forum.example.test/t/42.json"]
)
def test_cross_origin_redirect_is_refused(target: str) -> None:
    with pytest.raises(DiscourseError, match="refusing to forward credentials"):
        _redirect(SameOriginRedirectHandler(BASE), f"{BASE}/t/42.json", target)


# --- CLI --------------------------------------------------------------------


def test_cli_topic_view_prints_thread_data(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    _serve(monkeypatch, {"/t/42.json": _topic([_post(100, 1)], [100])})

    assert package_main(["topic", "view", f"{BASE}/t/proposal-drop-python-3-10/42"]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["thread_id"] == "42"
    assert printed["messages"][0]["from"] == "@alice"


def test_cli_reports_bridge_errors_on_stderr(forum_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert package_main(["topic", "view", "https://evil.example.test/t/x/1"]) == 1
    assert "magpie-discourse error:" in capsys.readouterr().err


def test_topic_url_accepts_the_effective_https_port(config: DiscourseConfig) -> None:
    assert topics.parse_topic_ref(f"{BASE}:443/t/proposal/42", config) == 42
    explicit = DiscourseConfig(base_url=f"{BASE}:443", api_key=None, api_username=None)
    assert topics.parse_topic_ref(f"{BASE}/t/proposal/42", explicit) == 42


@pytest.mark.parametrize("path", ["/t/42/7", "/t/42/7.json"])
def test_short_post_urls_use_the_topic_id(config: DiscourseConfig, path: str) -> None:
    assert topics.parse_topic_ref(f"{BASE}{path}", config) == 42


@pytest.mark.parametrize("url", [f"{BASE}:bad", f"{BASE}:65536", "https://[broken"])
def test_invalid_config_urls_fail_before_a_request(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", url)
    forum = _serve(monkeypatch, {})
    assert package_main(["topic", "view", "42"]) == 1
    assert forum.requests == []
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "ref",
    ["0", "-1", "²", f"{BASE}/t/proposal/0", f"{BASE}:bad/t/proposal/42", "https://[broken"],
)
def test_invalid_topic_references_fail_before_a_request(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, ref: str, capsys: pytest.CaptureFixture[str]
) -> None:
    forum = _serve(monkeypatch, {})
    assert package_main(["topic", "view", ref]) == 1
    assert forum.requests == []
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_invalid_post_limits_fail_before_a_request(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, limit: str, capsys: pytest.CaptureFixture[str]
) -> None:
    forum = _serve(monkeypatch, {})
    assert package_main(["topic", "view", "42", "--max-posts", limit]) == 1
    assert forum.requests == []
    assert capsys.readouterr().out == ""


def test_missing_username_fails_before_a_request(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", " ")
    forum = _serve(monkeypatch, {})
    assert package_main(["topic", "view", "42"]) == 1
    assert forum.requests == []
    assert capsys.readouterr().out == ""


def test_missing_posts_are_an_error_not_a_complete_thread(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    forum = _serve(
        monkeypatch,
        {
            "/t/42.json": _topic([_post(100, 1)], [100, 101]),
            "/t/42/posts.json": {"post_stream": {"posts": []}},
        },
    )
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "requested post" in output.err
    assert len(forum.requests) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"id": None},
        {"id": 43},
        {"title": None},
        {"post_stream": None},
        {"post_stream": ["invalid"]},
        {"post_stream": {"posts": [_post(100, 1)]}},
        {"post_stream": {"stream": "100", "posts": []}},
        {"post_stream": {"stream": [True], "posts": []}},
        {"post_stream": {"stream": [100], "posts": ["invalid"]}},
        {"post_stream": {"stream": [100], "posts": [{"id": 100}]}},
    ],
)
def test_malformed_topics_use_the_cli_error_channel(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    change: dict[str, Any],
) -> None:
    _serve(monkeypatch, {"/t/42.json": _topic([_post(100, 1)], [100], **change)})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "magpie-discourse error:" in output.err
    assert "Traceback" not in output.err


def test_an_explicitly_empty_topic_has_no_messages(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig
) -> None:
    forum = _serve(monkeypatch, {"/t/42.json": _topic([], [])})
    thread = topics.fetch_topic(config, 42)
    assert thread["messages"] == []
    assert thread["participant_handles"] == []
    assert thread["truncated"] is False
    assert len(forum.requests) == 1


def test_batch_order_does_not_change_topic_order(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig
) -> None:
    _serve(
        monkeypatch,
        {
            "/t/42.json": _topic([_post(100, 1)], [100, 101, 102]),
            "/t/42/posts.json": {"post_stream": {"posts": [_post(102, 3), _post(101, 2)]}},
        },
    )
    thread = topics.fetch_topic(config, 42)
    assert [post["message_id"] for post in thread["messages"]] == ["100", "101", "102"]


@pytest.mark.parametrize("code", [401, 403, 404, 429])
def test_http_errors_do_not_print_success_or_retry(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    code: int,
) -> None:
    forum = _serve(monkeypatch, {"/t/42.json": _http_error(code)})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert f"HTTP {code}" in output.err
    assert len(forum.requests) == 1


@pytest.mark.parametrize("target", [f"{BASE}:bad/t/42.json", "https://[broken"])
def test_invalid_redirect_urls_use_bridge_errors(target: str) -> None:
    with pytest.raises(DiscourseError):
        _redirect(SameOriginRedirectHandler(BASE), f"{BASE}/t/42.json", target)


def test_usage_errors_keep_argparse_exit_code(forum_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        package_main(["topic", "view"])
    assert exc.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("payload", [None, {"posts": []}, {"post_stream": []}])
def test_malformed_batches_do_not_become_complete_topics(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig, payload: Any
) -> None:
    _serve(
        monkeypatch,
        {"/t/42.json": _topic([_post(100, 1)], [100, 101]), "/t/42/posts.json": payload},
    )
    with pytest.raises(DiscourseError):
        topics.fetch_topic(config, 42)


@pytest.mark.parametrize(
    "problem",
    [
        urllib.error.URLError("offline"),
        TimeoutError(),
        ConnectionResetError("connection reset"),
        http.client.IncompleteRead(b"partial", 10),
    ],
)
def test_network_failures_use_the_cli_error_channel(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    problem: Exception,
) -> None:
    forum = _serve(monkeypatch, {"/t/42.json": problem})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "magpie-discourse error:" in output.err
    assert len(forum.requests) == 1


def test_retry_after_can_be_an_http_date(monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig) -> None:
    date = "Mon, 19 Oct 2026 10:00:00 GMT"
    _serve(monkeypatch, {"/t/42.json": _http_error(429, headers={"Retry-After": date})})
    with pytest.raises(DiscourseError, match=date):
        client.get_json(config, "/t/42.json")


def test_interrupted_http_error_body_keeps_the_http_status(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    error = _http_error(503)

    def interrupted() -> bytes:
        raise http.client.IncompleteRead(b"partial", 10)

    monkeypatch.setattr(error, "read", interrupted)
    forum = _serve(monkeypatch, {"/t/42.json": error})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "HTTP 503" in output.err
    assert len(forum.requests) == 1


@pytest.mark.parametrize("headers", [{}, {"Api-Key": "test-key", "Api-Username": "reader"}])
def test_equivalent_origins_preserve_read_headers(headers: dict[str, str]) -> None:
    request = urllib.request.Request(f"{BASE}/t/42.json", headers=headers)
    followed = SameOriginRedirectHandler(BASE).redirect_request(
        request, None, 302, "Moved", Message(), f"{BASE}:443/t/slug/42.json"
    )
    assert followed is not None
    assert followed.get_method() == "GET"
    assert dict(followed.header_items()) == dict(request.header_items())


# --- input and transport boundaries -----------------------------------------


@pytest.mark.parametrize("variable", ["DISCOURSE_API_KEY", "DISCOURSE_API_USERNAME"])
def test_cli_rejects_unencodable_headers_without_leaking_values_or_requesting(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    variable: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "reader")
    monkeypatch.setenv(variable, "private-\u5f20\u4e09")
    forum = _serve(monkeypatch, {"/t/42.json": _topic([_post(100, 1)], [100])})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert variable in output.err
    assert ("ASCII" if variable == "DISCOURSE_API_USERNAME" else "latin-1") in output.err
    assert "private-" not in output.err
    assert "Traceback" not in output.err
    assert forum.requests == []


def test_cli_preserves_a_latin1_key_with_an_ascii_username(
    monkeypatch: pytest.MonkeyPatch, forum_env: None
) -> None:
    monkeypatch.setenv("DISCOURSE_API_KEY", "cl\u00e9")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "reader")
    forum = _serve(monkeypatch, {"/t/42.json": _topic([], [])})
    assert package_main(["topic", "view", "42"]) == 0
    assert forum.requests[0].get_header("Api-key") == "cl\u00e9"
    assert forum.requests[0].get_header("Api-username") == "reader"


@pytest.mark.parametrize("encoding", ["cp1252", "cp936"])
def test_cli_json_round_trips_unicode_on_legacy_stdout(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, encoding: str
) -> None:
    title = "\u4e2d\u6587 \U0001f44d"
    post = {**_post(100, 1, "\u5f20\u4e09"), "cooked": f"<p>{title}</p>"}
    _serve(monkeypatch, {"/t/42.json": _topic([post], [100], title=title)})
    buffer = io.BytesIO()
    with (
        monkeypatch.context() as patched,
        io.TextIOWrapper(buffer, encoding=encoding, errors="strict") as stdout,
    ):
        patched.setattr(sys, "stdout", stdout)
        assert package_main(["topic", "view", "42"]) == 0
        stdout.flush()
        encoded = buffer.getvalue()
    assert encoded.isascii()
    result = json.loads(encoded.decode(encoding))
    assert result["subject"] == title
    assert result["messages"][0]["body"] == post["cooked"]
    assert result["messages"][0]["from"] == "@\u5f20\u4e09"


@pytest.mark.parametrize("suffix", ["?", "#", "?#", "?x=1", "#fragment"])
def test_cli_rejects_base_url_markers_before_requesting(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    suffix: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}/forum{suffix}")
    forum = _serve(monkeypatch, {"/forum/t/42.json": _topic([], [])})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "DISCOURSE_URL" in output.err
    assert forum.requests == []


def test_share_url_markers_and_escaped_base_path_are_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}/forum%3F%23")
    sub = load_config()
    assert topics.parse_topic_ref(f"{sub.base_url}/t/proposal/42?u=alice#post-2", sub) == 42


@pytest.mark.parametrize("limit", ["1", "500"])
def test_cli_reports_real_mega_topics_as_unsupported(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    limit: str,
) -> None:
    mega = _topic(
        [],
        [],
        posts_count=12000,
        post_stream={"posts": [_post(100, 1)], "isMegaTopic": True, "lastId": 12100},
    )
    forum = _serve(monkeypatch, {"/t/42.json": mega})
    assert package_main(["topic", "view", "42", "--max-posts", limit]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "mega topics without a post ID stream are not supported" in output.err
    assert len(forum.requests) == 1


def test_a_large_count_does_not_replace_stream_validation(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig
) -> None:
    _serve(monkeypatch, {"/t/42.json": _topic([_post(100, 1)], [100], posts_count=12000)})
    assert topics.fetch_topic(config, 42)["truncated"] is False


def test_moved_posts_keep_forum_stream_order_instead_of_date_order(
    monkeypatch: pytest.MonkeyPatch, config: DiscourseConfig
) -> None:
    recent = {**_post(100, 1), "created_at": "2026-10-05T10:00:00.000Z"}
    moved = {**_post(101, 3), "created_at": "2026-09-01T10:00:00.000Z"}
    _serve(monkeypatch, {"/t/42.json": _topic([moved, recent], [100, 101])})
    messages = topics.fetch_topic(config, 42)["messages"]
    assert [post["message_id"] for post in messages] == ["100", "101"]
    assert [post["date"] for post in messages] == [recent["created_at"], moved["created_at"]]


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_get_redirects_stay_in_the_configured_subpath(code: int) -> None:
    request = urllib.request.Request(f"{BASE}/forum/t/42.json", headers={"Api-Key": "secret"})
    followed = SameOriginRedirectHandler(f"{BASE}/forum").redirect_request(
        request, None, code, "Moved", Message(), f"{BASE}:443/forum/t/slug/42.json?u=reader"
    )
    assert followed is not None
    assert followed.get_method() == "GET"
    assert followed.get_header("Api-key") == "secret"
    assert followed.full_url == f"{BASE}:443/forum/t/slug/42.json?u=reader"


@pytest.mark.parametrize(
    "path",
    [
        "/other-app/collect",
        "/forum-other/collect",
        "/forum/%2e%2e/collect",
        "/forum/%252e%252e/collect",
        "/forum/a/%2e/collect",
        "/forum/a%2f..%2fcollect",
        "/forum/%5c..%5ccollect",
        "/forum/\\collect",
        "/forum/%0acollect",
        "/forum/%zz/collect",
    ],
)
def test_redirects_reject_paths_that_leave_or_obscure_the_forum_namespace(path: str) -> None:
    with pytest.raises(DiscourseError):
        _redirect(SameOriginRedirectHandler(f"{BASE}/forum"), f"{BASE}/forum/t/42.json", f"{BASE}{path}")


@pytest.mark.parametrize("method", ["POST", "HEAD"])
def test_non_get_redirects_are_refused(method: str) -> None:
    request = urllib.request.Request(f"{BASE}/forum/t/42.json", method=method, data=b"body")
    with pytest.raises(DiscourseError, match="Only GET"):
        SameOriginRedirectHandler(f"{BASE}/forum").redirect_request(
            request, None, 302, "Moved", Message(), "/forum/t/slug/42.json"
        )


@pytest.mark.parametrize(
    ("url", "method"),
    [
        (f"{BASE}/other-app/collect", "GET"),
        (f"{BASE}/forum-other/collect", "GET"),
        (f"{BASE}/forum/%2e%2e/collect", "GET"),
        ("https://evil.example.test/forum/t/42.json", "GET"),
        (f"{BASE}/forum/t/42.json", "POST"),
    ],
)
def test_transport_checks_the_initial_request_before_opening(
    monkeypatch: pytest.MonkeyPatch, url: str, method: str
) -> None:
    def unexpected_open(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("An out-of-scope request reached the opener")

    monkeypatch.setattr(urllib.request, "build_opener", unexpected_open)
    with pytest.raises(DiscourseError):
        client._urlopen(urllib.request.Request(url, method=method), 30, base_url=f"{BASE}/forum")


def test_cli_transport_binds_redirects_to_the_configured_forum(
    monkeypatch: pytest.MonkeyPatch, forum_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}/forum")
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "reader")
    requests: list[urllib.request.Request] = []

    class RedirectingOpener:
        def __init__(self, handler: SameOriginRedirectHandler) -> None:
            self.handler = handler

        def open(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
            requests.append(request)
            self.handler.redirect_request(request, None, 302, "Moved", Message(), "/other-app/collect")
            pytest.fail("The transport followed an out-of-scope redirect")

    def build_opener(handler: SameOriginRedirectHandler) -> RedirectingOpener:
        assert isinstance(handler, SameOriginRedirectHandler)
        return RedirectingOpener(handler)

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "refusing to forward credentials" in output.err
    assert len(requests) == 1


def _serve_redirect(monkeypatch: pytest.MonkeyPatch, location: str) -> list[urllib.request.Request]:
    """Exercise urllib's real redirect chain without opening any connection."""
    requests: list[urllib.request.Request] = []
    original_build_opener = urllib.request.build_opener

    class RedirectResponse(urllib.response.addinfourl):
        msg: str

    class FakeHTTPS(urllib.request.HTTPSHandler):
        def https_open(self, request: urllib.request.Request) -> Any:
            requests.append(request)
            headers = Message()
            if len(requests) == 1:
                code, body = 302, b""
                headers["Location"] = location
            else:
                assert len(requests) == 2, "Unexpected extra redirect request"
                code = 200
                body = json.dumps(_topic([_post(100, 1)], [100])).encode("utf-8")
            response = RedirectResponse(io.BytesIO(body), headers, request.full_url, code)
            response.msg = "Found" if code == 302 else "OK"
            return response

    class BlockHTTP(urllib.request.HTTPHandler):
        def http_open(self, request: urllib.request.Request) -> Any:
            pytest.fail("An HTTP redirect reached the transport")

    def build_opener(*handlers: Any) -> urllib.request.OpenerDirector:
        return original_build_opener(*handlers, FakeHTTPS(), BlockHTTP())

    def unexpected_connection(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("A redirect test attempted a real network connection")

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    monkeypatch.setattr(socket, "create_connection", unexpected_connection)
    return requests


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("/forum/t/slug/42.json", f"{BASE}/forum/t/slug/42.json"),
        ("slug/42.json", f"{BASE}/forum/t/slug/42.json"),
        ("/forum;", f"{BASE}/forum"),
        (f"{BASE}:443/forum/t/slug/42.json", f"{BASE}:443/forum/t/slug/42.json"),
        ("/forum/t/%E4%B8%AD%E6%96%87/42.json", f"{BASE}/forum/t/%E4%B8%AD%E6%96%87/42.json"),
        (
            "/forum/t/\u4e2d\u6587/42.json".encode().decode("latin-1"),
            f"{BASE}/forum/t/%E4%B8%AD%E6%96%87/42.json",
        ),
        ("/forum/t/slug/42.json?u=100%25", f"{BASE}/forum/t/slug/42.json?u=100%25"),
    ],
)
def test_cli_follows_real_urllib_redirects_with_read_headers(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    location: str,
    expected: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}/forum")
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "reader")
    requests = _serve_redirect(monkeypatch, location)
    assert package_main(["topic", "view", "42"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["thread_id"] == "42"
    assert output.err == ""
    assert [request.full_url for request in requests] == [f"{BASE}/forum/t/42.json", expected]
    for request in requests:
        assert request.get_method() == "GET"
        assert request.get_header("Api-key") == "test-key"
        assert request.get_header("Api-username") == "reader"
        assert request.get_header("Accept") == "application/json"


@pytest.mark.parametrize(
    "location",
    [
        "/other-app/collect",
        "/forum-other/collect",
        "/forum/../other-app/collect",
        "//evil.example.test/forum/t/42.json",
        "http://forum.example.test/forum/t/42.json",
        "/forum%2Fcollect",
        "/forum%2fother-app/collect",
        "/forum%252Fcollect",
        "/%66orum/collect",
        "/for%75m/collect",
        "/forum;v=1",
        "/forum/t/with%2Fslash/42.json",
        "/forum/t/100%25-done/42.json",
        "/forum/t/%2541/42.json",
    ],
)
def test_cli_rejects_unsafe_real_urllib_redirects_before_the_second_request(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    location: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}/forum")
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "reader")
    requests = _serve_redirect(monkeypatch, location)
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "magpie-discourse error:" in output.err
    assert "test-key" not in output.err
    assert "Traceback" not in output.err
    assert len(requests) == 1


@pytest.mark.parametrize(
    "path",
    [
        "/forum/..",
        "/forum/./",
        "/forum%zz",
        "/forum\\x",
        "/forum;v=1",
        "/forum;",
        "/forum;v=1/",
        "/forum/%25",
        "/forum/%2541",
        "/forum%2Fother",
        "/forum/%FF",
        "/forum/%0a",
    ],
)
def test_cli_rejects_invalid_base_paths_before_requesting(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    url = f"{BASE}{path}"
    monkeypatch.setenv("DISCOURSE_URL", url)
    route = urllib.parse.urlparse(f"{url.rstrip('/')}/t/42.json").path
    forum = _serve(monkeypatch, {route: _topic([], [])})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "DISCOURSE_URL has an invalid or ambiguous path" in output.err
    assert "Traceback" not in output.err
    assert forum.requests == []


@pytest.mark.parametrize("username", ["Andr\u00e9", "\u5f20\u4e09", "reader\U0001f44d"])
def test_cli_rejects_non_ascii_usernames_before_requesting(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    username: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", username)
    forum = _serve(monkeypatch, {"/t/42.json": _topic([], [])})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "DISCOURSE_API_USERNAME" in output.err
    assert "ASCII" in output.err
    assert username not in output.err
    assert "test-key" not in output.err
    assert "Traceback" not in output.err
    assert forum.requests == []


@pytest.mark.parametrize("path", ["/%66orum/collect", "/forum;v=1", "/forum%2Fcollect", "/forum/t/%2541"])
def test_transport_rejects_raw_path_aliases_before_opening(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    def unexpected_open(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("An ambiguous initial request reached the opener")

    monkeypatch.setattr(urllib.request, "build_opener", unexpected_open)
    request = urllib.request.Request(f"{BASE}{path}")
    with pytest.raises(DiscourseError):
        client._urlopen(request, 30, base_url=f"{BASE}/forum")


def _serve_post_variant(
    monkeypatch: pytest.MonkeyPatch, stage: str, post: dict[str, Any]
) -> tuple[FakeForum, int]:
    """Place a post in either response, optionally outside the output limit."""
    routes: dict[str, Any]
    if stage == "initial":
        routes = {"/t/42.json": _topic([post], [101])}
        limit = 500
    elif stage == "batch":
        routes = {
            "/t/42.json": _topic([_post(100, 1)], [100, 101]),
            "/t/42/posts.json": {"post_stream": {"posts": [post]}},
        }
        limit = 500
    elif stage == "initial_outside_limit":
        routes = {"/t/42.json": _topic([_post(100, 1), post], [100, 101])}
        limit = 1
    else:
        assert stage == "batch_extra"
        extra = {**post, "id": 102, "post_number": 3}
        routes = {
            "/t/42.json": _topic([_post(100, 1)], [100, 101, 102]),
            "/t/42/posts.json": {"post_stream": {"posts": [_post(101, 2), extra]}},
        }
        limit = 2
    return _serve(monkeypatch, routes), limit


@pytest.mark.parametrize("stage", ["initial", "batch", "initial_outside_limit", "batch_extra"])
@pytest.mark.parametrize("state", ["missing", "null"])
def test_cli_requires_bodies_on_all_response_posts(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    state: str,
) -> None:
    post = _post(101, 2)
    if state == "missing":
        post.pop("cooked")
    else:
        post["cooked"] = None
    forum, limit = _serve_post_variant(monkeypatch, stage, post)
    assert package_main(["topic", "view", "42", "--max-posts", str(limit)]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "cooked" in output.err
    assert "Traceback" not in output.err
    assert len(forum.requests) == (2 if stage in ("batch", "batch_extra") else 1)


@pytest.mark.parametrize("stage", ["initial", "batch"])
@pytest.mark.parametrize("body", [False, 123, [], {}])
def test_cli_rejects_non_string_post_bodies(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    body: Any,
) -> None:
    forum, limit = _serve_post_variant(monkeypatch, stage, {**_post(101, 2), "cooked": body})
    assert package_main(["topic", "view", "42", "--max-posts", str(limit)]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "cooked" in output.err
    assert "Traceback" not in output.err
    assert len(forum.requests) == (2 if stage == "batch" else 1)


@pytest.mark.parametrize("stage", ["initial", "batch"])
@pytest.mark.parametrize(
    ("body", "hidden", "marker", "expected"),
    [
        ("", False, "absent", False),
        (" \n", False, False, False),
        ("<p></p>", False, False, False),
        ("<p>\u4e2d\u6587 \U0001f44d</p>", False, False, False),
        ("<p>Hidden placeholder</p>", True, True, True),
        ("<p>Staff-visible content</p>", True, "absent", False),
        ("<p>Staff-visible content</p>", True, False, False),
        ("", True, True, True),
    ],
)
def test_cli_preserves_provided_bodies_and_reports_the_server_marker(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    body: str,
    hidden: bool,
    marker: bool | str,
    expected: bool,
) -> None:
    post = {**_post(101, 2), "cooked": body, "hidden": hidden}
    if marker != "absent":
        post["cooked_hidden"] = marker
    _, limit = _serve_post_variant(monkeypatch, stage, post)
    assert package_main(["topic", "view", "42", "--max-posts", str(limit)]) == 0
    output = capsys.readouterr()
    message = json.loads(output.out)["messages"][-1]
    assert output.err == ""
    assert message["body"] == body
    assert message["body_format"] == "html"
    assert message["body_hidden"] is expected
    assert message["hidden"] is hidden


@pytest.mark.parametrize("stage", ["initial", "batch", "initial_outside_limit", "batch_extra"])
@pytest.mark.parametrize("marker", [None, 0, "true"])
def test_cli_requires_boolean_body_markers_on_all_response_posts(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    marker: Any,
) -> None:
    post = {**_post(101, 2), "cooked": "<p>private-body-marker</p>", "cooked_hidden": marker}
    _, limit = _serve_post_variant(monkeypatch, stage, post)
    assert package_main(["topic", "view", "42", "--max-posts", str(limit)]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "cooked_hidden" in output.err
    assert "private-body-marker" not in output.err
    assert "Traceback" not in output.err


@pytest.mark.parametrize(("drop", "expected_requests"), [(None, 25), (21, 2), (490, 25)])
def test_multi_batch_reads_stop_at_the_first_incomplete_batch(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    drop: int | None,
    expected_requests: int,
) -> None:
    stream = list(range(1, 501))

    def more(request: urllib.request.Request) -> dict[str, Any]:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
        ids = [int(value) for value in query["post_ids[]"]]
        assert len(ids) <= 20
        return {"post_stream": {"posts": [_post(post_id, post_id) for post_id in ids if post_id != drop]}}

    forum = _serve(
        monkeypatch,
        {
            "/t/42.json": _topic([_post(i, i) for i in stream[:20]], stream),
            "/t/42/posts.json": more,
        },
    )
    assert package_main(["topic", "view", "42"]) == (0 if drop is None else 1)
    output = capsys.readouterr()
    if drop is None:
        thread = json.loads(output.out)
        assert len(thread["messages"]) == 500
        assert thread["truncated"] is False
        assert output.err == ""
    else:
        assert output.out == ""
        assert "did not return 1 requested post(s)" in output.err
    assert len(forum.requests) == expected_requests


@pytest.mark.parametrize(("stream", "limit"), [([100, 100, 101], "2"), ([100, 101, 100], "1")])
def test_duplicate_stream_ids_fail_even_beyond_the_output_limit(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    stream: list[int],
    limit: str,
) -> None:
    forum = _serve(monkeypatch, {"/t/42.json": _topic([_post(100, 1), _post(101, 2)], stream)})
    assert package_main(["topic", "view", "42", "--max-posts", limit]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "duplicate post ids" in output.err
    assert len(forum.requests) == 1


@pytest.mark.parametrize("path", ["/\u8bba\u575b", "/my forum"])
def test_raw_base_paths_fail_before_requesting(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}{path}")
    forum = _serve(monkeypatch, {f"{path}/t/42.json": _topic([], [])})
    assert package_main(["topic", "view", "42"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "DISCOURSE_URL" in output.err
    assert "percent-encoded" in output.err
    assert "Traceback" not in output.err
    assert forum.requests == []


@pytest.mark.parametrize("path", ["/%E8%AE%BA%E5%9D%9B", "/my%20forum", "/a;b/forum"])
def test_encoded_base_paths_keep_their_original_spelling(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    url = f"{BASE}{path}"
    monkeypatch.setenv("DISCOURSE_URL", url)
    forum = _serve(monkeypatch, {f"{path}/t/42.json": _topic([_post(100, 1)], [100])})
    assert package_main(["topic", "view", "42"]) == 0
    thread = json.loads(capsys.readouterr().out)
    assert thread["list"] == url
    assert forum.requests[0].full_url == f"{url}/t/42.json"
    assert forum.requests[0].full_url.isascii()


@pytest.mark.parametrize("base_path", ["", "/forum"])
@pytest.mark.parametrize(
    ("path", "topic_id"),
    [
        ("/t/2026/42", 2026),
        ("/t/42/7", 42),
        ("/t/2026/42/", 2026),
        ("/t/2026/42.json", 2026),
        ("/t/002026/0042.json/?u=reader#post-7", 2026),
        ("/t/2026/42?u=reader#post-42", 2026),
        ("/t/42/7?u=alice", 42),
        ("/t/%32%30%32%36/42", 42),
        ("/t/20%32%36/42", 42),
    ],
)
def test_cli_topic_urls_follow_discourse_route_precedence(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    base_path: str,
    path: str,
    topic_id: int,
) -> None:
    # Discourse's numeric topic/post route precedes the slug route; Slug.for
    # rejects generated numeric-only slugs. Match raw paths before decoding.
    # https://github.com/discourse/discourse/blob/c9d334e8b2ef730fa70fcbb880a16d79f4b5e7d2/config/routes.rb#L1671-L1691
    # https://github.com/discourse/discourse/blob/c9d334e8b2ef730fa70fcbb880a16d79f4b5e7d2/lib/slug.rb#L23-L34
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}{base_path}")
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "reader")
    slugs = {2026: "annual-update", 42: "discussion"}
    forum = _serve(
        monkeypatch,
        {
            f"{base_path}/t/{value}.json": _topic([_post(100, 1)], [100], id=value, slug=slug)
            for value, slug in slugs.items()
        },
    )
    assert package_main(["topic", "view", f"{BASE}{base_path}{path}"]) == 0
    output = capsys.readouterr()
    thread = json.loads(output.out)
    assert output.err == ""
    assert thread["thread_id"] == str(topic_id)
    assert thread["url"] == f"{BASE}{base_path}/t/{slugs[topic_id]}/{topic_id}"
    assert thread["messages"][0]["body"] == "<p>post 1</p>"
    assert [request.full_url for request in forum.requests] == [f"{BASE}{base_path}/t/{topic_id}.json"]
    assert forum.requests[0].get_header("Api-key") == "test-key"
    assert forum.requests[0].get_header("Api-username") == "reader"


@pytest.mark.parametrize("base_path", ["", "/forum"])
@pytest.mark.parametrize(
    "ref",
    [
        "42",
        "/t/42",
        "/t/42.json",
        "/t/discussion/42",
        "/t/discussion/42/7",
        "/t/2026/42/7",
        "/t/%32%30%32%36/42/7.json?u=reader#post-7",
        "/t/%E4%B8%AD%E6%96%87/42",
        "/t/\u8ba8\u8bba/42",
        "/t/\uff12\uff10\uff12\uff16/42",
    ],
)
def test_cli_supported_topic_references_keep_the_intended_topic(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    base_path: str,
    ref: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}{base_path}")
    forum = _serve(
        monkeypatch,
        {f"{base_path}/t/42.json": _topic([_post(100, 1)], [100], slug="discussion")},
    )
    value = ref if ref == "42" else f"{BASE}{base_path}{ref}"
    assert package_main(["topic", "view", value]) == 0
    output = capsys.readouterr()
    thread = json.loads(output.out)
    assert output.err == ""
    assert thread["thread_id"] == "42"
    assert thread["messages"][0]["body"] == "<p>post 1</p>"
    assert thread["url"] == f"{BASE}{base_path}/t/discussion/42"
    assert [request.full_url for request in forum.requests] == [f"{BASE}{base_path}/t/42.json"]


@pytest.mark.parametrize("base_path", ["", "/forum"])
def test_cli_canonical_topic_url_can_be_read_again(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    base_path: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}{base_path}")
    forum = _serve(
        monkeypatch,
        {f"{base_path}/t/42.json": _topic([_post(100, 1)], [100], slug="discussion")},
    )
    assert package_main(["topic", "view", f"{BASE}{base_path}/t/42/7?u=alice"]) == 0
    first = capsys.readouterr()
    thread = json.loads(first.out)
    assert first.err == ""
    assert package_main(["topic", "view", thread["url"]]) == 0
    second = capsys.readouterr()
    assert second.err == ""
    assert json.loads(second.out) == thread
    assert [request.full_url for request in forum.requests] == [f"{BASE}{base_path}/t/42.json"] * 2


@pytest.mark.parametrize("base_path", ["", "/forum"])
@pytest.mark.parametrize(
    "ref",
    [
        "\uff14\uff12",
        "\u0664\u0662",
        "4\uff12",
        "\u00b2",
        " \uff14\uff12 ",
        "/t/\uff14\uff12",
        "/t/slug/\uff14\uff12",
        "/t/slug/42/\uff17",
        "/t/42/\uff17",
        "/t/slug/\u0664\u0662",
        "/t/slug/42/\u0667",
        "/t/slug/4\uff12",
        "/t/slug/42/7\uff17",
    ],
)
def test_cli_non_ascii_topic_ids_and_post_numbers_fail_before_requesting(
    monkeypatch: pytest.MonkeyPatch,
    forum_env: None,
    capsys: pytest.CaptureFixture[str],
    base_path: str,
    ref: str,
) -> None:
    monkeypatch.setenv("DISCOURSE_URL", f"{BASE}{base_path}")
    monkeypatch.setenv("DISCOURSE_API_KEY", "test-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "reader")
    forum = _serve(monkeypatch, {})
    value = f"{BASE}{base_path}{ref}" if ref.startswith("/") else ref
    assert package_main(["topic", "view", value]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "magpie-discourse error:" in output.err
    if not ref.startswith("/"):
        assert output.err == "magpie-discourse error: Topic id must use ASCII digits\n"
    assert "Traceback" not in output.err
    assert "test-key" not in output.err
    assert forum.requests == []
