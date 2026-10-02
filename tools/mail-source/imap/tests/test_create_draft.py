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
"""``create_draft`` tests — drafts only, never sends; threading headers per the shared rule."""

from __future__ import annotations

import email

import pytest

from conftest import FakeMailbox, build_message, make_config
from imap_source.cli import CapabilityDeclined
from imap_source.create_draft import create_draft
from imap_source.searching import parse_message

ROOT = "<report-1@lists.example.org>"
REPLY = "<reply-1a@example.org>"


def box_with_thread() -> FakeMailbox:
    return FakeMailbox.seed(
        **{
            "INBOX": [
                build_message(ROOT, "Re[2]: Bug report", "dev@example.org"),
                build_message(
                    REPLY,
                    "Re: Bug report",
                    "peer@example.org",
                    in_reply_to=ROOT,
                    references=ROOT,
                    date="Tue, 22 Sep 2026 09:00:00 +0000",
                ),
            ],
            "Drafts": [],
        }
    )


def test_create_draft_appends_thread_attached_draft_and_never_sends() -> None:
    config = make_config()
    box = box_with_thread()
    result = create_draft(
        box,
        config,
        ROOT,
        body="thanks for the report\n",
        to=["dev@example.org"],
        cc=["security@example.org"],
        from_address="security-triage@example.org",
    )
    assert result["sent"] is False
    assert result["drafts_folder"] == "Drafts"
    stored = box.folders["Drafts"][result["draft_uid"]]
    parsed = parse_message(stored)
    assert parsed["Subject"] == "Re: Bug report"  # inherited, reply prefixes collapsed
    assert parsed["In-Reply-To"] == REPLY  # attaches to the chronologically last message
    assert parsed["References"] == f"{ROOT} {REPLY}"  # chain + parent, deduplicated
    assert parsed["To"] == "dev@example.org"
    assert parsed["Cc"] == "security@example.org"
    assert "thanks for the report" in parsed.get_payload()


def test_create_draft_defaults_to_the_reporter_address() -> None:
    config = make_config()
    box = box_with_thread()
    create_draft(box, config, ROOT, body="x", to=[], cc=[], from_address=None)
    stored = box.folders["Drafts"][1]
    parsed = email.message_from_bytes(stored)
    assert parsed["To"] == "dev@example.org"


def test_create_draft_declines_without_drafts_folder() -> None:
    config = make_config(drafts_folder=None)
    box = box_with_thread()
    with pytest.raises(CapabilityDeclined):
        create_draft(box, config, ROOT, body="x", to=[], cc=[], from_address=None)


def test_create_draft_declines_when_server_refuses_append() -> None:
    def refuse_append(folder: str, message: bytes, *, flags: str = "\\Draft") -> int:
        raise PermissionError("INSERT denied")

    config = make_config()
    box = box_with_thread()
    box.append = refuse_append  # type: ignore[method-assign]
    with pytest.raises(CapabilityDeclined):
        create_draft(box, config, ROOT, body="x", to=["dev@example.org"], cc=[], from_address=None)
