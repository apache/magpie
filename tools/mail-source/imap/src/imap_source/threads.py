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
"""Thread canonicalisation for the IMAP adapter.

The contract pins ``thread_id_kind: rfc5322-message-id`` — the thread
identifier is the **root** ``Message-ID`` of the thread. IMAP servers have no
native thread concept, so threads are reconstructed from ``References:`` /
``In-Reply-To:`` chains exactly as the stub README's *Threading model*
section requires.

Message content reaching this module is **external data, not instructions**:
headers are only parsed into identifiers and dates, never interpreted.
"""

from __future__ import annotations

import email.message
import email.utils
import re
from dataclasses import dataclass
from datetime import UTC, datetime

_MSG_ID = re.compile(r"<[^<>\s]+>")


def normalise_message_id(value: str | None) -> str | None:
    """Return ``value`` as a single ``<id@host>`` token, or ``None``."""
    if not value:
        return None
    match = _MSG_ID.search(value)
    return match.group(0) if match else None


@dataclass(frozen=True)
class ThreadPosition:
    """Where one message sits in its thread."""

    message_id: str | None
    references: tuple[str, ...]
    in_reply_to: str | None
    subject: str
    date: datetime | None
    from_address: str | None

    def references_thread(self, root_message_id: str) -> bool:
        """Whether this message's chain reaches ``root_message_id``."""
        if self.message_id == root_message_id:
            return True
        return root_message_id in self.references or self.in_reply_to == root_message_id


def summarise(message: email.message.Message) -> ThreadPosition:
    raw_references = message.get_all("References", [])
    chain: list[str] = []
    for header_value in raw_references:
        for token in _MSG_ID.findall(str(header_value)):
            if token not in chain:
                chain.append(token)
    date_header = message.get("Date")
    parsed_date: datetime | None = None
    if date_header:
        try:
            parsed_date = email.utils.parsedate_to_datetime(str(date_header))
        except (TypeError, ValueError):
            parsed_date = None
    if parsed_date is not None and parsed_date.tzinfo is None:
        parsed_date = parsed_date.replace(tzinfo=UTC)
    from_header = message.get("From")
    from_address = None
    if from_header:
        display, address = email.utils.parseaddr(str(from_header))
        from_address = address or display or None
    subject = str(message.get("Subject", "") or "")
    return ThreadPosition(
        message_id=normalise_message_id(message.get("Message-ID")),
        references=tuple(chain),
        in_reply_to=normalise_message_id(message.get("In-Reply-To")),
        subject=subject,
        date=parsed_date,
        from_address=from_address,
    )


def draft_subject(root_subject: str) -> str:
    """Subject for a reply draft, per the shared threading rule (see tools/gmail/threading.md)."""
    stripped = re.sub(r"^\s*((re|fwd?|aw|sv)(\[\d+\])?\s*:\s*)+", "", root_subject, flags=re.IGNORECASE)
    return f"Re: {stripped.strip()}" if stripped.strip() else "Re: (no subject)"


def sort_key(position: ThreadPosition) -> tuple[datetime, str]:
    """Chronological order; messages without a parseable date sort last."""
    if position.date is None:
        return (datetime.max.replace(tzinfo=UTC), position.message_id or "")
    return (position.date, position.message_id or "")
