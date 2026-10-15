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

"""Find drafts already waiting in a local Maildir.

The Maildir counterpart of the Gmail "detect drafts that already exist on a
thread" check: before a skill files a new reply, it asks whether a draft for
the same thread (or recipient, or subject) is already there, so it never
silently shadows one the human has not sent yet.

Read-only. It opens the Maildir without creating it and never changes,
moves, or flags a message.
"""

from __future__ import annotations

import argparse
import json
import mailbox
import re
import sys
from pathlib import Path
from typing import Any

_REPLY_PREFIX = re.compile(r"^\s*((re|fwd?|aw|sv)\s*:\s*)+", re.IGNORECASE)


def _normalise_subject(subject: str) -> str:
    return _REPLY_PREFIX.sub("", subject).strip().lower()


def _ids(header: str | None) -> set[str]:
    return set(re.findall(r"<[^<>\s]+>", header or ""))


def _wanted_ids(values: list[str]) -> set[str]:
    """Normalise caller-supplied Message-IDs: bracketed or bare, one or several per value."""
    wanted: set[str] = set()
    for value in values:
        for token in value.split():
            wanted |= _ids(token) or {f"<{token.strip('<>')}>"}
    return wanted


def find_drafts(
    maildir_path: str | Path,
    *,
    message_ids: list[str] | None = None,
    subject: str | None = None,
    to: str | None = None,
) -> list[dict[str, Any]]:
    """Return the drafts in ``maildir_path`` that match any given criterion.

    A message matches when its ``In-Reply-To`` or ``References`` names one of
    ``message_ids``, when its subject (reply prefixes stripped, case ignored)
    contains ``subject``, or when its ``To``/``Cc`` contains ``to``. With no
    criterion, every message in the Maildir is returned. A Maildir that does
    not exist yields no drafts rather than an error.
    """
    path = Path(maildir_path).expanduser()
    if not (path / "cur").is_dir() and not (path / "new").is_dir():
        return []

    wanted_ids = _wanted_ids(message_ids or [])
    # A subject that is only reply prefixes normalises to "" and would match every draft.
    wanted_subject = _normalise_subject(subject or "") or None
    wanted_to = to.lower() if to else None
    # A given subject is a criterion even when it normalises to nothing.
    any_criterion = bool(wanted_ids or subject or wanted_to)

    box = mailbox.Maildir(str(path), create=False)
    found: list[dict[str, Any]] = []
    for key, msg in box.iteritems():
        threading = _ids(msg.get("In-Reply-To")) | _ids(msg.get("References"))
        recipients = f"{msg.get('To', '')} {msg.get('Cc', '')}".lower()
        msg_subject = str(msg.get("Subject", ""))
        matched = not any_criterion or (
            bool(wanted_ids & threading)
            or (wanted_subject is not None and wanted_subject in _normalise_subject(msg_subject))
            or (wanted_to is not None and wanted_to in recipients)
        )
        if not matched:
            continue
        found.append(
            {
                "file": key,
                "subject": msg_subject,
                "to": str(msg.get("To", "")),
                "in_reply_to": str(msg.get("In-Reply-To", "")),
                "date": str(msg.get("Date", "")),
                "draft_flag": "D" in msg.get_flags(),
            }
        )
    found.sort(key=lambda d: d["file"])
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maildir-draft-find",
        description="List drafts already in a local Maildir that match a thread, subject or recipient (read-only).",
    )
    parser.add_argument("--maildir", required=True, help="Path to the Drafts Maildir to search.")
    parser.add_argument(
        "--message-id",
        action="extend",
        nargs="+",
        default=[],
        help="Message-IDs of the thread, with or without <>; several per flag, and the flag repeats. "
        "Matches a draft whose In-Reply-To or References names one.",
    )
    parser.add_argument(
        "--subject", default=None, help="Subject substring (reply prefixes and case ignored)."
    )
    parser.add_argument("--to", default=None, help="Recipient address substring, matched against To and Cc.")
    args = parser.parse_args(argv)

    json.dump(
        find_drafts(args.maildir, message_ids=args.message_id, subject=args.subject, to=args.to),
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
