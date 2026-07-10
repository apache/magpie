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

import asyncio
import email
import email.policy
import pathlib
from email.message import EmailMessage
from unittest.mock import patch

import pytest

from oauth_draft import mcp_server
from oauth_draft.credentials import Credentials

CREDS = Credentials(
    client_id="cid",
    client_secret="secret",
    refresh_token="refresh",
    from_address="me@example.com",
)


def _run_impl(
    *,
    thread_id: str | None = None,
    no_reply_headers: bool = False,
    body: str = "Reply body with a link: https://lists.apache.org/thread/abc123\n",
):
    """Call the tool implementation with all network boundaries mocked.

    Returns ``(result_dict, raw_bytes_posted)`` where ``raw_bytes`` is the
    RFC822 message that ``build_mime`` produced and that would have been
    POSTed to Gmail's ``drafts.create``.
    """
    captured: dict[str, bytes] = {}

    def fake_create_draft(access_token, thread_id, raw_bytes):
        captured["raw"] = raw_bytes
        return {"id": "draft-1", "message": {"id": "msg-1", "threadId": thread_id or "tid"}}

    with (
        patch.object(mcp_server, "locate_credentials", return_value="/dev/null"),
        patch.object(mcp_server.Credentials, "load", return_value=CREDS),
        patch.object(mcp_server, "refresh_access_token", return_value="tok"),
        patch.object(mcp_server._cd, "latest_reply_headers", return_value=("<a@x>", "<root@x> <a@x>")),
        patch.object(mcp_server._cd, "create_draft", side_effect=fake_create_draft),
    ):
        result = mcp_server._create_draft_impl(
            to=["rcpt@example.com"],
            subject="Re: hello",
            body=body,
            cc=None,
            bcc=None,
            thread_id=thread_id,
            no_reply_headers=no_reply_headers,
            credentials_path=None,
        )
    return result, captured.get("raw", b"")


def _parse(raw: bytes) -> EmailMessage:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert isinstance(msg, EmailMessage)
    return msg


def test_tools_are_registered_without_any_html_parameter():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {"create_draft", "setup_credentials", "check_auth"}
    by_name = {t.name: t for t in tools}
    draft_props = by_name["create_draft"].inputSchema.get("properties", {})
    # The draft tool must never expose an HTML / rich-text body knob.
    assert not any("html" in p.lower() for p in draft_props)
    assert {"to", "subject", "body"} <= set(draft_props)
    # No tool anywhere exposes an html parameter.
    for t in tools:
        assert not any("html" in p.lower() for p in t.inputSchema.get("properties", {}))


def test_impl_produces_single_part_plain_text_with_verbatim_link():
    result, raw = _run_impl(thread_id="tid")
    msg = _parse(raw)
    assert msg.get_content_type() == "text/plain"
    assert not msg.is_multipart()
    assert all(part.get_content_type() != "text/html" for part in msg.walk())
    assert b"text/html" not in raw
    # Link goes out verbatim — no google.com/url tracking redirect.
    assert "https://lists.apache.org/thread/abc123" in msg.get_content()
    assert "google.com/url" not in raw.decode()
    assert result["content_type"] == "text/plain"


def test_impl_return_shape():
    result, _ = _run_impl(thread_id="tid")
    assert result["draft_id"] == "draft-1"
    assert result["message_id"] == "msg-1"
    assert result["thread_id"] == "tid"
    assert result["gmail_url"].endswith("#drafts/msg-1")


def test_impl_sets_reply_headers_when_thread_id_given():
    _, raw = _run_impl(thread_id="tid")
    decoded = raw.decode()
    assert "In-Reply-To: <a@x>" in decoded
    assert "References: <root@x> <a@x>" in decoded


