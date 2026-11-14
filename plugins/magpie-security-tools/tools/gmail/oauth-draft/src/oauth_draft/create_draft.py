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
"""Create a Gmail draft with ``threadId`` attachment via the Gmail REST API.

This script exists because the claude.ai Gmail MCP connector's
``mcp__claude_ai_Gmail__create_draft`` tool does **not** expose a
``threadId`` parameter — the Gmail API supports it, but the MCP does not
plumb it through. Drafts created via that MCP start a new conversation on
the user's own Gmail side; recipients' clients thread-match by subject,
but the sender's own conversation view does not.

This module takes the OAuth+curl route: it holds a user-provided Google
OAuth refresh token, trades it for a short-lived access token, and POSTs
a raw RFC822 message to Gmail's ``drafts.create`` endpoint with both the
``threadId`` attachment **and** ``In-Reply-To`` / ``References`` MIME
headers derived from the last message in the thread. The resulting
draft threads reliably on every client. For a message that never reached
the user's Gmail (only in the PonyMail archive, say), ``--in-reply-to`` /
``--references`` set those headers from Message-IDs the caller already has.

Pick this backend by setting ``tools.gmail.draft_backend: oauth_curl``
in your ``config/user.md``. See ``tools/gmail/draft-backends.md`` for
setup instructions (creating the Google Cloud OAuth client, obtaining a
refresh token, and populating the credentials file).
"""

from __future__ import annotations

import argparse
import base64
import email.message
import email.utils
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

from oauth_draft.credentials import (
    GMAIL_API,
    Credentials,
    locate_credentials,
    refresh_access_token,
)


def api_get(access_token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"{GMAIL_API}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Gmail API {path} failed ({e.code}): {e.read().decode(errors='replace')}") from e


