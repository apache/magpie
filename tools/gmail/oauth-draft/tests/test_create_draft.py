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

import base64
import email
import email.policy
import io
import json
import urllib.error
from email.message import EmailMessage
from unittest.mock import patch

import pytest

from oauth_draft.create_draft import (
    api_get,
    api_post,
    build_mime,
    choose_reply_headers,
    create_draft,
    explicit_reply_headers,
    headers_from_thread,
    latest_reply_headers,
    main,
    normalize_message_id,
    parse_args,
    read_body,
)


def parse_built_message(raw: bytes) -> EmailMessage:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert isinstance(msg, EmailMessage)
    return msg


def test_build_mime_sets_basic_headers():
    raw = build_mime(
        from_addr="me@example.com",
        to=["a@example.com"],
        cc=[],
        bcc=[],
        subject="Hello",
        body="Body content.",
        in_reply_to=None,
        references=None,
    )
    msg = parse_built_message(raw)
    assert msg["From"] == "me@example.com"
    assert msg["To"] == "a@example.com"
    assert msg["Subject"] == "Hello"
    assert msg["Cc"] is None
    assert msg["Bcc"] is None
    assert msg["In-Reply-To"] is None
    assert msg["References"] is None
    assert msg.get_content().rstrip() == "Body content."


def test_build_mime_is_plain_text_not_html():
    """The built message must be single-part ``text/plain`` — never HTML.

    The project sends plain-text mail only. ``build_mime`` uses
    ``EmailMessage.set_content(str)``, which yields a single
    ``text/plain`` part with no ``text/html`` alternative. This guards
    against a regression that would introduce an HTML body (e.g. a
    stray ``add_alternative`` / ``set_content(subtype="html")``).
    """
    raw = build_mime(
        from_addr="me@example.com",
        to=["a@example.com"],
        cc=[],
        bcc=[],
        subject="Plain",
        body="Just text, no markup.",
        in_reply_to=None,
        references=None,
    )
    msg = parse_built_message(raw)
    assert msg.get_content_type() == "text/plain"
    assert not msg.is_multipart()
    # No HTML part anywhere in the tree.
    assert all(part.get_content_type() != "text/html" for part in msg.walk())
    # The raw RFC822 bytes carry no HTML content-type header either.
    assert b"text/html" not in raw


def test_build_mime_joins_multiple_recipients():
    raw = build_mime(
        from_addr="me@example.com",
        to=["a@example.com", "b@example.com"],
        cc=["cc1@example.com", "cc2@example.com"],
        bcc=["bcc@example.com"],
        subject="Multi",
        body="x",
        in_reply_to=None,
        references=None,
    )
    msg = parse_built_message(raw)
    assert msg["To"] == "a@example.com, b@example.com"
    assert msg["Cc"] == "cc1@example.com, cc2@example.com"
    assert msg["Bcc"] == "bcc@example.com"


def test_build_mime_sets_reply_headers_when_provided():
    raw = build_mime(
        from_addr="me@example.com",
        to=["a@example.com"],
        cc=[],
        bcc=[],
        subject="Re: Thing",
        body="reply",
        in_reply_to="<msg-1@example.com>",
        references="<root@example.com> <msg-1@example.com>",
    )
    msg = parse_built_message(raw)
    assert msg["In-Reply-To"] == "<msg-1@example.com>"
    assert msg["References"] == "<root@example.com> <msg-1@example.com>"


def test_headers_from_thread_empty_returns_none_pair():
    assert headers_from_thread({}) == (None, None)
    assert headers_from_thread({"messages": []}) == (None, None)


def test_headers_from_thread_no_message_id_returns_none_pair():
    thread = {"messages": [{"payload": {"headers": [{"name": "Subject", "value": "x"}]}}]}
    assert headers_from_thread(thread) == (None, None)


def test_headers_from_thread_seeds_references_when_absent():
    thread = {
        "messages": [
            {
                "payload": {
                    "headers": [
                        {"name": "Message-ID", "value": "<a@example.com>"},
                    ]
                }
            }
        ]
    }
    assert headers_from_thread(thread) == ("<a@example.com>", "<a@example.com>")


def test_headers_from_thread_appends_to_existing_references():
    thread = {
        "messages": [
            {
                "payload": {
                    "headers": [
                        {"name": "Message-ID", "value": "<root@example.com>"},
                    ]
                }
            },
            {
                "payload": {
                    "headers": [
                        {"name": "Message-ID", "value": "<reply@example.com>"},
                        {"name": "References", "value": "<root@example.com>"},
                    ]
                }
            },
        ]
    }
    in_reply_to, references = headers_from_thread(thread)
    assert in_reply_to == "<reply@example.com>"
    assert references == "<root@example.com> <reply@example.com>"


