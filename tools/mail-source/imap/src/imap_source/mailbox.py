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
"""Thin, UID-based wrapper over ``imaplib``.

Everything the operation modules need goes through :class:`Mailbox`; tests
inject a fake with the same method surface instead of talking to a real
server (see ``tests/conftest.py``). Only :func:`connect` touches ``imaplib``
itself.
"""

from __future__ import annotations

import contextlib
import imaplib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from imap_source.config import ImapConfig


@dataclass(frozen=True)
class MessageHead:
    uid: int
    raw: bytes


class ImapOperationError(RuntimeError):
    """A server-side operation failed (folder missing, permission denied, …)."""


@runtime_checkable
class MailSource(Protocol):
    """The method surface the operation modules need — satisfied by ``Mailbox`` and by test fakes."""

    def folder_exists(self, name: str) -> bool:
        """Whether ``name`` exists as a mailbox folder on the server."""

    def select(self, name: str, *, read_only: bool = True) -> None:
        """Select ``name`` as the current mailbox, read-only by default."""

    def search_uids(self, *criteria: str) -> list[int]:
        """Run a UID SEARCH with the given IMAP criteria and return numeric UIDs."""

    def fetch(self, uids: Iterable[int], *, headers_only: bool = True) -> list[MessageHead]:
        """Fetch header or full payloads for the given UIDs."""

    def append(self, folder: str, message: bytes, *, flags: str = "\\Draft") -> int:
        """APPEND a raw RFC822 message to ``folder`` and return its UID."""


class Mailbox:
    def __init__(self, connection: imaplib.IMAP4 | imaplib.IMAP4_SSL) -> None:
        self._connection = connection

    @classmethod
    def connect(cls, config: ImapConfig) -> Mailbox:
        if config.use_tls:
            connection: imaplib.IMAP4 | imaplib.IMAP4_SSL = imaplib.IMAP4_SSL(config.host, config.port)
        else:
            connection = imaplib.IMAP4(config.host, config.port)
        try:
            connection.login(config.user, config.password)
        except imaplib.IMAP4.error as exc:
            connection.logout()
            raise ImapOperationError(f"login failed for {config.user}@{config.host}: {exc}") from exc
        return cls(connection)

    def logout(self) -> None:
        with contextlib.suppress(imaplib.IMAP4.error):  # pragma: no cover - best-effort teardown
            self._connection.logout()

    def folder_exists(self, name: str) -> bool:
        status, data = self._connection.list('""', _quote(name))
        if status != "OK" or not data:
            return False
        quoted = _quote(name).encode()
        return any(line is not None and quoted in (line if isinstance(line, bytes) else b"") for line in data)

    def select(self, name: str, *, read_only: bool = True) -> None:
        status, _data = self._connection.select(_quote(name), readonly=read_only)
        if status != "OK":
            raise ImapOperationError(f"cannot select folder {name!r}")

    def search_uids(self, *criteria: str) -> list[int]:
        """Run ``UID SEARCH`` with IMAP quoted criteria and return numeric UIDs."""
        program = " ".join(_quote(part) if " " in part else part for part in criteria)
        # imaplib's documented way to omit the charset argument is None.
        status, data = self._connection.uid("search", None, program)  # type: ignore[arg-type]
        if status != "OK":
            raise ImapOperationError(f"UID SEARCH {program} failed")
        blobs = [chunk for chunk in data if isinstance(chunk, bytes)]
        uids: list[int] = []
        for chunk in blobs:
            uids.extend(int(token) for token in chunk.split() if token.isdigit())
        return sorted(set(uids))

    def fetch(self, uids: Iterable[int], *, headers_only: bool = True) -> list[MessageHead]:
        items = ",".join(str(uid) for uid in uids)
        if not items:
            return []
        part = "(RFC822.HEADER)" if headers_only else "(RFC822)"
        status, data = self._connection.uid("fetch", items, part)
        if status != "OK":
            raise ImapOperationError(f"UID FETCH {items} failed")
        return [head for head in (self._parse_fetch(entry) for entry in data) if head is not None]

    def append(self, folder: str, message: bytes, *, flags: str = "\\Draft") -> int:
        """``APPEND`` a raw RFC822 message; returns the server-assigned UIDVALIDITY-agnostic UID if reported."""
        status, data = self._connection.append(_quote(folder), flags, None, message)
        if status != "OK":
            raise ImapOperationError(f"APPEND to {folder!r} failed: {data!r}")
        return _uid_from_append(data)

    @staticmethod
    def _parse_fetch(entry: object) -> MessageHead | None:
        if not isinstance(entry, tuple):
            return None
        header_blob = entry[0]
        raw = entry[1]
        if not isinstance(header_blob, bytes) or not isinstance(raw, bytes):
            return None
        uid_match = re.search(rb"UID (\d+)", header_blob)
        if uid_match is None:
            return None
        return MessageHead(uid=int(uid_match.group(1)), raw=raw)


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _uid_from_append(data: Sequence[object]) -> int:
    for entry in data:
        if not isinstance(entry, bytes):
            continue
        match = re.search(rb"APPENDUID \d+ (\d+)", entry)
        if match:
            return int(match.group(1))
    return 0
