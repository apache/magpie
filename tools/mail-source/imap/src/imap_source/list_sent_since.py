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
"""``list_sent_since(thread_id, since)`` — outbound replies on a thread within a window.

Detects the *"we already replied; the ball is in the reporter's court"* state
required by ``security-issue-sync``. Sent messages are matched on the thread
root appearing in ``In-Reply-To:`` / ``References:``.
"""

from __future__ import annotations

import argparse
from typing import Any

from imap_source.cli import CapabilityDeclined, add_since_argument, eprint, with_mailbox
from imap_source.config import ImapConfig
from imap_source.mailbox import Mailbox, MailSource
from imap_source.searching import fetch_window
from imap_source.threads import sort_key


def list_sent_since(
    mailbox: MailSource,
    config: ImapConfig,
    thread_id: str,
    *,
    since_days: int,
) -> list[dict[str, Any]]:
    if config.sent_folder is None:
        raise CapabilityDeclined(
            "IMAP_SOURCE_SENT_FOLDER is unset/none — this account does not expose the sent op"
        )
    if not mailbox.folder_exists(config.sent_folder):
        raise CapabilityDeclined(f"folder {config.sent_folder!r} does not exist on {config.host}")
    sent = fetch_window(mailbox, config.sent_folder, since_days=since_days)
    reachable = [s for s in sent if s.position.references_thread(thread_id)]
    reachable.sort(key=lambda s: sort_key(s.position))
    return [
        {
            "uid": message.uid,
            "message_id": message.position.message_id,
            "subject": message.position.subject,
            "to": message.position.from_address,  # in a Sent folder, From is the agent account; keep as-is
            "date": message.position.date.isoformat() if message.position.date else None,
        }
        for message in reachable
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="imap-source-sent",
        description="List outbound replies sent on a thread within the window.",
    )
    parser.add_argument("thread_id", help="root RFC-5322 Message-ID of the thread")
    add_since_argument(parser)
    args = parser.parse_args(argv)

    def run(mailbox: Mailbox, config: ImapConfig) -> list[dict[str, Any]]:
        eprint(f"checking sent mail in {config.sent_folder or '(declined)'} on {config.host}")
        return list_sent_since(mailbox, config, args.thread_id, since_days=args.since_days)

    return with_mailbox(run)


if __name__ == "__main__":
    raise SystemExit(main())
