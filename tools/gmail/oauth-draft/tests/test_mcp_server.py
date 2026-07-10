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
from email.message import EmailMessage
from unittest.mock import patch

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


def test_tool_is_registered_without_any_html_parameter():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {"create_draft"}
    props = tools[0].inputSchema.get("properties", {})
    # The tool must never expose an HTML / rich-text body knob.
    assert not any("html" in p.lower() for p in props)
    assert {"to", "subject", "body"} <= set(props)


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
