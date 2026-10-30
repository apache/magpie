#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Resolve the root RFC-5322 ``Message-ID`` header of Gmail thread(s).

Companion to ``create_draft`` / ``mark_threads_read``: same credentials
file, same OAuth refresh-token flow, same broad ``https://mail.google.com/``
scope (read is covered).

**Why this command exists.** The claude.ai Gmail MCP ``get_thread`` tool
only surfaces the *key* headers (``Subject`` / ``From`` / ``To`` / ``Cc`` /
``Date``) plus Gmail's opaque per-message IDs — it does **not** expose the
RFC-5322 ``Message-ID:`` header. The skills want the real ``Message-ID``
because, unlike a Gmail ``threadId`` (which only resolves inside the one
mailbox that holds the thread), the ``Message-ID`` is archive-independent:
it is the stable identifier the reporter's MUA stamped, and it is what the
ASF PonyMail archive hashes its permalinks on. ``security-issue-import``
records it in the *Security mailing list thread* tracker field so the
inbound message stays locatable even from an account that never received
the Gmail copy.

This command fetches ``threads.get?format=metadata&metadataHeaders=Message-ID``
and prints the ``Message-ID`` of the thread's **root** (chronologically
first) message — the inbound report.

Usage::

    uv run --project tools/gmail/oauth-draft \
      oauth-draft-message-id <threadId> [<threadId> ...]

Output is one TSV line per thread: ``<threadId>\\t<message-id>``. A thread
with no resolvable root header prints ``<threadId>\\t`` (empty) and the
command still exits 0 — a missing header is a data fact, not a tool error.
With ``--json`` the same mapping is emitted as a JSON object instead.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from oauth_draft.credentials import (
    GMAIL_API,
    Credentials,
    locate_credentials,
    refresh_access_token,
)


def root_message_id(access_token: str, thread_id: str) -> str | None:
    """Return the ``Message-ID`` header of the thread's root message.

    Returns ``None`` when the thread has no messages or the root message
    carries no ``Message-ID`` header (both are legitimate states, not
    errors — e.g. a draft-only thread).
    """
    params = {
        "format": "metadata",
        "metadataHeaders": "Message-ID",
    }
    # urlencode with doseq so repeated metadataHeaders survive if extended.
    url = f"{GMAIL_API}/threads/{thread_id}?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"Gmail threads.get failed ({e.code}) for {thread_id}: {e.read().decode(errors='replace')}"
        ) from e
    messages = data.get("messages") or []
    if not messages:
        return None
    headers = messages[0].get("payload", {}).get("headers", [])
    for h in headers:
        if h.get("name", "").lower() == "message-id":
            return h.get("value")
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="oauth-draft-message-id",
        description=(
            "Resolve the root RFC-5322 Message-ID header of Gmail thread(s) via the OAuth refresh-token flow."
        ),
    )
    p.add_argument(
        "thread_ids",
        nargs="+",
        metavar="THREAD_ID",
        help="One or more Gmail threadId values to resolve.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit a {threadId: message-id} JSON object instead of TSV lines.",
    )
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
    creds_path = locate_credentials(args.credentials)
    creds = Credentials.load(creds_path, require_from_address=False)
    access_token = refresh_access_token(creds)

    resolved: dict[str, str | None] = {}
    for tid in args.thread_ids:
        resolved[tid] = root_message_id(access_token, tid)

    if args.json:
        print(json.dumps(resolved, indent=2))
    else:
        for tid, mid in resolved.items():
            sys.stdout.write(f"{tid}\t{mid or ''}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
