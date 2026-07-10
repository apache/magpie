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
"""An MCP-server frontend for the ``oauth-draft`` Gmail helpers.

This exposes the same OAuth+REST plain-text drafting that
``oauth-draft-create`` provides on the command line as a single MCP
tool, ``create_draft``, so any MCP-speaking agent can create Gmail
drafts **without** going through the claude.ai Gmail connector.

Why an agent should prefer this over the claude.ai Gmail MCP
------------------------------------------------------------
The claude.ai Gmail connector's ``create_draft`` silently rewrites
embedded URLs into Google tracking redirects
(``https://www.google.com/url?...``) and can attach open/click
tracking. This server POSTs a raw RFC822 message straight to Gmail's
``drafts.create`` endpoint, so links go out **verbatim** and no
tracking is added. See ``tools/gmail/draft-backends.md``.

Plain text only, by construction
--------------------------------
The one tool exposes **no** HTML / rich-text parameter, and the
message is built by :func:`oauth_draft.create_draft.build_mime`, which
uses ``EmailMessage.set_content(str)`` — a single
``text/plain; charset="utf-8"`` part, never ``text/html`` or a
``multipart/alternative``. There is deliberately no code path here
that can emit HTML. (The test suite asserts this.)

Auth reuses the shared ``oauth-draft`` credential handling: the same
``~/.config/apache-magpie/gmail-oauth.json`` file (overridable via
``$GMAIL_OAUTH_CREDENTIALS`` or the ``credentials_path`` argument),
created by ``oauth-draft-setup``. See ``tools/gmail/oauth-draft/README.md``.

Run
---
    uv run --project <framework>/tools/gmail/oauth-draft --extra mcp \\
        oauth-draft-mcp

Register with Claude Code (user scope, so every project sees it)::

    claude mcp add gmail-plaintext -s user -- \\
        uv run --project <framework>/tools/gmail/oauth-draft --extra mcp \\
        oauth-draft-mcp

The server name ``gmail-plaintext`` makes the tool available to agents
as ``mcp__gmail-plaintext__create_draft``.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from oauth_draft import create_draft as _cd
from oauth_draft.credentials import (
    Credentials,
    locate_credentials,
    refresh_access_token,
)

mcp = FastMCP("gmail-plaintext")


def _create_draft_impl(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None,
    bcc: list[str] | None,
    thread_id: str | None,
    no_reply_headers: bool,
    credentials_path: str | None,
) -> dict[str, str]:
    """Shared implementation, kept plain so the tests can call it directly."""
    creds = Credentials.load(locate_credentials(credentials_path))
    assert creds.from_address is not None  # require_from_address=True default
    access_token = refresh_access_token(creds)

    if thread_id and not no_reply_headers:
        in_reply_to, references = _cd.latest_reply_headers(access_token, thread_id)
    else:
        in_reply_to, references = (None, None)

    raw = _cd.build_mime(
        from_addr=creds.from_address,
        to=to,
        cc=cc or [],
        bcc=bcc or [],
        subject=subject,
        body=body,
        in_reply_to=in_reply_to,
        references=references,
    )
    result = _cd.create_draft(access_token, thread_id, raw)
    message: dict[str, Any] = result.get("message", {}) or {}
    draft_message_id = str(message.get("id", ""))
    return {
        "draft_id": str(result.get("id", "")),
        "message_id": draft_message_id,
        "thread_id": str(message.get("threadId", "")),
        "gmail_url": f"https://mail.google.com/mail/u/0/#drafts/{draft_message_id}",
        "content_type": "text/plain",
    }


@mcp.tool()
def create_draft(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    thread_id: str | None = None,
    no_reply_headers: bool = False,
    credentials_path: str | None = None,
) -> dict[str, str]:
    """Create a Gmail draft as PLAIN TEXT ONLY (no HTML, no tracking).

    The draft is created in the authenticated account and left
    **unsent** — the human reviews it and sends it from Gmail. The body
    is transmitted verbatim as a single ``text/plain`` part; links are
    NOT rewrapped into tracking redirects.

    Args:
        to: Primary recipient addresses (plain ``user@host``, no display name).
        subject: Subject line (typically ``Re: <root subject>`` when replying).
        body: Plain-text message body. Sent exactly as given.
        cc: Optional Cc recipients.
        bcc: Optional Bcc recipients.
        thread_id: Optional Gmail ``threadId`` to attach the draft to. When
            set (and ``no_reply_headers`` is false), the server reads the
            thread's last message and sets ``In-Reply-To`` / ``References``
            so the draft threads reliably on every mail client.
        no_reply_headers: Skip the thread lookup / reply headers. Only useful
            for smoke tests — production replies always want the headers.
        credentials_path: Override the OAuth credentials JSON path. Defaults
            to ``$GMAIL_OAUTH_CREDENTIALS`` or
            ``~/.config/apache-magpie/gmail-oauth.json``.

    Returns:
        ``{draft_id, message_id, thread_id, gmail_url, content_type}``.
    """
    return _create_draft_impl(
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        thread_id=thread_id,
        no_reply_headers=no_reply_headers,
        credentials_path=credentials_path,
    )


def main() -> None:
    """Console-script entry point: run the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