def api_post(access_token: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{GMAIL_API}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Gmail API {path} failed ({e.code}): {e.read().decode(errors='replace')}") from e


def headers_from_thread(thread: dict) -> tuple[str | None, str | None]:
    """Return ``(in_reply_to, references)`` derived from ``thread``'s last message.

    Pure helper — accepts the parsed ``threads.get`` response so it can
    be unit-tested without hitting the Gmail API. The companion
    :func:`latest_reply_headers` does the network round-trip and
    delegates the parsing here.
    """
    messages = thread.get("messages") or []
    if not messages:
        return (None, None)
    last = messages[-1]
    headers = {h["name"].lower(): h["value"] for h in last.get("payload", {}).get("headers", [])}
    msg_id = headers.get("message-id")
    existing_refs = headers.get("references", "")
    if not msg_id:
        return (None, None)
    references = (existing_refs + " " + msg_id).strip() if existing_refs else msg_id
    return (msg_id, references)


def latest_reply_headers(access_token: str, thread_id: str) -> tuple[str | None, str | None]:
    """Return ``(in_reply_to, references)`` for the last message in ``thread_id``."""
    thread = api_get(access_token, f"/threads/{thread_id}?format=full")
    return headers_from_thread(thread)


# Printable ASCII without space, '<', '>' or '@': a Message-ID never carries
# whitespace, so CR / LF (header injection) cannot get through either.
_MSG_ID_PART = r"[!-;=?A-~]+"
_MSG_ID_BODY = re.compile(rf"{_MSG_ID_PART}@{_MSG_ID_PART}")


def normalize_message_id(value: str) -> str:
    """Return ``value`` as a bracketed ``<local@domain>`` Message-ID.

    Angle brackets are optional on input. Anything that is not a single
    ``local@domain`` token -- whitespace, CR / LF, control or non-ASCII
    characters, a missing ``@``, unbalanced brackets -- raises ``ValueError``.
    """
    body = value
    if body.startswith("<") and body.endswith(">"):
        body = body[1:-1]
    if not _MSG_ID_BODY.fullmatch(body):
        raise ValueError(f"not a Message-ID (expected <local@domain>): {value!r}")
    return f"<{body}>"


def explicit_reply_headers(in_reply_to: str | None, references: str | None) -> tuple[str | None, str | None]:
    """Validate caller-supplied threading headers and return ``(in_reply_to, references)``.

    For replying to a message that is not in the user's Gmail (for example a
    report only in the PonyMail archive), so there is no ``threadId`` to read
    the headers from. ``references`` is a space-separated list of Message-IDs,
    root first; it defaults to ``in_reply_to`` alone, and ``in_reply_to`` is
    appended when the list does not already name it (RFC 5322: a reply's
    ``References`` is its parent's ``References`` plus the parent's ID).
    """
    if not in_reply_to:
        if references:
            raise ValueError("references needs in_reply_to")
        return (None, None)
    parent = normalize_message_id(in_reply_to)
    chain = (
        [normalize_message_id(ref) for ref in re.split(r"[ \t]+", references.strip(" \t"))]
        if references
        else []
    )
    if parent not in chain:
        chain.append(parent)
    return (parent, " ".join(chain))


def choose_reply_headers(
    access_token: str,
    thread_id: str | None,
    explicit: tuple[str | None, str | None],
    no_reply_headers: bool,
) -> tuple[str | None, str | None]:
    """Pick the draft's ``(in_reply_to, references)``.

    Headers from :func:`explicit_reply_headers` win over the ones derived from
    ``thread_id``'s last message, and skip that lookup; ``thread_id`` still
    attaches the draft to the Gmail thread.
    """
    if explicit[0]:
        return explicit
    if thread_id and not no_reply_headers:
        return latest_reply_headers(access_token, thread_id)
    return (None, None)


def build_mime(
    from_addr: str,
    to: list[str],
    cc: list[str],
    bcc: list[str],
    subject: str,
    body: str,
    in_reply_to: str | None,
    references: str | None,
) -> bytes:
    msg = email.message.EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    # Plain text only — by design. ``set_content(str)`` produces a
    # single ``text/plain; charset="utf-8"`` part with no ``text/html``
    # alternative. The project's outbound mail is always plain text:
    # never call ``add_alternative`` / ``set_content(..., subtype="html")``
    # here, and never attach an HTML body. (The test suite asserts the
    # built message stays single-part text/plain.)
    msg.set_content(body)
    return bytes(msg)


def create_draft(access_token: str, thread_id: str | None, raw_bytes: bytes) -> dict:
    raw_b64url = base64.urlsafe_b64encode(raw_bytes).decode().rstrip("=")
    message: dict = {"raw": raw_b64url}
    if thread_id:
        message["threadId"] = thread_id
    return api_post(access_token, "/drafts", {"message": message})


def read_body(path: str | None) -> str:
    if path == "-" or path is None:
        return sys.stdin.read()
    return pathlib.Path(path).expanduser().read_text()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n\n", 1)[0],
    )
    p.add_argument(
        "--thread-id",
        help=(
            "Gmail threadId to attach the draft to. If omitted, the draft "
            "starts a new conversation (subject-matched fallback on recipient side)."
        ),
    )
    p.add_argument(
        "--to",
        action="append",
        required=True,
        help="Primary recipient (may be repeated)",
    )
    p.add_argument(
        "--cc",
        action="append",
        default=[],
        help="Cc recipient (may be repeated)",
    )
    p.add_argument(
        "--bcc",
        action="append",
        default=[],
        help="Bcc recipient (may be repeated)",
    )
    p.add_argument(
        "--subject",
        required=True,
        help="Subject line — typically 'Re: <root subject>' when attaching to a thread",
    )
    p.add_argument(
        "--body-file",
        default="-",
        help="Path to a plain-text body file, or '-' for stdin (the default)",
    )
    p.add_argument(
        "--credentials",
        help=(
            "Path to the OAuth credentials JSON. "
            "Defaults to $GMAIL_OAUTH_CREDENTIALS or "
            "~/.config/apache-magpie/gmail-oauth.json."
        ),
    )
    p.add_argument(
        "--no-reply-headers",
        action="store_true",
        help=(
            "Skip setting In-Reply-To / References from the thread's last message. Useful for smoke-testing."
        ),
    )
    p.add_argument(
        "--in-reply-to",
        help=(
            "Message-ID the draft replies to (angle brackets optional). For a message that is not "
            "in this Gmail account, e.g. one only in the PonyMail archive. Wins over the headers "
            "derived from --thread-id, which still attaches the draft to that thread."
        ),
    )
    p.add_argument(
        "--references",
        help=(
            "Space-separated Message-IDs for the References header, root first. Needs "
            "--in-reply-to, which is appended when missing. Default: the --in-reply-to ID alone."
        ),
    )
    args = p.parse_args(argv)
    if args.no_reply_headers and args.in_reply_to:
        p.error("--no-reply-headers and --in-reply-to are mutually exclusive")
    try:
        args.in_reply_to, args.references = explicit_reply_headers(args.in_reply_to, args.references)
    except ValueError as e:
        p.error(str(e))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    creds = Credentials.load(locate_credentials(args.credentials))
    assert creds.from_address is not None  # required=True path above
    access_token = refresh_access_token(creds)

    in_reply_to, references = choose_reply_headers(
        access_token,
        args.thread_id,
        (args.in_reply_to, args.references),
        args.no_reply_headers,
    )

    raw = build_mime(
        from_addr=creds.from_address,
        to=args.to,
        cc=args.cc,
        bcc=args.bcc,
        subject=args.subject,
        body=read_body(args.body_file),
        in_reply_to=in_reply_to,
        references=references,
    )
    result = create_draft(access_token, args.thread_id, raw)
    draft_id = result.get("id", "?")
    draft_message_id = result.get("message", {}).get("id", "?")
    print(f"Draft ID:    {draft_id}")
    print(f"Message ID:  {draft_message_id}")
    print(f"Gmail URL:   https://mail.google.com/mail/u/0/#drafts/{draft_message_id}")
    print(f"Thread ID:   {result.get('message', {}).get('threadId', '(new)')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
