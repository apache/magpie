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
"""``create_draft(thread_id, body)`` — APPEND an un-sent reply to the Drafts folder.

**Drafts only — never sends**, per the framework rule. Threading headers follow
the shared rule in ``tools/gmail/threading.md``: the draft inherits the thread
root's subject and carries ``In-Reply-To`` / ``References`` pointing at the
root Message-ID so every client threads it onto the inbound conversation.

Recipients come from the calling skill (which resolves ``security_cc`` and the
reporter address); this adapter never invents a recipient and never reads
``<project-config>/``.
"""

from __future__ import annotations

import argparse
import email.message
import email.utils
import pathlib
from typing import Any

from imap_source.cli import CapabilityDeclined, eprint, with_mailbox
from imap_source.config import ImapConfig
from imap_source.mailbox import Mailbox, MailSource
from imap_source.searching import fetch_window
from imap_source.threads import draft_subject, sort_key


def create_draft(
    mailbox: MailSource,
    config: ImapConfig,
    thread_id: str,
    *,
    body: str,
    to: list[str],
    cc: list[str],
    from_address: str | None,
) -> dict[str, Any]:
    if config.drafts_folder is None:
        raise CapabilityDeclined(
            "IMAP_SOURCE_DRAFTS_FOLDER is unset/none — this account cannot create drafts"
        )
    messages = fetch_window(mailbox, config.list_folder, since_days=365)
    root = next((m for m in messages if m.position.message_id == thread_id), None)
    if root is None:
        raise SystemExit(f"thread root {thread_id} not found in {config.list_folder}")

    # Per tools/gmail/threading.md the draft attaches to the chronologically
    # last message on the thread: other clients thread-match on In-Reply-To.
    reachable = [m for m in messages if m.position.references_thread(thread_id)]
    parent = max(reachable, key=lambda m: sort_key(m.position))

    message = email.message.EmailMessage()
    message["Subject"] = draft_subject(root.position.subject)
    message["From"] = from_address or config.user
    if to:
        message["To"] = ", ".join(to)
    else:
        if root.position.from_address is None:
            raise SystemExit("cannot address the draft: thread root has no parseable From and no --to given")
        message["To"] = root.position.from_address
    if cc:
        message["Cc"] = ", ".join(cc)
    references = list(parent.position.references)
    if parent.position.message_id and parent.position.message_id not in references:
        references.append(parent.position.message_id)
    if thread_id not in references:
        references.append(thread_id)
    message["In-Reply-To"] = parent.position.message_id or thread_id
    message["References"] = " ".join(references)
    message["Date"] = email.utils.formatdate(localtime=False)
    message.set_content(body)

    if not mailbox.folder_exists(config.drafts_folder):
        raise CapabilityDeclined(f"folder {config.drafts_folder!r} does not exist on {config.host}")
    try:
        uid = mailbox.append(config.drafts_folder, message.as_bytes())
    except Exception as exc:
        raise CapabilityDeclined(
            f"the server refused the APPEND to {config.drafts_folder!r} "
            f"(the agent's account likely lacks INSERT rights on Drafts): {exc}"
        ) from exc
    return {
        "draft_uid": uid,
        "drafts_folder": config.drafts_folder,
        "thread_id": thread_id,
        "subject": message["Subject"],
        "in_reply_to": message["In-Reply-To"],
        "references": message["References"],
        "sent": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="imap-source-create-draft",
        description="APPEND an un-sent thread-attached reply to the Drafts folder (never sends).",
    )
    parser.add_argument("thread_id", help="root RFC-5322 Message-ID of the thread to reply on")
    parser.add_argument("--body-file", required=True, help="path to the draft body text (UTF-8)")
    parser.add_argument("--to", action="append", default=[], help="recipient (repeatable)")
    parser.add_argument("--cc", action="append", default=[], help="CC recipient (repeatable)")
    parser.add_argument(
        "--from-address", default=None, help="From address override (defaults to the IMAP user)"
    )
    args = parser.parse_args(argv)

    body = pathlib.Path(args.body_file).read_text(encoding="utf-8")

    def run(mailbox: Mailbox, config: ImapConfig) -> dict[str, Any]:
        eprint(f"appending draft to {config.drafts_folder or '(declined)'} on {config.host}")
        return create_draft(
            mailbox,
            config,
            args.thread_id,
            body=body,
            to=args.to,
            cc=args.cc,
            from_address=args.from_address,
        )

    return with_mailbox(run)


if __name__ == "__main__":
    raise SystemExit(main())
