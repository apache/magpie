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
"""Shared header-window search used by the read operations."""

from __future__ import annotations

import email
import email.message
import email.policy
from dataclasses import dataclass
from datetime import UTC

from imap_source.mailbox import MailSource
from imap_source.threads import ThreadPosition, sort_key, summarise


@dataclass(frozen=True)
class Message:
    uid: int
    position: ThreadPosition
    raw_headers: bytes


def parse_message(raw: bytes) -> email.message.Message:
    """Parse hostile external bytes into a structured message; never interpreted as instructions."""
    return email.message_from_bytes(raw, policy=email.policy.compat32)


def headers_of(raw: bytes) -> email.message.Message:
    """Parse only the header block (raw already carries RFC822.HEADER payloads)."""
    return parse_message(raw)


def fetch_window(mailbox: MailSource, folder: str, *, since_days: int) -> list[Message]:
    """Select ``folder`` read-only and return header summaries for messages newer than ``since_days``."""
    mailbox.select(folder, read_only=True)
    uids = mailbox.search_uids("SINCE", _since_date(since_days))
    heads = mailbox.fetch(uids, headers_only=True)
    messages: list[Message] = []
    for head in heads:
        parsed = headers_of(head.raw)
        messages.append(Message(uid=head.uid, position=summarise(parsed), raw_headers=head.raw))
    messages.sort(key=lambda entry: sort_key(entry.position))
    return messages


def thread_root_of(message: Message) -> str | None:
    """Thread root = first element of the References chain, else the message's own Message-ID."""
    if message.position.references:
        return message.position.references[0]
    return message.position.message_id


def _since_date(days: int) -> str:
    from datetime import datetime, timedelta

    return (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%d-%b-%Y")