def test_impl_skips_thread_lookup_when_no_reply_headers():
    # Patch directly here (not via _run_impl) so the assertion sees the same
    # mock the implementation would call.
    with (
        patch.object(mcp_server, "locate_credentials", return_value="/dev/null"),
        patch.object(mcp_server.Credentials, "load", return_value=CREDS),
        patch.object(mcp_server, "refresh_access_token", return_value="tok"),
        patch.object(mcp_server._cd, "latest_reply_headers") as latest,
        patch.object(mcp_server._cd, "create_draft", return_value={"id": "d", "message": {"id": "m"}}),
    ):
        mcp_server._create_draft_impl(
            to=["x@example.com"],
            subject="S",
            body="x",
            cc=None,
            bcc=None,
            thread_id="tid",
            no_reply_headers=True,
            credentials_path=None,
        )
        latest.assert_not_called()


def test_impl_skips_thread_lookup_when_no_thread_id():
    _, raw = _run_impl(thread_id=None)
    decoded = raw.decode()
    assert "In-Reply-To:" not in decoded


# --- create_draft SystemExit handling --------------------------------------


def test_create_draft_impl_converts_systemexit_to_tool_error():
    # The CLI helpers raise SystemExit (BaseException); it must be surfaced as
    # a normal tool error, not allowed to kill the server process.
    with patch.object(mcp_server, "locate_credentials", side_effect=SystemExit("no creds found")):
        with pytest.raises(RuntimeError, match="no creds found"):
            mcp_server._create_draft_impl(
                to=["x@example.com"],
                subject="S",
                body="b",
                cc=None,
                bcc=None,
                thread_id=None,
                no_reply_headers=False,
                credentials_path=None,
            )


# --- setup_credentials -----------------------------------------------------


class _FakeOAuthCreds:
    refresh_token = "rt"
    scopes = ("https://mail.google.com/",)


def test_setup_credentials_runs_flow_and_writes(tmp_path):
    secrets = tmp_path / "client_secrets.json"
    secrets.write_text("{}")
    out = tmp_path / "gmail-oauth.json"
    written: dict[str, str] = {}

    def fake_write(**kwargs):
        written.update(kwargs)

    with (
        patch.object(mcp_server._setup, "run_consent_flow", return_value=_FakeOAuthCreds()),
        patch.object(mcp_server._setup, "read_client_app", return_value=("cid", "sec")),
        patch.object(mcp_server._setup, "write_credentials", side_effect=fake_write),
    ):
        result = mcp_server.setup_credentials(
            client_secrets_path=str(secrets),
            from_address="me@example.com",
            credentials_path=str(out),
        )
    assert result["from_address"] == "me@example.com"
    assert result["credentials_path"] == str(out)
    assert result["scopes"] == "https://mail.google.com/"
    assert written["client_id"] == "cid"
    assert written["client_secret"] == "sec"
    assert written["refresh_token"] == "rt"
    assert written["from_address"] == "me@example.com"


def test_setup_credentials_errors_without_from_address(tmp_path):
    secrets = tmp_path / "client_secrets.json"
    secrets.write_text("{}")
    with patch.object(mcp_server._setup, "detect_from_address", return_value=None):
        with pytest.raises(ValueError, match="from_address"):
            mcp_server.setup_credentials(client_secrets_path=str(secrets))


def test_setup_credentials_errors_when_client_secrets_missing(tmp_path):
    with pytest.raises(ValueError, match="client_secrets not found"):
        mcp_server.setup_credentials(
            client_secrets_path=str(tmp_path / "nope.json"),
            from_address="me@example.com",
        )


# --- check_auth ------------------------------------------------------------


def test_check_auth_reports_ok_when_token_refreshes():
    with (
        patch.object(mcp_server, "locate_credentials", return_value=pathlib.Path("/dev/null")),
        patch.object(mcp_server.Credentials, "load", return_value=CREDS),
        patch.object(mcp_server, "refresh_access_token", return_value="tok"),
    ):
        result = mcp_server.check_auth()
    assert result["status"] == "ok"
    assert result["from_address"] == "me@example.com"


def test_check_auth_converts_systemexit_to_tool_error():
    with (
        patch.object(mcp_server, "locate_credentials", return_value=pathlib.Path("/dev/null")),
        patch.object(mcp_server.Credentials, "load", return_value=CREDS),
        patch.object(mcp_server, "refresh_access_token", side_effect=SystemExit("refresh failed (401)")),
    ):
        with pytest.raises(RuntimeError, match="refresh failed"):
            mcp_server.check_auth()
