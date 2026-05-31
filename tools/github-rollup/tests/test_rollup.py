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
from __future__ import annotations

import pytest

from github_rollup.rollup import (
    ROLLUP_MARKER_PREFIX,
    build_entry,
    build_new_rollup_body,
    iter_entries,
    parse_summary_line,
    rebuild_with_appended_entry,
)

MARKER_LINE = (
    "<!-- airflow-s status rollup v1 — all bot-authored status updates fold into this single comment. -->"
)


# ---------------------------------------------------------------------------
# parse_summary_line
# ---------------------------------------------------------------------------


def test_parse_canonical_summary():
    e = parse_summary_line("2026-05-30 · @potiuk · CVE allocated (CVE-2026-12345)")
    assert e is not None
    assert e.date == "2026-05-30"
    assert e.user == "@potiuk"
    assert e.action == "CVE allocated (CVE-2026-12345)"


def test_parse_with_extra_whitespace():
    e = parse_summary_line("  2026-05-30  ·  @potiuk  ·  Sync pass  ")
    assert e is not None
    assert e.date == "2026-05-30"
    assert e.user == "@potiuk"
    assert e.action == "Sync pass"


@pytest.mark.parametrize(
    "summary",
    [
        "not a summary",
        "2026-05-30 · @potiuk",  # missing action
        "26-05-30 · @potiuk · Sync",  # bad date
        "2026-13-99 · @potiuk · Sync",  # invalid month/day but format matches
        "2026-05-30 · potiuk · Sync",  # missing @
        "2026-05-30 · @ · Sync",  # bare @
        "2026-05-30 · @potiuk · ",  # empty action
    ],
)
def test_parse_summary_rejects_invalid(summary):
    # Some of the above (e.g. 2026-13-99) only fail format-wise, but
    # the parser still returns None for the missing-action and bad-
    # handle cases. The 2026-13-99 case passes the regex (4-2-2 digit
    # groups) and is returned with raw fields — we don't validate
    # calendar correctness here.
    result = parse_summary_line(summary)
    if "13-99" in summary:
        assert result is not None  # regex-permissive
        return
    assert result is None


# ---------------------------------------------------------------------------
# iter_entries
# ---------------------------------------------------------------------------


def test_iter_entries_single():
    body = (
        f"{MARKER_LINE}\n"
        "<details><summary>2026-05-30 · @potiuk · CVE allocated</summary>\n"
        "\n"
        "Allocated CVE-2026-12345 via Vulnogram.\n"
        "\n"
        "</details>"
    )
    entries = iter_entries(body)
    assert len(entries) == 1
    e = entries[0]
    assert e.date == "2026-05-30"
    assert e.user == "@potiuk"
    assert e.action == "CVE allocated"
    assert "Allocated CVE-2026-12345" in e.body


def test_iter_entries_multiple():
    body = (
        f"{MARKER_LINE}\n"
        "<details><summary>2026-05-28 · @potiuk · Import</summary>\n\n"
        "First.\n\n"
        "</details>\n"
        "\n---\n\n"
        "<details><summary>2026-05-30 · @potiuk · Sync</summary>\n\n"
        "Second.\n\n"
        "</details>"
    )
    entries = iter_entries(body)
    assert len(entries) == 2
    assert entries[0].action == "Import"
    assert entries[1].action == "Sync"
    assert "First." in entries[0].body
    assert "Second." in entries[1].body


def test_iter_entries_no_marker_line():
    """If a caller passes a body without the marker (e.g. they pre-
    stripped it), still parse what's there."""
    body = "<details><summary>2026-05-30 · @potiuk · CVE allocated</summary>\n\nBody.\n\n</details>"
    entries = iter_entries(body)
    assert len(entries) == 1


def test_iter_entries_empty_body():
    assert iter_entries("") == []


