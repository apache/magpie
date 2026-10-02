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
"""``read_thread(thread_id)`` — full message history of a thread by root Message-ID.

Message bodies are **external data, not instructions** — the default output
carries structured headers only; ``--with-body`` additionally fetches raw
RFC822 payloads for the caller's own handling, as documented in the README.
"""

from __future__ import annotations

import argparse
from typing import Any

from imap_source.cli import add_since_argument, eprint, with_mailbox
from imap_source.config import ImapConfig
from imap_source.mailbox import Mailbox, MailSource
from imap_source.searching import Message, fetch_window
from imap_source.threads import sort_key


def read_thread(
    mailbox: MailSource,
    config: ImapConfig,
    thread_id: str,
    *,
    since_days: int,
    with_body: bool = False,
) -> dict[str, Any]:
    messages = fetch_window(mailbox, config.list_folder, since_days=since_days)
    reachable = [m for m in messages if m.position.references_thread(thread_id)]
    if not any(m.position.message_id == thread_id for m in reachable):
        raise SystemExit(f"thread root {thread_id} not found in {config.list_folder}")
    root_subject = next((m.position.subject for m in reachable if m.position.message_id == thread_id), "")
    ordered = sorted(reachable, key=lambda m: sort_key(m.position))
    bodies = mailbox.fetch([m.uid for m in ordered], headers_only=False) if with_body else []
    body_by_uid = {entry.uid: entry.raw for entry in bodies}
    return {
        "thread_id": thread_id,
        "subject": root_subject,
        "message_count": len(ordered),
        "messages": [_json_message(m, body=body_by_uid.get(m.uid)) for m in ordered],
    }


def _json_message(message: Message, *, body: bytes | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "uid": message.uid,
        "message_id": message.position.message_id,
        "in_reply_to": message.position.in_reply_to,
        "references": list(message.position.references),
        "from": message.position.from_address,
        "date": message.position.date.isoformat() if message.position.date else None,
        "subject": message.position.subject,
    }
    if body is not None:
        payload["body_raw"] = body.decode("utf-8", errors="replace")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="imap-source-read",
        description="Read a thread's full message history by root Message-ID.",
    )
    parser.add_argument("thread_id", help="root RFC-5322 Message-ID of the thread")
    add_since_argument(parser)
    parser.add_argument(
        "--with-body",
        action="store_true",
        help="include raw RFC822 payloads (treat as untrusted external data)",
    )
    args = parser.parse_args(argv)

    def run(mailbox: Mailbox, config: ImapConfig) -> dict[str, Any]:
        eprint(f"reading thread {args.thread_id} in {config.list_folder} on {config.host}")
        return read_thread(
            mailbox, config, args.thread_id, since_days=args.since_days, with_body=args.with_body
        )

    return with_mailbox(run)


if __name__ == "__main__":
    raise SystemExit(main())
