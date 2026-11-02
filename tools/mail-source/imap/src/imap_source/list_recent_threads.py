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
"""``list_recent_threads(list, since)`` — ``IMAP SEARCH SINCE <date>`` against the list folder."""

from __future__ import annotations

import argparse
from typing import Any

from imap_source.cli import add_since_argument, eprint, with_mailbox
from imap_source.config import ImapConfig
from imap_source.mailbox import Mailbox, MailSource
from imap_source.searching import Message, fetch_window, thread_root_of, thread_start_message


def list_recent_threads(
    mailbox: MailSource,
    config: ImapConfig,
    *,
    since_days: int,
) -> list[dict[str, Any]]:
    messages = fetch_window(mailbox, config.list_folder, since_days=since_days)
    grouped: dict[str, list[Message]] = {}
    for message in messages:
        root = thread_root_of(message)
        if root is None:
            continue
        grouped.setdefault(root, []).append(message)

    threads: list[dict[str, Any]] = []
    for root, members in grouped.items():
        # The subject and the sender come from the root when the window holds
        # it, else from the earliest message the window can prove - the same
        # message `read_thread` reports the thread under, so a thread that is
        # listed, read and replied to always carries one subject.
        start = thread_start_message(members, root)
        thread: dict[str, Any] = {
            "thread_id": root,
            "subject": start.position.subject if start is not None else "",
            "started_by": start.position.from_address if start is not None else None,
            "message_count": len(members),
            "last_date": None,
            "uids": [m.uid for m in members],
        }
        for message in members:
            if message.position.date is not None:
                iso_date = message.position.date.isoformat()
                if thread["last_date"] is None or iso_date > str(thread["last_date"]):
                    thread["last_date"] = iso_date
        threads.append(thread)
    return sorted(threads, key=lambda entry: str(entry["last_date"]) or "", reverse=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="imap-source-threads",
        description="List threads newer than the search window on the configured security-list folder.",
    )
    add_since_argument(parser)
    args = parser.parse_args(argv)

    def run(mailbox: Mailbox, config: ImapConfig) -> list[dict[str, Any]]:
        eprint(
            f"searching {config.list_folder} on {config.host} (messages newer than {args.since_days} days)"
        )
        return list_recent_threads(mailbox, config, since_days=args.since_days)

    return with_mailbox(run)


if __name__ == "__main__":
    raise SystemExit(main())