def test_headers_from_thread_is_case_insensitive_on_header_name():
    thread = {
        "messages": [
            {
                "payload": {
                    "headers": [
                        {"name": "message-id", "value": "<lower@example.com>"},
                    ]
                }
            }
        ]
    }
    assert headers_from_thread(thread)[0] == "<lower@example.com>"


def test_parse_args_defaults():
    args = parse_args(["--to", "x@example.com", "--subject", "S"])
    assert args.to == ["x@example.com"]
    assert args.cc == []
    assert args.bcc == []
    assert args.body_file == "-"
    assert args.thread_id is None
    assert args.no_reply_headers is False


def test_parse_args_repeats():
    args = parse_args(
        [
            "--to",
            "a@example.com",
            "--to",
            "b@example.com",
            "--cc",
            "c@example.com",
            "--subject",
            "S",
        ]
    )
    assert args.to == ["a@example.com", "b@example.com"]
    assert args.cc == ["c@example.com"]


# --- explicit In-Reply-To / References --------------------------------------


@pytest.mark.parametrize("value", ["<report@example.org>", "report@example.org"])
def test_normalize_message_id_adds_angle_brackets(value):
    assert normalize_message_id(value) == "<report@example.org>"


@pytest.mark.parametrize(
    "value",
    [
        "<a@x>\r\nBcc: attacker@example.com",
        "a@x\nX-Injected: 1",
        "<a@x>\r",
        "<a b@x>",
        " <a@x>",
        "<a@x",
        "a@x>",
        "<<a@x>>",
        "<no-at-sign>",
        "<a@b@c>",
        "<@x>",
        "<a@>",
        "<a\x00@x>",
        "<ä@x>",
        "",
    ],
)
def test_normalize_message_id_rejects_malformed_or_injected(value):
    with pytest.raises(ValueError, match="not a Message-ID"):
        normalize_message_id(value)


def test_explicit_reply_headers_none_when_not_given():
    assert explicit_reply_headers(None, None) == (None, None)


def test_explicit_reply_headers_references_default_to_in_reply_to():
    assert explicit_reply_headers("report@example.org", None) == (
        "<report@example.org>",
        "<report@example.org>",
    )


def test_explicit_reply_headers_normalizes_references_and_appends_parent():
    assert explicit_reply_headers("<b@x>", "root@x  <a@x>") == ("<b@x>", "<root@x> <a@x> <b@x>")


def test_explicit_reply_headers_keeps_references_naming_the_parent():
    assert explicit_reply_headers("<b@x>", "<a@x> <b@x>") == ("<b@x>", "<a@x> <b@x>")


def test_explicit_reply_headers_rejects_injection_in_references():
    with pytest.raises(ValueError, match="not a Message-ID"):
        explicit_reply_headers("<b@x>", "<a@x>\r\nBcc: attacker@example.com")


def test_explicit_reply_headers_references_need_in_reply_to():
    with pytest.raises(ValueError, match="references needs in_reply_to"):
        explicit_reply_headers(None, "<a@x>")


def test_choose_reply_headers_explicit_wins_and_skips_thread_lookup():
    with patch("oauth_draft.create_draft.latest_reply_headers") as latest:
        result = choose_reply_headers("tok", "tid", ("<p@x>", "<p@x>"), no_reply_headers=False)
    assert result == ("<p@x>", "<p@x>")
    latest.assert_not_called()


def test_parse_args_normalizes_in_reply_to():
    args = parse_args(["--to", "x@example.com", "--subject", "S", "--in-reply-to", "report@example.org"])
    assert args.in_reply_to == "<report@example.org>"
    assert args.references == "<report@example.org>"


@pytest.mark.parametrize(
    "extra",
    [
        ["--in-reply-to", "<a@x>\r\nBcc: attacker@example.com"],
        ["--references", "<a@x>"],
        ["--in-reply-to", "<a@x>", "--no-reply-headers"],
    ],
)
def test_parse_args_rejects_bad_reply_header_input(extra):
    with pytest.raises(SystemExit) as excinfo:
        parse_args(["--to", "x@example.com", "--subject", "S", *extra])
    assert excinfo.value.code == 2


# --- read_body -------------------------------------------------------------


