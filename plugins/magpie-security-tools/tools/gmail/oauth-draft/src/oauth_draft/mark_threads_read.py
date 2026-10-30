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
"""Bulk-modify Gmail threads via the OAuth refresh-token flow.

Companion to ``create_draft``: same credentials file, same auth
flow, same broad ``https://mail.google.com/`` scope. Default behaviour
is *mark threads matching ``--query`` as read* (i.e. remove the
system ``UNREAD`` label). Add or remove arbitrary labels via
``--add-label`` / ``--remove-label``.

Why this exists: the claude.ai Gmail MCP connector's modify-side
tools (``unlabel_thread``, ``label_thread``) ride on an OAuth scope
set that excludes ``gmail.modify``, so bulk mark-as-read fails with
*"Request had insufficient authentication scopes"*. The
``oauth_curl`` backend's setup
(see ``tools/gmail/oauth-draft/README.md``) already grants the broader
scope, which covers modify, so this command just rides on the
credentials file the user already has.

The token returned by the refresh-token flow lives ~1 hour. The
script does not refresh mid-run; if you ever drive this against a
list of more than a few thousand threads, refactor to refresh on
401 / when ``time.monotonic() > token_acquired_at + 3000``.
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


def list_thread_ids(access_token: str, query: str) -> list[str]:
    """Paginate ``threads.list?q=<query>`` and return every matching thread ID."""
    ids: list[str] = []
    page_token: str | None = None
    while True:
        params = {"q": query, "maxResults": "500"}
        if page_token:
            params["pageToken"] = page_token
        url = f"{GMAIL_API}/threads?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise SystemExit(
                f"Gmail threads.list failed ({e.code}): {e.read().decode(errors='replace')}"
            ) from e
        ids.extend(t["id"] for t in data.get("threads", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return ids


def modify_thread(
    access_token: str,
    thread_id: str,
    add_labels: list[str],
    remove_labels: list[str],
) -> None:
    payload: dict = {}
    if add_labels:
        payload["addLabelIds"] = add_labels
    if remove_labels:
        payload["removeLabelIds"] = remove_labels
    req = urllib.request.Request(
        f"{GMAIL_API}/threads/{thread_id}/modify",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"Gmail threads.modify failed ({e.code}) for {thread_id}: {e.read().decode(errors='replace')}"
        ) from e


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Bulk-modify Gmail threads matching a search query.",
    )
    ap.add_argument(
        "--query",
        required=True,
        help='Gmail search query, e.g. "label:apache-security in:spam is:unread".',
    )
    ap.add_argument(
        "--add-label",
        action="append",
        default=[],
        help="System or user label ID to add. Repeatable. Default: none.",
    )
    ap.add_argument(
        "--remove-label",
        action="append",
        default=[],
        help=(
            "System or user label ID to remove. Repeatable. "
            'Default when neither --add-label nor --remove-label is given: ["UNREAD"] '
            "(i.e. mark threads as read)."
        ),
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually modify matching threads. The default is a list-only dry-run "
            "(prints matches and the count, makes no Gmail writes). Required for "
            "any mutation; the two-step shape is the safety gate against typo-induced "
            "broad-query mailbox damage."
        ),
    )
    ap.add_argument(
        "--max",
        type=int,
        default=None,
        help="Cap the number of threads listed/modified. Useful for smoke tests.",
    )
    ap.add_argument(
        "--credentials",
        help=(
            "Override the credentials file path. "
            "Default: $GMAIL_OAUTH_CREDENTIALS or "
            "~/.config/apache-magpie/gmail-oauth.json."
        ),
    )
    args = ap.parse_args(argv)
    if not args.add_label and not args.remove_label:
        args.remove_label = ["UNREAD"]
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    creds_path = locate_credentials(args.credentials)
    creds = Credentials.load(creds_path, require_from_address=False)
    access_token = refresh_access_token(creds)

    print(f"Listing threads matching: {args.query!r}", file=sys.stderr)
    ids = list_thread_ids(access_token, args.query)
    print(f"Found {len(ids)} matching thread(s).", file=sys.stderr)

    if args.max is not None and len(ids) > args.max:
        print(f"--max={args.max}: trimming to first {args.max}.", file=sys.stderr)
        ids = ids[: args.max]

    if not args.execute:
        for tid in ids:
            print(tid)
        print(
            f"Dry-run: {len(ids)} thread(s) would be modified "
            f"(add: {args.add_label or '[]'}, remove: {args.remove_label or '[]'}). "
            f"Re-run with --execute to apply.",
            file=sys.stderr,
        )
        return 0

    print(
        f"Modifying {len(ids)} thread(s) "
        f"(add: {args.add_label or '[]'}, remove: {args.remove_label or '[]'})...",
        file=sys.stderr,
    )
    failed = 0
    for i, tid in enumerate(ids, 1):
        try:
            modify_thread(access_token, tid, args.add_label, args.remove_label)
        except SystemExit as e:
            print(f"[{i}/{len(ids)}] FAILED {tid}: {e}", file=sys.stderr)
            failed += 1
            continue
        if i % 25 == 0 or i == len(ids):
            print(f"[{i}/{len(ids)}] done", file=sys.stderr)
    if failed:
        print(f"FAILED: {failed} thread(s) did not get modified.", file=sys.stderr)
        return 1
    print(f"OK: {len(ids)} thread(s) modified.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
