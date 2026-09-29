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
"""Fake IMAP backend with the same method surface ``Mailbox`` uses.

No network, no real server: every operation test seeds RFC822 messages into
``FakeMailbox`` and exercises the same code paths the console scripts run.
UIDs are per-folder, mirroring real IMAP semantics.
"""

from __future__ import annotations

import email.message
import email.policy
from collections.abc import Iterable
from dataclasses import dataclass, field

from imap_source.config import ImapConfig
from imap_source.mailbox import MessageHead


@dataclass
class FakeMailbox:
    folders: dict[str, dict[int, bytes]] = field(default_factory=dict)
    selected: str | None = None
    next_uid: dict[str, int] = field(default_factory=dict)
    read_only: bool = True

    @classmethod
    def seed(cls, **folders: list[bytes]) -> FakeMailbox:
        box = cls()
        for name, messages in folders.items():
            box.folders.setdefault(name, {})  # declare the folder even when empty
            for raw in messages:
                box.append(name, raw)
        return box

    def append(self, folder: str, message: bytes, *, flags: str = "\\Draft") -> int:
        _ = flags
        store = self.folders.setdefault(folder, {})
        uid = self.next_uid.get(folder, 1)
        self.next_uid[folder] = uid + 1
        store[uid] = message
        return uid

    def folder_exists(self, name: str) -> bool:
        return name in self.folders

    def select(self, name: str, *, read_only: bool = True) -> None:
        if name not in self.folders:
            raise KeyError(name)
        self.selected = name
        self.read_only = read_only

    def search_uids(self, *criteria: str) -> list[int]:
        assert self.selected is not None, "select() before search_uids()"
        # The fake does not implement server-side date filtering; SINCE is the
        # server's job, and the header-side logic under test is date-agnostic.
        _ = criteria
        return sorted(self.folders[self.selected])

    def fetch(self, uids: Iterable[int], *, headers_only: bool = True) -> list[MessageHead]:
        assert self.selected is not None
        store = self.folders[self.selected]
        heads: list[MessageHead] = []
        for uid in uids:
            raw = store[uid]
            if headers_only:
                raw = raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
            heads.append(MessageHead(uid=uid, raw=raw))
        return heads


def make_config(**overrides: object) -> ImapConfig:
    base: dict[str, object] = {
        "host": "imap.example.org",
        "port": 993,
        "use_tls": True,
        "user": "security-triage@example.org",
        "password": "app-password",
        "list_folder": "INBOX",
        "sent_folder": "Sent",
        "drafts_folder": "Drafts",
        "archive_template": None,
    }
    base.update(overrides)
    return ImapConfig(**base)  # type: ignore[arg-type]


def build_message(
    message_id: str,
    subject: str,
    sender: str,
    references: str | None = None,
    in_reply_to: str | None = None,
    date: str = "Mon, 21 Sep 2026 10:00:00 +0000",
    body: str = "external content\n",
) -> bytes:
    message = email.message.EmailMessage(policy=email.policy.default)
    message["Message-ID"] = message_id
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = "security-triage@example.org"
    message["Date"] = date
    if references:
        message["References"] = references
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    message.set_content(body)
    return message.as_bytes()
