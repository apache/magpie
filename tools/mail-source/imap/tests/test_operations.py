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
"""Operation tests against the fake IMAP backend."""

from __future__ import annotations

import pytest

from conftest import FakeMailbox, build_message, make_config
from imap_source.cli import CapabilityDeclined
from imap_source.list_drafts import list_drafts
from imap_source.list_recent_threads import list_recent_threads
from imap_source.list_sent_since import list_sent_since
from imap_source.read_thread import read_thread

ROOT = "<report-1@lists.example.org>"
REPLY = "<reply-1a@example.org>"
FOLLOWUP = "<reply-1b@example.org>"
UNRELATED = "<other-thread@lists.example.org>"


def seeded_box() -> FakeMailbox:
    return FakeMailbox.seed(
        **{
            "INBOX": [
                build_message(ROOT, "Bug report: connector crash", "dev@example.org"),
                build_message(
                    REPLY,
                    "Re: Bug report: connector crash",
                    "peer@example.org",
                    in_reply_to=ROOT,
                    references=ROOT,
                    date="Tue, 22 Sep 2026 09:00:00 +0000",
                ),
                build_message(UNRELATED, "Lunch plans", "friend@example.org"),
            ],
            "Sent": [
                build_message(
                    FOLLOWUP,
                    "Re: Bug report: connector crash",
                    "security-triage@example.org",
                    in_reply_to=ROOT,
                    references=f"{ROOT} {REPLY}",
                    date="Wed, 23 Sep 2026 08:00:00 +0000",
                ),
            ],
            "Drafts": [
                build_message(
                    "<draft-1@example.org>",
                    "Re: Bug report: connector crash",
                    "security-triage@example.org",
                    in_reply_to=ROOT,
                ),
            ],
        }
    )


def test_list_recent_threads_groups_by_root_message_id() -> None:
    config = make_config()
    box = seeded_box()
    threads = list_recent_threads(box, config, since_days=90)
    assert len(threads) == 2
    report = next(t for t in threads if t["thread_id"] == ROOT)
    assert report["message_count"] == 2
    assert report["uids"] == [1, 2]
    assert report["subject"].startswith("Bug report")


def test_read_thread_returns_chronological_history() -> None:
    config = make_config()
    box = seeded_box()
    result = read_thread(box, config, ROOT, since_days=90)
    assert result["message_count"] == 2
    assert [m["message_id"] for m in result["messages"]] == [ROOT, REPLY]
    assert all("body_raw" not in m for m in result["messages"])


def test_read_thread_declares_missing_root() -> None:
    config = make_config()
    box = seeded_box()
    with pytest.raises(SystemExit):
        read_thread(box, config, "<ghost@x>", since_days=90)


def test_list_sent_since_matches_on_thread_chain() -> None:
    config = make_config()
    box = seeded_box()
    sent = list_sent_since(box, config, ROOT, since_days=90)
    assert [s["message_id"] for s in sent] == [FOLLOWUP]


def test_list_sent_since_declines_without_sent_folder() -> None:
    config = make_config(sent_folder=None)
    box = seeded_box()
    with pytest.raises(CapabilityDeclined):
        list_sent_since(box, config, ROOT, since_days=90)


def test_list_drafts_is_the_idempotency_check() -> None:
    config = make_config()
    box = seeded_box()
    drafts = list_drafts(box, config, ROOT, since_days=90)
    assert [d["message_id"] for d in drafts] == ["<draft-1@example.org>"]


def test_list_drafts_declines_when_folder_is_declared_off() -> None:
    config = make_config(drafts_folder=None)
    box = seeded_box()
    with pytest.raises(CapabilityDeclined):
        list_drafts(box, config, ROOT, since_days=90)


def test_list_drafts_declines_when_folder_is_missing_on_server() -> None:
    config = make_config(drafts_folder="Shared Drafts")
    box = seeded_box()
    with pytest.raises(CapabilityDeclined):
        list_drafts(box, config, ROOT, since_days=90)
