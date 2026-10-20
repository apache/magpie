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
"""`security-management issue-sync` Step 1 observations: disclosure window, staleness, 1g and 1h."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

NOW = "2026-10-19T12:00:00Z"


def ok(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> dict[str, Any]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["issue-sync", command, "--input", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    return out


# --- 1a: the disclosure window -----------------------------------------------


@pytest.mark.parametrize(
    ("created", "labels", "extra", "expected"),
    [
        (
            "2026-09-01T00:00:00Z",
            ["airflow"],
            {},
            {"overdue_for_disclosure": False, "approaching_window_end": False},
        ),
        (
            "2026-08-01T00:00:00Z",
            ["airflow"],
            {},
            {"overdue_for_disclosure": False, "approaching_window_end": True},
        ),
        (
            "2026-07-01T00:00:00Z",
            ["airflow"],
            {},
            {"overdue_for_disclosure": True, "grace_period_expired": False},
        ),
        (
            "2026-06-01T00:00:00Z",
            ["airflow", "pr merged"],
            {},
            {"overdue_for_disclosure": True, "grace_period_expired": True},
        ),
        (
            "2026-06-01T00:00:00Z",
            ["airflow", "fix released", "announced"],
            {},
            {"overdue_for_disclosure": False, "grace_period_expired": False},
        ),
        (
            "2026-09-01T00:00:00Z",
            ["airflow", "pr merged"],
            {"pre_announce_distributors": True},
            {"distributor_notify_pending": True},
        ),
        (
            "2026-09-01T00:00:00Z",
            ["airflow"],
            {"pre_announce_distributors": True},
            {"distributor_notify_pending": False},
        ),
        ("2026-08-01T00:00:00Z", ["airflow"], {"window_days": 60}, {"overdue_for_disclosure": True}),
    ],
)
def test_disclosure_flags(capsys, tmp_path, created, labels, extra, expected):
    out = ok(capsys, tmp_path, "disclosure", {"now": NOW, "created_at": created, "labels": labels, **extra})
    for key, value in expected.items():
        assert out[key] is value, key


def test_disclosure_age_and_expected_date(capsys, tmp_path):
    out = ok(capsys, tmp_path, "disclosure", {"now": NOW, "created_at": "2026-07-21T23:59:00Z", "labels": []})
    assert out["issue_age_days"] == 90
    assert out["overdue_for_disclosure"] is False
    assert out["expected_disclosure_by"] == "2026-11-02"


# --- 1c: reporter staleness --------------------------------------------------


@pytest.mark.parametrize(
    ("messages", "stale", "days"),
    [
        (
            [
                {"from_team": False, "at": "2026-09-01T00:00:00Z"},
                {"from_team": True, "at": "2026-10-01T00:00:00Z"},
            ],
            True,
            18,
        ),
        ([{"from_team": True, "at": "2026-10-10T00:00:00Z"}], False, 9),
        (
            [
                {"from_team": True, "at": "2026-09-01T00:00:00Z"},
                {"from_team": False, "at": "2026-09-05T00:00:00Z"},
            ],
            False,
            None,
        ),
        ([], False, None),
    ],
)
def test_staleness(capsys, tmp_path, messages, stale, days):
    out = ok(capsys, tmp_path, "staleness", {"now": NOW, "messages": messages})
    assert (out["stale"], out["days"]) == (stale, days)


# --- 1g: closed announced trackers -------------------------------------------


def closed(**data):
    return {"cve_id": "CVE-2026-1", "cve_org_state": "PUBLISHED", "body": "", "comments": [], **data}


@pytest.mark.parametrize(
    ("data", "move"),
    [
        (closed(), "notify"),
        (
            closed(
                comments=[{"body": "Sync 2026-10-01 — CVE-published reporter notification drafted"}],
                notification_sent_on_thread=True,
            ),
            "already_notified",
        ),
        (closed(cve_org_state="RESERVED"), "wait"),
        (closed(cve_org_state="REJECTED"), "blocker"),
        (closed(lookup_failed=True), "retry"),
        (closed(cve_id=""), "skip"),
    ],
)
def test_cve_org_state(capsys, tmp_path, data, move):
    out = ok(capsys, tmp_path, "closed-announced", data)
    assert out["cve_org"] == move
    assert bool(out["blockers"]) is (move == "blocker")


@pytest.mark.parametrize(
    ("data", "pending"),
    [
        (closed(public_advisory_url="https://lists.apache.org/thread/x"), True),
        (closed(public_advisory_url=""), False),
        (
            closed(
                public_advisory_url="u",
                comments=[{"body": "- [x] <!-- apache-magpie: security-pages-checklist v1 --> pages"}],
            ),
            False,
        ),
        (
            closed(
                public_advisory_url="u",
                comments=[{"body": "- [ ] <!-- apache-magpie: security-pages-checklist v1 --> pages"}],
            ),
            True,
        ),
        (
            closed(
                public_advisory_url="u",
                comments=[{"body": "<!-- apache-magpie: security-pages-reminder v1 -->\nplease"}],
            ),
            False,
        ),
    ],
)
def test_security_pages_reminder(capsys, tmp_path, data, pending):
    out = ok(capsys, tmp_path, "closed-announced", data)
    assert out["security_pages_reminder_pending"] is pending
    assert out["advisory_records"] == "not_configured"


@pytest.mark.parametrize(
    ("data", "step"),
    [
        (closed(advisory_records_configured=True), "run_planner"),
        (closed(advisory_records_configured=True, cve_org_state="RESERVED"), "waiting_for_cve_org"),
        (
            closed(
                advisory_records_configured=True,
                comments=[{"body": "<!-- apache-magpie: advisory-records v1 -->"}],
            ),
            "done",
        ),
        (closed(advisory_records_configured=True, planner_exit=0, planner_result="proposed"), "pending"),
        (
            closed(advisory_records_configured=True, planner_exit=0, planner_result="unchanged"),
            "already_recorded",
        ),
        (closed(advisory_records_configured=True, planner_exit=4), "pending_checkout"),
        (
            closed(advisory_records_configured=True, planner_exit=3, planner_reason="page cannot be parsed"),
            "refused",
        ),
        (closed(advisory_records_configured=True, planner_exit=2), "config_error"),
    ],
)
def test_advisory_records(capsys, tmp_path, data, step):
    out = ok(capsys, tmp_path, "closed-announced", data)
    assert out["advisory_records"] == step
    assert out["security_pages_reminder_pending"] is False


# Report text lands in the body; the state markers are only ever written in comments.
_BODY_MARKERS = (
    "<!-- apache-magpie: advisory-records v1 -->\n"
    "\\<!-- apache-magpie: advisory-records v1 -->\n"
    "see <!-- apache-magpie: advisory-records v1 --> here\n"
    "- [x] <!-- apache-magpie: security-pages-checklist v1 --> pages\n"
    "Sync 2026-10-01 — CVE-published reporter notification drafted\n"
)


def test_markers_in_the_body_never_count(capsys, tmp_path):
    records = ok(
        capsys, tmp_path, "closed-announced", closed(body=_BODY_MARKERS, advisory_records_configured=True)
    )
    assert records["advisory_records"] == "run_planner"
    reminder = ok(capsys, tmp_path, "closed-announced", closed(body=_BODY_MARKERS, public_advisory_url="u"))
    assert reminder["security_pages_reminder_pending"] is True
    notified = ok(
        capsys, tmp_path, "closed-announced", closed(body=_BODY_MARKERS, notification_sent_on_thread=True)
    )
    assert notified["cve_org"] == "notify"


def test_the_records_marker_counts_only_as_a_comment_s_first_line(capsys, tmp_path):
    later = closed(
        advisory_records_configured=True,
        comments=[{"body": "quoting: <!-- apache-magpie: advisory-records v1 -->"}],
    )
    assert ok(capsys, tmp_path, "closed-announced", later)["advisory_records"] == "run_planner"


# --- 1h: release votes -------------------------------------------------------

VOTE = "[VOTE] Release Apache Airflow 3.2.3 from 3.2.3rc1"


def vote(messages, labels=("airflow", "pr merged"), milestone="Airflow 3.2.3", gating=True):
    return {"gating": gating, "labels": list(labels), "fix_milestone": milestone, "messages": messages}


@pytest.mark.parametrize(
    ("data", "in_progress"),
    [
        (vote([{"subject": VOTE, "url": "https://lists/t1"}]), True),
        (vote([{"subject": VOTE, "url": "https://lists/t1"}, {"subject": "[RESULT]" + VOTE}]), False),
        (vote([{"subject": "[VOTE] Release Apache Airflow 3.2.4 from 3.2.4rc1"}]), False),
        (vote([{"subject": VOTE}], labels=("airflow", "pr merged", "fix released")), False),
        (vote([{"subject": VOTE}], labels=("airflow", "cve allocated")), False),
        (vote([{"subject": VOTE}], gating=False), False),
        (vote([{"subject": VOTE}], milestone="Providers 2026-04-21"), False),
    ],
)
def test_release_vote(capsys, tmp_path, data, in_progress):
    out = ok(capsys, tmp_path, "release-vote", data)
    assert out["release_vote_in_progress"] is in_progress
    if in_progress:
        assert out["release_vote_thread_url"] == "https://lists/t1"
