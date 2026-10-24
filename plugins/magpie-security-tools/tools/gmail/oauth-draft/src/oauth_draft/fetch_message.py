#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Save one Gmail message's full RFC-5322 source to a local ``.eml`` file.

Companion to ``create_draft`` / ``message_id``: same credentials file,
same OAuth refresh-token flow, same broad ``https://mail.google.com/``
scope (read is covered). Read-only — it never modifies the mailbox.

**Why this command exists.** Automated scanners (for example the
Anthropic OSS Scanner) disclose dozens of findings in **one** message of
several megabytes. The claude.ai Gmail MCP returns a message body inline
into the model's context, which either truncates it or exhausts the
context window. This command fetches ``messages.get?format=raw``, decodes
it and writes the bytes to a file, so a parser
(``security-management issue-import-from-scan parse-email``) can split
it into per-finding files the agent reads one at a time.

Usage::

    uv run --project tools/gmail/oauth-draft \
      oauth-draft-fetch-message <messageId> --out <scratch>/scan.eml

Prints one JSON object: the message and thread IDs, the path written, the
byte count, and the ``Subject`` / ``From`` / ``Date`` / ``Message-ID``
headers. The body is **not** printed.
"""

from __future__ import annotations

import argparse
import base64
import email
import email.policy
import json
import os
import pathlib
import tempfile
import urllib.error
import urllib.request

from oauth_draft.credentials import (
    GMAIL_API,
    Credentials,
    locate_credentials,
    refresh_access_token,
)

_HEADERS = ("Subject", "From", "Date", "Message-ID")


def fetch_raw(access_token: str, message_id: str) -> tuple[bytes, str | None]:
    """Return ``(raw RFC-5322 bytes, threadId)`` for one Gmail message."""
    url = f"{GMAIL_API}/messages/{message_id}?format=raw"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        # A multi-megabyte message takes a while; the draft helpers' 15s is too short.
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"Gmail messages.get failed ({e.code}) for {message_id}: {e.read().decode(errors='replace')}"
        ) from e
    raw = data.get("raw")
    if not raw:
        raise SystemExit(f"Gmail messages.get returned no raw source for {message_id}")
    # Gmail returns base64url, sometimes without padding.
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)), data.get("threadId")


def summarize(raw: bytes) -> dict[str, str]:
    """The identifying headers of ``raw`` — never its body."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    return {name: str(msg.get(name, "")) for name in _HEADERS}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="oauth-draft-fetch-message",
        description="Save a Gmail message's full RFC-5322 source to a file (read-only).",
    )
    p.add_argument(
        "message_id", metavar="MESSAGE_ID", help="The Gmail message id (not the Message-ID header)."
    )
    p.add_argument("--out", required=True, help="The .eml file to write.")
    p.add_argument(
        "--credentials",
        default=None,
        help=(
            "Override the credentials file path. "
            "Default: $GMAIL_OAUTH_CREDENTIALS or the packaged default path."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    creds = Credentials.load(locate_credentials(args.credentials), require_from_address=False)
    raw, thread_id = fetch_raw(refresh_access_token(creds), args.message_id)
    out = pathlib.Path(args.out)
    # The message may carry embargoed findings and secrets: owner-only from creation.
    out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # A fresh 0600 file that atomically replaces the target: an existing, more
    # permissive file never holds the confidential contents, even for a moment.
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        os.replace(tmp, out)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise
    print(
        json.dumps(
            {
                "message_id": args.message_id,
                "thread_id": thread_id,
                "path": str(out),
                "bytes": len(raw),
                "headers": summarize(raw),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