def test_read_body_from_file(tmp_path):
    p = tmp_path / "body.txt"
    p.write_text("hello from file")
    assert read_body(str(p)) == "hello from file"


def test_read_body_from_stdin_when_dash(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("piped"))
    assert read_body("-") == "piped"


def test_read_body_from_stdin_when_none(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("default"))
    assert read_body(None) == "default"


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


def test_api_get_parses_json_response():
    with patch("oauth_draft.create_draft.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(b'{"id": "thread-1"}')
        result = api_get("token", "/threads/thread-1")
    assert result == {"id": "thread-1"}
    request = mock_open.call_args.args[0]
    assert request.full_url.endswith("/threads/thread-1")
    assert request.headers["Authorization"] == "Bearer token"


def test_api_post_parses_json_response():
    with patch("oauth_draft.create_draft.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(b'{"id": "draft-7"}')
        result = api_post("token", "/drafts", {"message": {"raw": "X"}})
    assert result == {"id": "draft-7"}
    request = mock_open.call_args.args[0]
    assert request.method == "POST"
    assert request.headers["Content-type"] == "application/json"
    assert json.loads(request.data) == {"message": {"raw": "X"}}


def test_api_get_raises_on_http_error():
    """``api_get`` must surface HTTP errors as a clean ``SystemExit``.

    Regression: ``api_get`` was the only ``urlopen`` call in the
    package without a ``try/except HTTPError``, so a 401/403/404 from
    ``threads.get`` (the path exercised on every ``oauth-draft-create
    --thread-id <X>`` invocation) produced a raw Python traceback
    instead of a one-line error matching the rest of the tool.
    """
    err = urllib.error.HTTPError(
        url="https://x",
        code=404,
        msg="Not Found",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error": "thread missing"}'),
    )
    with patch("oauth_draft.create_draft.urllib.request.urlopen", side_effect=err):
        with pytest.raises(SystemExit) as excinfo:
            api_get("token", "/threads/missing-thread")
    assert "failed (404)" in str(excinfo.value)
    assert "thread missing" in str(excinfo.value)


def test_api_post_raises_on_http_error():
    err = urllib.error.HTTPError(
        url="https://x",
        code=403,
        msg="Forbidden",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error": "forbidden"}'),
    )
    with patch("oauth_draft.create_draft.urllib.request.urlopen", side_effect=err):
        with pytest.raises(SystemExit) as excinfo:
            api_post("token", "/drafts", {})
    assert "failed (403)" in str(excinfo.value)
    assert "forbidden" in str(excinfo.value)


def test_latest_reply_headers_pulls_from_api_get():
    fake_thread = {
        "messages": [
            {
                "payload": {
                    "headers": [
                        {"name": "Message-ID", "value": "<m@example.com>"},
                    ]
                }
            }
        ]
    }
    with patch("oauth_draft.create_draft.api_get", return_value=fake_thread) as m:
        in_reply, refs = latest_reply_headers("token", "thread-id-9")
    assert in_reply == "<m@example.com>"
    assert refs == "<m@example.com>"
    m.assert_called_once_with("token", "/threads/thread-id-9?format=full")


def test_create_draft_payload_includes_threadid_when_set():
    raw = b"raw-bytes"
    with patch("oauth_draft.create_draft.api_post", return_value={"id": "d-1"}) as m:
        result = create_draft("token", "thread-1", raw)
    assert result == {"id": "d-1"}
    _, _, payload = m.call_args.args
    expected_b64 = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    assert payload == {"message": {"raw": expected_b64, "threadId": "thread-1"}}


def test_create_draft_payload_omits_threadid_when_none():
    with patch("oauth_draft.create_draft.api_post", return_value={"id": "d-2"}) as m:
        create_draft("token", None, b"x")
    _, _, payload = m.call_args.args
    assert "threadId" not in payload["message"]


# --- main ------------------------------------------------------------------


def _make_creds_file(tmp_path):
    p = tmp_path / "creds.json"
    p.write_text(
        json.dumps(
            {
                "client_id": "cid",
                "client_secret": "secret",
                "refresh_token": "refresh",
                "from_address": "me@example.com",
            }
        )
    )
    return p


def test_main_create_draft_end_to_end(tmp_path, capsys):
    creds = _make_creds_file(tmp_path)
    body_file = tmp_path / "body.txt"
    body_file.write_text("Reply body")
    api_post_mock = patch(
        "oauth_draft.create_draft.api_post",
        return_value={
            "id": "draft-id-99",
            "message": {"id": "msg-id-99", "threadId": "tid"},
        },
    )
    with (
        patch("oauth_draft.create_draft.refresh_access_token", return_value="tok"),
        patch(
            "oauth_draft.create_draft.latest_reply_headers",
            return_value=("<a@x>", "<a@x>"),
        ),
        api_post_mock as post,
    ):
        rc = main(
            [
                "--credentials",
                str(creds),
                "--thread-id",
                "tid",
                "--to",
                "rcpt@example.com",
                "--subject",
                "Re: hello",
                "--body-file",
                str(body_file),
            ]
        )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Draft ID:    draft-id-99" in out
    assert "Message ID:  msg-id-99" in out
    # Verify the MIME body posted to /drafts has reply headers + body.
    _, path, payload = post.call_args.args
    assert path == "/drafts"
    raw_b64 = payload["message"]["raw"]
    raw_bytes = base64.urlsafe_b64decode(raw_b64 + "=" * (-len(raw_b64) % 4))
    decoded = raw_bytes.decode()
    assert "From: me@example.com" in decoded
    assert "To: rcpt@example.com" in decoded
    assert "Subject: Re: hello" in decoded
    assert "In-Reply-To: <a@x>" in decoded
    assert "Reply body" in decoded


def test_main_no_reply_headers_skips_thread_lookup(tmp_path):
    creds = _make_creds_file(tmp_path)
    body = tmp_path / "b.txt"
    body.write_text("x")
    with (
        patch("oauth_draft.create_draft.refresh_access_token", return_value="t"),
        patch("oauth_draft.create_draft.latest_reply_headers") as latest,
        patch(
            "oauth_draft.create_draft.api_post",
            return_value={"id": "d", "message": {"id": "m"}},
        ),
    ):
        rc = main(
            [
                "--credentials",
                str(creds),
                "--thread-id",
                "tid",
                "--no-reply-headers",
                "--to",
                "x@example.com",
                "--subject",
                "S",
                "--body-file",
                str(body),
            ]
        )
    assert rc == 0
    latest.assert_not_called()


def _posted_message(post) -> EmailMessage:
    raw_b64 = post.call_args.args[2]["message"]["raw"]
    return parse_built_message(base64.urlsafe_b64decode(raw_b64 + "=" * (-len(raw_b64) % 4)))


def test_main_in_reply_to_without_thread_id_sets_headers(tmp_path):
    creds = _make_creds_file(tmp_path)
    body = tmp_path / "b.txt"
    body.write_text("x")
    with (
        patch("oauth_draft.create_draft.refresh_access_token", return_value="t"),
        patch("oauth_draft.create_draft.latest_reply_headers") as latest,
        patch(
            "oauth_draft.create_draft.api_post",
            return_value={"id": "d", "message": {"id": "m"}},
        ) as post,
    ):
        rc = main(
            [
                "--credentials",
                str(creds),
                "--in-reply-to",
                "report@example.org",
                "--references",
                "<root@example.org>",
                "--to",
                "x@example.com",
                "--subject",
                "Re: S",
                "--body-file",
                str(body),
            ]
        )
    assert rc == 0
    latest.assert_not_called()
    assert "threadId" not in post.call_args.args[2]["message"]
    msg = _posted_message(post)
    assert msg["In-Reply-To"] == "<report@example.org>"
    assert msg["References"] == "<root@example.org> <report@example.org>"


def test_main_explicit_headers_win_over_thread_id(tmp_path):
    creds = _make_creds_file(tmp_path)
    body = tmp_path / "b.txt"
    body.write_text("x")
    with (
        patch("oauth_draft.create_draft.refresh_access_token", return_value="t"),
        patch(
            "oauth_draft.create_draft.latest_reply_headers",
            return_value=("<thread-last@x>", "<thread-last@x>"),
        ) as latest,
        patch(
            "oauth_draft.create_draft.api_post",
            return_value={"id": "d", "message": {"id": "m", "threadId": "tid"}},
        ) as post,
    ):
        rc = main(
            [
                "--credentials",
                str(creds),
                "--thread-id",
                "tid",
                "--in-reply-to",
                "<report@example.org>",
                "--to",
                "x@example.com",
                "--subject",
                "Re: S",
                "--body-file",
                str(body),
            ]
        )
    assert rc == 0
    latest.assert_not_called()
    assert post.call_args.args[2]["message"]["threadId"] == "tid"
    msg = _posted_message(post)
    assert msg["In-Reply-To"] == "<report@example.org>"
    assert msg["References"] == "<report@example.org>"
