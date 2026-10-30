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
    ROLLUP_MARKER,
    RollupEntry,
    build_entry,
    build_new_rollup_body,
    find_rollup_index,
    insert_entries_by_date,
    is_canonical_rollup_body,
    is_rollup_body,
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
    body = build_new_rollup_body(entry, "airflow-s")
    assert body.startswith(f"{ROLLUP_MARKER}\n")
    assert ROLLUP_MARKER == "<!-- apache-magpie: status-rollup v1 -->"
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


def _rollup(*dates: str) -> str:
    body = f"{MARKER_LINE}\n" + build_entry(date=dates[0], user="@a", action="Step", body=dates[0])
    for d in dates[1:]:
        body = rebuild_with_appended_entry(body, build_entry(date=d, user="@a", action="Step", body=d))
    return body


def _entry(date: str) -> RollupEntry:
    return RollupEntry(date=date, user="@c", action="Old", body=f"old {date}")


def test_insert_entries_by_date_keeps_the_latest_entry_last():
    out = insert_entries_by_date(
        _rollup("2026-01-01", "2026-03-01"), [_entry("2026-04-01"), _entry("2026-02-01")]
    )
    assert [e.date for e in iter_entries(out)] == ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    assert "</details>\n\n---\n\n<details>" in out


def test_insert_entries_by_date_before_the_first_entry():
    existing = _rollup("2026-05-01")
    out = insert_entries_by_date(existing, [_entry("2026-01-01")])
    assert [e.date for e in iter_entries(out)] == ["2026-01-01", "2026-05-01"]
    # The existing entry's text is untouched.
    assert existing.split("\n", 1)[1] in out


def test_insert_entries_by_date_keeps_a_same_day_existing_entry_last():
    out = insert_entries_by_date(_rollup("2026-01-01", "2026-03-01"), [_entry("2026-03-01")])
    entries = iter_entries(out)
    assert [e.date for e in entries] == ["2026-01-01", "2026-03-01", "2026-03-01"]
    assert entries[-1].action == "Step"


def test_insert_entries_by_date_ignores_summary_lines_inside_an_entry():
    example = "<details><summary>2025-12-01 · @x · Example</summary>\n\nquoted\n\n</details>"
    body = f"```\n{example}\n```"
    existing = f"{MARKER_LINE}\n" + build_entry(date="2026-01-01", user="@a", action="Step", body=body)
    out = insert_entries_by_date(existing, [_entry("2026-02-01")])
    # Appended after the January entry, not inside its quoted example.
    assert out.startswith(existing)
    assert out.endswith(build_entry(date="2026-02-01", user="@c", action="Old", body="old 2026-02-01"))


def test_insert_entries_by_date_skips_unparsed_anchors():
    existing = f"{MARKER_LINE}\n<details><summary>free text</summary>\n\nX.\n\n</details>"
    out = insert_entries_by_date(existing, [_entry("2026-01-01")])
    assert [e.action for e in iter_entries(out)] == ["", "Old"]


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
    existing = build_new_rollup_body(
        build_entry(date="2026-05-01", user="@a", action="x1", body="b1"), "airflow-s"
    )
    for i, action in enumerate(["x2", "x3"], start=2):
        existing = rebuild_with_appended_entry(
            existing,
            build_entry(date=f"2026-05-0{i}", user="@a", action=action, body=f"b{i}"),
        )
    assert [e.action for e in iter_entries(existing)] == ["x1", "x2", "x3"]


# ---------------------------------------------------------------------------
# marker detection: canonical first, legacy still recognised
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "canonical", "rollup"),
    [
        ("<!-- apache-magpie: status-rollup v1 -->\n<details>", True, True),
        ("<!-- apache-magpie: status-rollup v2 -->", True, True),
        (f"{MARKER_LINE}\n<details>", False, True),
        ("<!-- acme-security status rollup v1 — x -->", False, True),
        ("<!-- apache-magpie: release-manager-handoff v1 -->", False, False),
        ("<!-- apache-magpie: status-rollup-x v1 -->", False, False),
        ("quoted <!-- apache-magpie: status-rollup v1 -->", False, False),
        ("", False, False),
    ],
)
def test_marker_detection(body, canonical, rollup):
    assert is_canonical_rollup_body(body) is canonical
    assert is_rollup_body(body) is rollup


def test_find_rollup_index_prefers_canonical_then_first_legacy():
    canonical = f"{ROLLUP_MARKER}\n<details><summary>2026-05-28 · @a · Import</summary>\n\nA.\n\n</details>"
    legacy = f"{MARKER_LINE}\n<details><summary>2026-05-28 · @a · Import</summary>\n\nA.\n\n</details>"
    assert find_rollup_index(["hi", legacy, canonical]) == 2
    assert find_rollup_index(["hi", legacy, legacy]) == 1
    assert find_rollup_index(["hi"]) is None


def test_find_rollup_index_skips_marker_comments_by_untrusted_authors():
    canonical = f"{ROLLUP_MARKER}\n<details><summary>2026-05-28 · @a · Import</summary>\n\nA.\n\n</details>"
    legacy = f"{MARKER_LINE}\n<details><summary>2026-05-28 · @a · Import</summary>\n\nA.\n\n</details>"
    bodies = ["hi", canonical, legacy, canonical]
    authors = ["outsider", "outsider", "Alice", "bob"]
    # Untrusted canonical decoy at 1 is skipped; trusted canonical at 3 wins over legacy at 2.
    assert find_rollup_index(bodies, authors, {"alice", "bob"}) == 3
    assert find_rollup_index(bodies, authors, {"alice"}) == 2
    assert find_rollup_index(bodies, authors, set()) is None
    assert find_rollup_index([canonical], [""], {"alice"}) is None
    # Without a trusted set the author is not consulted.
    assert find_rollup_index(bodies) == 1


def test_find_rollup_index_requires_one_author_per_body_when_filtering():
    with pytest.raises(ValueError):
        find_rollup_index(["a", "b"], ["x"], {"x"})


def test_iter_entries_skips_the_canonical_marker_line():
    body = f"{ROLLUP_MARKER}\n<details><summary>2026-05-28 · @a · Import</summary>\n\nA.\n\n</details>"
    assert [(e.action, e.body) for e in iter_entries(body)] == [("Import", "A.")]
