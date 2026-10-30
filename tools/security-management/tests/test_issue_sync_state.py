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


@pytest.mark.parametrize(
    ("extra", "deadline", "expired"),
    [
        ({}, "2026-04-15", False),
        ({"grace_period_days": None}, "2026-04-15", False),
        ({"grace_period_days": 0}, "2026-04-01", True),
        ({"grace_period_days": "0"}, "2026-04-01", True),
        ({"grace_period_days": 1}, "2026-04-02", True),
        ({"grace_period_days": 14}, "2026-04-15", False),
        ({"window_days": None}, "2026-04-15", False),
        ({"window_days": 0}, "2026-04-15", False),
        ({"window_days": "0"}, "2026-04-15", False),
        ({"window_days": -1}, "2026-04-15", False),
        ({"window_days": 1}, "2026-01-16", True),
        ({"window_days": 90}, "2026-04-15", False),
    ],
)
def test_disclosure_configured_days(capsys, tmp_path, extra, deadline, expired):
    out = ok(
        capsys,
        tmp_path,
        "disclosure",
        {
            "now": "2026-04-05T12:00:00Z",
            "created_at": "2026-01-01T09:00:00Z",
            "labels": ["pr merged"],
            **extra,
        },
    )
    assert out["expected_disclosure_by"] == deadline
    assert out["overdue_for_disclosure"] is True
    assert out["grace_period_expired"] is expired


@pytest.mark.parametrize("shipping", ["pr merged", "fix released"])
@pytest.mark.parametrize(
    ("window", "now", "expired"),
    [
        (90, "2026-04-01T12:00:00Z", False),
        (90, "2026-04-02T12:00:00Z", True),
        (1, "2026-01-02T12:00:00Z", False),
        (1, "2026-01-03T12:00:00Z", True),
    ],
)
def test_zero_grace_period_preserves_day_boundary(capsys, tmp_path, shipping, window, now, expired):
    out = ok(
        capsys,
        tmp_path,
        "disclosure",
        {
            "now": now,
            "created_at": "2026-01-01T09:00:00Z",
            "labels": [shipping],
            "window_days": window,
            "grace_period_days": 0,
        },
    )
    assert out["overdue_for_disclosure"] is expired
    assert out["grace_period_expired"] is expired


@pytest.mark.parametrize(
    ("labels", "overdue"),
    [
        ([], True),
        (["pr merged", "announced"], False),
        (["fix released", "announced - emails sent"], False),
    ],
)
def test_zero_grace_period_preserves_label_guards(capsys, tmp_path, labels, overdue):
    out = ok(
        capsys,
        tmp_path,
        "disclosure",
        {
            "now": "2026-04-05T12:00:00Z",
            "created_at": "2026-01-01T09:00:00Z",
            "labels": labels,
            "grace_period_days": 0,
            "pre_announce_distributors": True,
        },
    )
    assert out["overdue_for_disclosure"] is overdue
    assert out["grace_period_expired"] is False
    assert out["distributor_notify_pending"] is False


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


@pytest.mark.parametrize(
    ("extra", "stale"),
    [
        ({}, False),
        ({"timeout_days": None}, False),
        ({"timeout_days": 0}, True),
        ({"timeout_days": "0"}, True),
        ({"timeout_days": 1}, False),
        ({"timeout_days": 14}, False),
    ],
)
def test_staleness_configured_timeout(capsys, tmp_path, extra, stale):
    out = ok(
        capsys,
        tmp_path,
        "staleness",
        {
            "now": "2026-04-05T12:00:00Z",
            "messages": [{"from_team": True, "at": "2026-04-04T23:59:00Z"}],
            **extra,
        },
    )
    assert (out["stale"], out["days"]) == (stale, 1)


@pytest.mark.parametrize(
    ("timeout", "now", "stale"),
    [
        (0, "2026-04-04T23:59:00Z", False),
        (0, "2026-04-05T00:00:00Z", True),
        (1, "2026-04-05T23:59:00Z", False),
        (1, "2026-04-06T00:00:00Z", True),
    ],
)
def test_staleness_timeout_day_boundary(capsys, tmp_path, timeout, now, stale):
    out = ok(
        capsys,
        tmp_path,
        "staleness",
        {
            "now": now,
            "messages": [{"from_team": True, "at": "2026-04-04T12:00:00Z"}],
            "timeout_days": timeout,
        },
    )
    assert out["stale"] is stale


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [
            {"from_team": True, "at": "2026-04-01T00:00:00Z"},
            {"from_team": False, "at": "2026-04-02T00:00:00Z"},
        ],
    ],
)
def test_zero_timeout_preserves_reporter_turn(capsys, tmp_path, messages):
    out = ok(capsys, tmp_path, "staleness", {"now": NOW, "messages": messages, "timeout_days": 0})
    assert (out["stale"], out["days"]) == (False, None)


