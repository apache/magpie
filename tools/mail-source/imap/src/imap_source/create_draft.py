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

A thread whose root sits outside the fetched window is still replyable - an
archive read from the middle of a conversation holds the replies but not the
report. The draft then inherits the subject of the same message
``read_thread`` and ``list_recent_threads`` report the thread under (the
earliest the window can prove), and - when the caller names no recipient -
addresses the earliest message that is not this adapter's own account,
falling back to the earliest message.

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
from imap_source.searching import Message, fetch_window, thread_start_message
from imap_source.threads import canonical_thread_id, draft_subject, sort_key


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
    thread_id = canonical_thread_id(thread_id) or thread_id
    if config.drafts_folder is None:
        raise CapabilityDeclined(
            "IMAP_SOURCE_DRAFTS_FOLDER is unset/none — this account cannot create drafts"
        )
    messages = fetch_window(mailbox, config.list_folder, since_days=365)
    reachable = [m for m in messages if m.position.references_thread(thread_id)]
    if not reachable:
        raise SystemExit(f"thread {thread_id} not found in {config.list_folder}")
    ordered = sorted(reachable, key=lambda m: sort_key(m.position))
    root = next((m for m in ordered if m.position.message_id == thread_id), None)
    # The root may sit outside the fetched window: the thread is still
    # replyable, because `read_thread` returns it and `list_recent_threads`
    # lists it. The subject then comes from the same message those two report
    # it under, and the default recipient from the earliest sender that is not
    # this account - the one address the adapter knows is the project's own.
    # The earliest fetched message is not necessarily the reporter: a thread the
    # project answered first would otherwise address the project itself.
    start = thread_start_message(ordered, thread_id)
    addressee = root if root is not None else _first_foreign_sender(ordered, config.user)

    # Per tools/gmail/threading.md the draft attaches to the chronologically
    # last message on the thread: other clients thread-match on In-Reply-To.
    parent = ordered[-1]

    message = email.message.EmailMessage()
    message["Subject"] = draft_subject(start.position.subject if start is not None else "")
    message["From"] = from_address or config.user
    if to:
        message["To"] = ", ".join(to)
    else:
        recipient = addressee.position.from_address
        if recipient is None:
            raise SystemExit("cannot address the draft: the thread has no parseable From and no --to given")
        message["To"] = recipient
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


def _first_foreign_sender(messages: list[Message], own_address: str) -> Message:
    """The earliest message with a sender that is not this adapter's own account.

    A heuristic, documented in the README: a thread the project answered before
    the window starts would still address the maintainer who replied first.
    Addresses are compared case-insensitively, as clients vary their case. A
    message with no parseable ``From`` is skipped, so it never wins over a
    later message that can be addressed.
    """
    own = own_address.casefold()
    return next(
        (
            message
            for message in messages
            if message.position.from_address is not None and message.position.from_address.casefold() != own
        ),
        messages[0],
    )


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
