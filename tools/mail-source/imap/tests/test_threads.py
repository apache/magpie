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
"""Threading canonicalisation tests — thread_id_kind: rfc5322-message-id."""

from __future__ import annotations

from conftest import build_message
from imap_source.searching import parse_message
from imap_source.threads import draft_subject, normalise_message_id, summarise

ROOT = "<report-1@lists.example.org>"
REPLY = "<reply-1a@example.org>"


def test_normalise_message_id_extracts_single_token() -> None:
    assert normalise_message_id("<a@b> (was: <c@d>)") == "<a@b>"
    assert normalise_message_id("  <x@y>  ") == "<x@y>"
    assert normalise_message_id(None) is None
    assert normalise_message_id("not-a-message-id") is None


def test_summarise_walks_references_chain() -> None:
    raw = build_message(REPLY, "Re: report", "dev@example.org", references=f"{ROOT} <mid-2@x>")
    position = summarise(parse_message(raw))
    assert position.message_id == REPLY
    assert position.references == (ROOT, "<mid-2@x>")
    assert position.references_thread(ROOT)
    assert not position.references_thread("<unrelated@x>")


def test_in_reply_to_alone_reaches_the_root() -> None:
    raw = build_message(REPLY, "Re: report", "dev@example.org", in_reply_to=ROOT)
    position = summarise(parse_message(raw))
    assert position.references_thread(ROOT)


def test_summarise_survives_malformed_dates_and_from() -> None:
    raw = build_message(ROOT, "report", "not-an-address", date="not a date")
    position = summarise(parse_message(raw))
    assert position.date is None
    assert position.from_address == "not-an-address"


def test_draft_subject_collapses_existing_reply_prefixes() -> None:
    assert draft_subject("Re: Re[2]: FWD: report") == "Re: report"
    assert draft_subject("report") == "Re: report"
    assert draft_subject("") == "Re: (no subject)"