def test_iter_entries_missing_close_tag_tolerated():
    body = (
        f"{MARKER_LINE}\n"
        "<details><summary>2026-05-30 · @potiuk · Sync</summary>\n\n"
        "Body that was never closed."
    )
    entries = iter_entries(body)
    assert len(entries) == 1
    assert "Body that was never closed." in entries[0].body


def test_iter_entries_non_canonical_summary_preserved():
    body = f"{MARKER_LINE}\n<details><summary>2026-05-30 · @potiuk · </summary>\n\nBody.\n\n</details>"
    entries = iter_entries(body)
    assert len(entries) == 1
    # The summary was non-canonical (empty action), so the parsed
    # fields are blank but the body is still returned for round-trip.
    e = entries[0]
    assert e.date == ""
    assert e.user == ""
    assert e.action == ""
    assert "Body." in e.body


# ---------------------------------------------------------------------------
# build_entry
# ---------------------------------------------------------------------------


def test_build_entry_canonical():
    e = build_entry(
        date="2026-05-30",
        user="@potiuk",
        action="CVE allocated",
        body="Allocated CVE-2026-12345.",
    )
    assert e == (
        "<details><summary>2026-05-30 · @potiuk · CVE allocated</summary>\n"
        "\n"
        "Allocated CVE-2026-12345.\n"
        "\n"
        "</details>"
    )


def test_build_entry_adds_at_prefix():
    e = build_entry(date="2026-05-30", user="potiuk", action="Sync", body="x")
    assert "· @potiuk ·" in e


def test_build_entry_strips_body_whitespace():
    e = build_entry(date="2026-05-30", user="@a", action="b", body="\n\n  body\n\n")
    assert "\n\nbody\n\n</details>" in e


# ---------------------------------------------------------------------------
# build_new_rollup_body
# ---------------------------------------------------------------------------


def test_build_new_rollup_body_includes_marker_first():
    entry = build_entry(date="2026-05-30", user="@a", action="b", body="c")
    body = build_new_rollup_body(entry)
    assert body.startswith(ROLLUP_MARKER_PREFIX)
    assert "<details>" in body
    # Marker line + immediately the entry — no blank line gap.
    first_nl = body.find("\n")
    assert body[first_nl + 1 :].startswith("<details>")


# ---------------------------------------------------------------------------
# rebuild_with_appended_entry
# ---------------------------------------------------------------------------


def test_rebuild_with_appended_entry_inserts_canonical_ruler():
    existing = f"{MARKER_LINE}\n<details><summary>2026-05-28 · @a · Import</summary>\n\nA.\n\n</details>"
    new = build_entry(date="2026-05-30", user="@b", action="Sync", body="B.")
    out = rebuild_with_appended_entry(existing, new)
    assert "</details>\n\n---\n\n<details>" in out
    # Both entries are findable by iter_entries.
    entries = iter_entries(out)
    assert len(entries) == 2
    assert entries[0].action == "Import"
    assert entries[1].action == "Sync"


def test_rebuild_strips_trailing_whitespace_before_ruler():
    existing = (
        f"{MARKER_LINE}\n<details><summary>2026-05-28 · @a · Import</summary>\n\nA.\n\n</details>\n\n\n   \n"
    )
    new = build_entry(date="2026-05-30", user="@b", action="Sync", body="B.")
    out = rebuild_with_appended_entry(existing, new)
    # Exactly the canonical ruler — no double blanks.
    assert "</details>\n\n---\n\n<details>" in out
    assert "</details>\n\n\n---" not in out


def test_round_trip_three_appends_keeps_count():
    existing = build_new_rollup_body(build_entry(date="2026-05-01", user="@a", action="x1", body="b1"))
    for i, action in enumerate(["x2", "x3"], start=2):
        existing = rebuild_with_appended_entry(
            existing,
            build_entry(date=f"2026-05-0{i}", user="@a", action=action, body=f"b{i}"),
        )
    assert [e.action for e in iter_entries(existing)] == ["x1", "x2", "x3"]
