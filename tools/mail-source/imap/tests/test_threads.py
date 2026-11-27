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

import base64

import pytest

from conftest import build_message
from imap_source.searching import Message, parse_message, thread_root_of
from imap_source.threads import (
    canonical_thread_id,
    decode_subject,
    draft_subject,
    normalise_message_id,
    summarise,
)

ROOT = "<report-1@lists.example.org>"
REPLY = "<reply-1a@example.org>"


def test_normalise_message_id_extracts_single_token() -> None:
    assert normalise_message_id("<a@b> (was: <c@d>)") == "<a@b>"
    assert normalise_message_id("  <x@y>  ") == "<x@y>"
    assert normalise_message_id(None) is None
    assert normalise_message_id("not-a-message-id") is None


def test_canonical_thread_id_accepts_bare_or_bracketed_form() -> None:
    assert canonical_thread_id("<a@b>") == "<a@b>"
    assert canonical_thread_id("  a@b  ") == "<a@b>"
    assert canonical_thread_id(None) is None
    assert canonical_thread_id("not-a-message-id") is None


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


def _thread_root(raw: bytes) -> str | None:
    return thread_root_of(Message(uid=1, position=summarise(parse_message(raw)), raw_headers=raw))


def test_thread_root_takes_the_in_reply_to_step() -> None:
    """A reply carrying only In-Reply-To is keyed on its parent, as maildir keys it."""
    raw = build_message(REPLY, "Re: report", "dev@example.org", in_reply_to=ROOT)
    assert _thread_root(raw) == ROOT


def test_thread_root_prefers_references_over_in_reply_to() -> None:
    raw = build_message(
        REPLY,
        "Re: report",
        "dev@example.org",
        references=f"{ROOT} <mid@example.org>",
        in_reply_to="<mid@example.org>",
    )
    assert _thread_root(raw) == ROOT


def test_thread_root_ignores_a_comment_beside_the_id() -> None:
    """RFC 5322 allows `In-Reply-To: (was: report) <r@h>`; the comment is not a root."""
    raw = build_message(REPLY, "Re: report", "dev@example.org", in_reply_to=f"(was: report) {ROOT}")
    assert _thread_root(raw) == ROOT


def test_summarise_survives_malformed_dates_and_from() -> None:
    raw = build_message(ROOT, "report", "not-an-address", date="not a date")
    position = summarise(parse_message(raw))
    assert position.date is None
    assert position.from_address == "not-an-address"


def test_draft_subject_collapses_existing_reply_prefixes() -> None:
    assert draft_subject("Re: Re[2]: FWD: report") == "Re: report"
    assert draft_subject("report") == "Re: report"
    assert draft_subject("") == "Re: (no subject)"


def _with_subject(subject_line: str) -> bytes:
    return (
        f"Message-ID: {ROOT}\r\nFrom: reporter@example.org\r\n{subject_line}\r\n"
        "Date: Mon, 23 Nov 2026 12:00:00 +0000\r\n\r\nbody\r\n"
    ).encode()


def test_summarise_decodes_an_encoded_subject() -> None:
    raw = _with_subject("Subject: =?utf-8?q?=5BSECURITY=5D_Z=C3=BCrich_RCE?=")
    assert summarise(parse_message(raw)).subject == "[SECURITY] Z\u00fcrich RCE"


def test_summarise_unfolds_a_folded_subject() -> None:
    raw = _with_subject("Subject: [SECURITY] a long report subject\r\n that a client folded")
    assert summarise(parse_message(raw)).subject == "[SECURITY] a long report subject that a client folded"


@pytest.mark.parametrize("charset", ["shift_jis", "euc-jp", "utf-8"])
def test_decode_subject_keeps_half_width_katakana(charset: str) -> None:
    # make_header() re-encodes Japanese charsets as ISO-2022-JP, which has no
    # half-width katakana, so these subjects used to raise UnicodeEncodeError.
    text = "[SECURITY] \uff76\uff80\uff76\uff85 RCE"
    encoded = f"=?{charset}?b?{base64.b64encode(text.encode(charset)).decode()}?="
    assert decode_subject(encoded) == text


def test_decode_subject_keeps_spacing_around_encoded_words() -> None:
    assert decode_subject("Re: =?utf-8?q?Z=C3=BCrich?= and more") == "Re: Z\u00fcrich and more"
    assert decode_subject("=?utf-8?q?a?= =?utf-8?q?b?=") == "ab"


def test_decode_subject_keeps_undecodable_bytes_as_raw_text() -> None:
    assert decode_subject("=?utf-8?b?/w==?=") == "=?utf-8?b?/w==?="


def test_decode_subject_keeps_a_raw_8bit_subject_with_an_encoded_word() -> None:
    # Decoding it would turn the raw characters into literal escapes.
    assert decode_subject("café =?utf-8?q?x?=") == "café =?utf-8?q?x?="
    assert decode_subject("=?utf-8?q?a?=中b") == "=?utf-8?q?a?=中b"
    assert "\\u" not in decode_subject("menu �� =?utf-8?q?x?=\r\n tail")


def test_decode_subject_keeps_undecodable_text() -> None:
    assert decode_subject("=?bogus-charset?q?x?=") == "=?bogus-charset?q?x?="
    assert decode_subject(None) == ""
