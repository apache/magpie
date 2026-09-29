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
from imap_source.searching import fetch_window, thread_root_of


def list_recent_threads(
    mailbox: MailSource,
    config: ImapConfig,
    *,
    since_days: int,
) -> list[dict[str, Any]]:
    messages = fetch_window(mailbox, config.list_folder, since_days=since_days)
    threads: dict[str, dict[str, Any]] = {}
    for message in messages:
        root = thread_root_of(message)
        if root is None:
            continue
        thread = threads.setdefault(
            root,
            {
                "thread_id": root,
                "subject": message.position.subject,
                "started_by": message.position.from_address,
                "message_count": 0,
                "last_date": None,
                "uids": [],
            },
        )
        thread["message_count"] += 1
        thread["uids"].append(message.uid)
        if message.position.date is not None:
            iso_date = message.position.date.isoformat()
            if thread["last_date"] is None or iso_date > str(thread["last_date"]):
                thread["last_date"] = iso_date
    return sorted(threads.values(), key=lambda entry: str(entry["last_date"]) or "", reverse=True)


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
