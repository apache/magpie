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
"""The shared readers of existing trackers: fields, threads, dispositions, selectors."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from security_management.shared import dispositions, fields, selectors, threads

TRACKER = "example-s/example-s"


def test_fields_read_values_absent_and_undecided():
    body = (
        "### The issue description\n\nx\n\n### Security mailing list thread\n\n_No response_\n\n"
        "### CWE\n\nCWE-79\n\n### CWE\n\nCWE-80\n"
    )
    out = fields.read(body, ["mailing_thread", "cwe", "severity"])
    assert out["values"] == {"mailing_thread": "", "severity": ""}
    assert out["absent"] == ["severity"]
    assert [u["role"] for u in out["undecided"]] == ["cwe"]


def test_fields_read_ignores_fenced_headings_and_refuses_containers():
    body = "### The issue description\n\n```\n### Severity\n\nCritical\n```\n\n### Severity\n\nLow\n"
    assert fields.read(body, ["severity"])["values"] == {"severity": "Low"}
    disputed = "### The issue description\n\n> ### Severity\n> Critical\n\n### Severity\n\nLow\n"
    assert fields.read(disputed, ["severity"])["undecided"]


@pytest.mark.parametrize(
    ("value", "path", "thread"),
    [
        ("https://lists.apache.org/thread/abc123xyz", "security_at_imported_public", None),
        (
            "No public archive URL — tracked privately on Gmail thread `18f3a2b9c1d4e507`.",
            "security_at_imported_gmail_only",
            "18f3a2b9c1d4e507",
        ),
        (
            "N/A — opened from public PR https://github.com/apache/airflow/pull/45210; no security@ thread",
            "pr_imported",
            None,
        ),
        ("N/A — imported from markdown file `audit.md`; no security@ thread.", "internal_audit", None),
        ("", "indeterminate", None),
        ("see the mail", "indeterminate", None),
    ],
)
def test_threads_classify(value, path, thread):
    out = threads.classify(value)
    assert out["import_path"] == path and out["thread_id"] == thread


def test_threads_primary_line_skips_relay_threads():
    value = (
        "No public archive URL — tracked privately on Gmail thread `19dc8d4675dfc1f1`.\n"
        "Root Message-ID: `<abc@example.com>`\n"
        "Aymane (huntr.com bounty `abdbcf11`-class duplicate, ASF-relayed by @apache/security): Gmail thread `19def0954b27ac31`."
    )
    out = threads.classify(value)
    assert out["thread_id"] == "19dc8d4675dfc1f1" and out["root_message_id"] == "<abc@example.com>"
    assert out["secondary_threads"][0]["thread_id"] == "19def0954b27ac31" and out["needs_decision"] is None
    both = "Relayed by GHSA: Gmail thread `aaaaaaaa1`.\nvia HackerOne: Gmail thread `bbbbbbbb2`."
    assert threads.classify(both)["needs_decision"]


def test_dispositions_markers_and_times():
    assert (
        dispositions.proposal_class("**Triage proposal**\n\nx\n\n**Proposed disposition: VALID.**\n")
        == "VALID"
    )
    assert dispositions.proposal_class("Quote: **Triage proposal**\n**Proposed disposition: VALID.**") is None
    assert dispositions.normalise_class("defense in depth") == "DEFENSE-IN-DEPTH"
    assert dispositions.normalise_class("UNCERTAIN") is None
    assert dispositions.parse_time("2026-10-01T10:00:00Z") == datetime(2026, 10, 1, 10, tzinfo=UTC)
    assert dispositions.parse_time(0) == datetime(1970, 1, 1, tzinfo=UTC)
    assert dispositions.parse_time("yesterday") is None


def test_selectors_issue_numbers():
    assert selectors.issue_numbers("#240", TRACKER) == [240]
    assert selectors.issue_numbers(f"{TRACKER}#240, https://github.com/{TRACKER}/issues/241", TRACKER) == [
        240,
        241,
    ]
    assert selectors.issue_numbers("#3 - #5, 4", TRACKER) == [3, 4, 5]
    for bad in ("other/repo#1", "#5-#3", "#1-#5000", "abc", ""):
        with pytest.raises(ValueError):
            selectors.issue_numbers(bad, TRACKER)