# --- day setting coercion ---------------------------------------------------


@pytest.fixture(params=["window_days", "grace_period_days", "timeout_days"])
def day_setting(request):
    field = request.param
    data: dict[str, Any] = {"now": "2026-04-05T12:00:00Z"}
    if field == "timeout_days":
        data["messages"] = [{"from_team": True, "at": "2026-04-04T12:00:00Z"}]
        return "staleness", field, data
    data.update(created_at="2026-01-01T09:00:00Z", labels=["pr merged"])
    return "disclosure", field, data


@pytest.mark.parametrize("value", ["", [], {}], ids=["empty-string", "empty-list", "empty-object"])
def test_issue_sync_refuses_empty_day_inputs(capsys, tmp_path, day_setting, value):
    command, field, data = day_setting
    path = tmp_path / "input.json"
    path.write_text(json.dumps({**data, field: value}), encoding="utf-8")
    code = main(["issue-sync", command, "--input", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["ok"] is False
    assert isinstance(out["refused"], str) and out["refused"]


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


# --- 1d: the advisory archive URL gate ----------------------------------------

SUBJECT = "CVE-2026-12345: Apache Foo: path handling in the log viewer"
ADVISORY: dict[str, Any] = {
    "cve_id": "CVE-2026-12345",
    "advisory_list": "users@foo.apache.org",
    "mail_archive_url": "https://lists.apache.org",
    "url": "https://lists.apache.org/thread/abc123",
    "authorized_senders": ["rm@apache.org", "Sec Member <sec@apache.org>"],
    "thread": {
        "list": "<users.foo.apache.org>",
        "subject": SUBJECT,
        "from": "Release Manager <RM@apache.org>",
    },
}


def test_advisory_archive_accepts_the_advisory_thread(capsys, tmp_path) -> None:
    out = ok(capsys, tmp_path, "advisory-archive", ADVISORY)
    assert (out["accepted"], out["reasons"], out["requires_confirmation"]) == (True, [], True)
    assert out["list"] == "users@foo.apache.org"
    tagged = {
        **ADVISORY,
        "thread": {
            "list": "users@foo.apache.org",
            "subject": "[ANNOUNCE] CVE-2026-12345: Foo",
            "from": "sec@apache.org",
        },
    }
    assert ok(capsys, tmp_path, "advisory-archive", tagged)["accepted"] is True


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"thread": {"list": "dev@foo.apache.org", "subject": SUBJECT}}, "not on the public"),
        (
            {"thread": {"list": "<users.foo.apache.org>", "subject": "Re: CVE-2026-12345: Apache Foo"}},
            "advisory subject",
        ),
        (
            {"thread": {"list": "<users.foo.apache.org>", "subject": "Question about CVE-2026-12345"}},
            "advisory subject",
        ),
        (
            {"thread": {"list": "<users.foo.apache.org>", "subject": "CVE-2026-99999: Apache Foo"}},
            "advisory subject",
        ),
        ({"url": "https://example.org/thread/abc123"}, "configured archive"),
        ({"thread": {}}, "fetch the thread first"),
        ({"mail_archive_url": None}, "mail_archive_url is not configured"),
        (
            {
                "thread": {
                    "list": "<users.foo.apache.org>",
                    "subject": SUBJECT,
                    "from": '"rm@apache.org" <x@example.org>',
                }
            },
            "not from a release manager",
        ),
        (
            {
                "thread": {
                    "list": "<users.foo.apache.org>",
                    "subject": SUBJECT,
                    "from": "rm@apache.org, x@example.org",
                }
            },
            "who sent the root message",
        ),
        ({"authorized_senders": []}, "no authorized_senders"),
        (
            {"thread": {"list": "<users.foo.apache.org>", "subject": SUBJECT, "from": "someone@example.org"}},
            "not from a release manager",
        ),
        ({"thread": {"list": "<users.foo.apache.org>", "subject": SUBJECT}}, "who sent the root message"),
    ],
)
def test_advisory_archive_rejects_other_posts(capsys, tmp_path, change, reason) -> None:
    out = ok(capsys, tmp_path, "advisory-archive", {**ADVISORY, **change})
    assert out["accepted"] is False
    assert any(reason in r for r in out["reasons"]), out["reasons"]


def test_advisory_archive_refuses_without_a_list(capsys, tmp_path) -> None:
    path = tmp_path / "a.json"
    path.write_text(json.dumps({**ADVISORY, "advisory_list": ""}), encoding="utf-8")
    assert main(["issue-sync", "advisory-archive", "--input", str(path)]) != 0
