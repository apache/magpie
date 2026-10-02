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
"""``list_drafts(thread_id)`` — draft replies already attached to a thread.

Contract rule: *never propose a fresh draft when one is already pending*.
When ``IMAP_SOURCE_DRAFTS_FOLDER`` is unset/``none`` the op is **declined**
(exit 3) rather than faked, so the skill's resolution chain can fall through.
"""

from __future__ import annotations

import argparse
from typing import Any

from imap_source.cli import CapabilityDeclined, add_since_argument, eprint, with_mailbox
from imap_source.config import ImapConfig
from imap_source.mailbox import Mailbox, MailSource
from imap_source.searching import fetch_window
from imap_source.threads import sort_key


def list_drafts(
    mailbox: MailSource,
    config: ImapConfig,
    thread_id: str,
    *,
    since_days: int,
) -> list[dict[str, Any]]:
    if config.drafts_folder is None:
        raise CapabilityDeclined(
            "IMAP_SOURCE_DRAFTS_FOLDER is unset/none — this account does not expose drafts ops"
        )
    if not mailbox.folder_exists(config.drafts_folder):
        raise CapabilityDeclined(f"folder {config.drafts_folder!r} does not exist on {config.host}")
    drafts = fetch_window(mailbox, config.drafts_folder, since_days=since_days)
    reachable = [d for d in drafts if d.position.references_thread(thread_id)]
    reachable.sort(key=lambda d: sort_key(d.position))
    return [
        {
            "uid": draft.uid,
            "message_id": draft.position.message_id,
            "subject": draft.position.subject,
            "date": draft.position.date.isoformat() if draft.position.date else None,
        }
        for draft in reachable
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="imap-source-drafts",
        description="List draft replies already attached to a thread (idempotency check).",
    )
    parser.add_argument("thread_id", help="root RFC-5322 Message-ID of the thread")
    add_since_argument(parser)
    args = parser.parse_args(argv)

    def run(mailbox: Mailbox, config: ImapConfig) -> list[dict[str, Any]]:
        eprint(f"checking drafts in {config.drafts_folder or '(declined)'} on {config.host}")
        return list_drafts(mailbox, config, args.thread_id, since_days=args.since_days)

    return with_mailbox(run)


if __name__ == "__main__":
    raise SystemExit(main())
