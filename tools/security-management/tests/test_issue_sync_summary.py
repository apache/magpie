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
"""`issue-sync nudge-summary` and the `summary:` clause of `parse-bulk-reply`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

TRACKER = "example-s/example-s"
NOW = "2026-11-26T09:00:00Z"
LIST = "security@example.apache.org"
# Built at run time so the source carries no literal record ID.
RECORD = "CVE" + "-2026-" + "12345"


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["issue-sync", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out)


def ok(capsys, tmp_path: Path, data: dict[str, Any]) -> dict[str, Any]:
    code, out = run(capsys, tmp_path, "nudge-summary", data)
    assert code == 0, out
    return out


def asked(
    issue: int, since: str, who: list[str], question: str = "Valid, or hardening only?"
) -> dict[str, Any]:
    return {
        "issue": issue,
        "title": f"Path traversal in the file reader ({issue})",
        "current_labels": ["security issue", "needs triage"],
        "pending_team_question": {
            "url": f"https://github.com/{TRACKER}/issues/{issue}#issuecomment-{issue}0",
            "question": question,
            "asked": who,
            "since": since,
        },
    }


def stale(n: int) -> list[dict[str, Any]]:
    return [asked(100 + i, "2026-11-01", ["alice"]) for i in range(n)]


def base(reports: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"tracker": TRACKER, "now": NOW, "security_list": LIST, "reports": reports, **extra}


def test_below_threshold_keeps_per_tracker_nudges(capsys, tmp_path):
    out = ok(capsys, tmp_path, base(stale(4)))
    assert out["collapse"] is False
    assert out["per_tracker_nudges"] == [100, 101, 102, 103]
    assert out["collapsed"] == [] and out["draft"] is None


def test_at_threshold_collapses_into_one_draft(capsys, tmp_path):
    out = ok(capsys, tmp_path, base(stale(5)))
    assert out["collapse"] is True
    assert out["collapsed"] == [100, 101, 102, 103, 104]
    assert out["per_tracker_nudges"] == []
    draft = out["draft"]
    assert draft["to"] == LIST and draft["new_thread"] is True
    assert draft["clean"] is True
    assert "It replaces 5 separate reminder comments" in draft["body"]
    assert (
        f"- Path traversal in the file reader (100)\n  https://github.com/{TRACKER}/issues/100\n"
        in draft["body"]
    )
    assert "waiting 25 days" in draft["body"]


def test_young_questions_are_not_nudge_candidates(capsys, tmp_path):
    reports = [*stale(4), asked(200, "2026-11-24", ["bob"])]
    out = ok(capsys, tmp_path, base(reports))
    assert out["nudge_candidates"] == [100, 101, 102, 103]
    assert out["collapse"] is False
    out = ok(capsys, tmp_path, base(reports, nudge_after_days=2))
    assert out["collapse"] is True and 200 in out["collapsed"]


def test_already_nudged_question_is_listed_but_not_a_candidate(capsys, tmp_path):
    reports = stale(5)
    reports[0]["pending_team_question"]["nudged"] = True
    out = ok(capsys, tmp_path, base(reports))
    assert out["nudge_candidates"] == [101, 102, 103, 104] and out["collapse"] is False
    out = ok(capsys, tmp_path, base(reports, nudge_summary_threshold=4))
    assert "/issues/100" in out["draft"]["body"]


@pytest.mark.parametrize(("value", "collapse"), [(3, True), ("3", True), ("off", False), (None, False)])
def test_threshold_setting(capsys, tmp_path, value, collapse):
    data = base(stale(4))
    if value is not None:
        data["nudge_summary_threshold"] = value
    assert ok(capsys, tmp_path, data)["collapse"] is collapse


@pytest.mark.parametrize("value", [0, "five", True, -1])
def test_bad_threshold_refused(capsys, tmp_path, value):
    code, out = run(capsys, tmp_path, "nudge-summary", base(stale(5), nudge_summary_threshold=value))
    assert code == 2 and out["ok"] is False


@pytest.mark.parametrize("address", [None, "TODO", "<security-list>"])
def test_missing_security_list_refused(capsys, tmp_path, address):
    code, out = run(capsys, tmp_path, "nudge-summary", {**base(stale(5)), "security_list": address})
    assert code == 2 and "security_list" in out["refused"]


def test_public_list_refused(capsys, tmp_path):
    data = base(stale(5), security_list="users@example.apache.org", public_lists=["users@example.apache.org"])
    code, out = run(capsys, tmp_path, "nudge-summary", data)
    assert code == 2 and "public list" in out["refused"]


def test_groups_and_deadlines(capsys, tmp_path):
    reports = [
        *stale(5),
        {  # waiting on the release manager
            "issue": 300,
            "title": "Token leak in the export log",
            "current_labels": ["cve allocated", "fix released"],
            "current_milestone": "3.1.1",
            "release_shipped": True,
            "advisory_shipped": False,
            "release_manager": "rmgr",
            "released_on": "2026-11-16",
        },
        {  # in flight
            "issue": 301,
            "current_labels": ["cve allocated", "pr created"],
            "current_milestone": "3.1.2",
            "milestone_due_on": "2026-12-03",
            "fix_pr": {"url": "https://github.com/example/example/pull/9", "state": "open"},
            "release_shipped": False,
        },
        {  # fix work needed, disclosure overdue
            "issue": 302,
            "title": "Unsafe redirect after login",
            "current_labels": ["cve allocated"],
            "proposed_milestone": "3.2.0 (create)",
            "fix_pr": {"url": None, "state": None},
            "expected_disclosure_by": "2026-11-20",
        },
        {"issue": 303, "state": "closed", "current_labels": ["announced"]},
    ]
    body = ok(capsys, tmp_path, base(reports, project_name="Example"))["draft"]["body"]
    assert "1. Needs a decision: 5" in body
    assert "4. Waiting on the release manager (released, advisory not sent): 1" in body
    assert "Release manager: rmgr; waiting 10 days since 3.1.1 shipped" in body
    assert "3. In flight (fix PR open or merged, awaiting release): 1" in body
    assert "fix PR open; release 3.1.2, 2026-12-03" in body
    assert "2. Fix work needed (valid, no fix PR yet): 1" in body
    assert "target 3.2.0, cut date not set" in body
    assert (
        "- 2026-11-20: disclosure window ends (OVERDUE by 6 days): Unsafe redirect after login\n"
        f"  https://github.com/{TRACKER}/issues/302\n"
    ) in body
    assert f"- 2026-12-03: release 3.1.2 cut\n  https://github.com/{TRACKER}/issues/301\n" in body
    assert f"- Token leak in the export log\n  https://github.com/{TRACKER}/issues/300\n" in body
    assert "other open trackers" not in body  # the closed tracker is not counted as open
    assert "/issues/303" not in body


def personal(*handles: str) -> dict[str, Any]:
    """The documented `user` input: the `security_issue_sync` block of `user.md`."""
    return {"do_not_ping": list(handles)}


def test_do_not_ping_whole_user_md_shape_also_excludes(capsys, tmp_path):
    reports = [*stale(4), asked(110, "2026-11-01", ["carol"])]
    user = {"security_issue_sync": {"do_not_ping": ["carol"]}}
    assert "carol" not in ok(capsys, tmp_path, base(reports, user=user))["draft"]["body"]


def test_do_not_ping_and_names(capsys, tmp_path):
    reports = [asked(100 + i, "2026-11-01", ["alice", "carol"]) for i in range(4)]
    reports.append(asked(110, "2026-11-01", ["carol"]))
    data = base(reports, user=personal("@carol"), people={"alice": "Alice Example"})
    body = ok(capsys, tmp_path, data)["draft"]["body"]
    assert "Asked: Alice Example (alice); waiting" in body
    assert "carol" not in body
    assert "Asked: the security team; waiting" in body
    assert "@" not in body.replace(LIST, "")


def test_do_not_ping_leaves_no_trace(capsys, tmp_path):
    # Every asked person excluded reads the same as nobody named; an excluded RM leaves a plain wait line.
    rm = {
        "issue": 300,
        "title": "Token leak in the export log",
        "current_labels": ["fix released"],
        "current_milestone": "3.1.1",
        "release_shipped": True,
        "advisory_shipped": False,
        "release_manager": "carol",
        "released_on": "2026-11-16",
    }
    excluded = ok(
        capsys, tmp_path, base([*stale(4), asked(110, "2026-11-01", ["carol"]), rm], user=personal("carol"))
    )
    nobody = ok(
        capsys, tmp_path, base([*stale(4), asked(110, "2026-11-01", []), {**rm, "release_manager": None}])
    )
    assert excluded["draft"]["body"] == nobody["draft"]["body"]
    body = excluded["draft"]["body"]
    assert "  Waiting 10 days since 3.1.1 shipped\n" in body
    for hint in ("carol", "skipped", "omitted", "not named", "do_not_ping", "the release manager;"):
        assert hint not in body


def test_do_not_ping_is_read_from_the_personal_layer_only(capsys, tmp_path):
    reports = [*stale(4), asked(110, "2026-11-01", ["carol"])]
    body = ok(capsys, tmp_path, base(reports, do_not_ping=["carol"]))["draft"]["body"]
    assert "Asked: carol; waiting" in body


def test_guardrails_run_over_the_body(capsys, tmp_path):
    reports = [*stale(4), asked(120, "2026-11-01", ["alice"], "Is CVSS 9.8 (critical) right?")]
    draft = ok(capsys, tmp_path, base(reports))["draft"]
    assert draft["clean"] is False
    assert {v["guardrail"] for v in draft["violations"]} == {"Never propagate a reporter-supplied CVSS score"}


def test_recap_line_after_the_draft(capsys, tmp_path):
    out = ok(capsys, tmp_path, base(stale(6), draft={"id": "r-77", "url": "https://mail.example/d/r-77"}))
    assert out["recap_line"] == (
        f"- 6 nudges replaced by summary email draft [`r-77`](https://mail.example/d/r-77) to {LIST}: review and send it."
    )


def parse(
    capsys, tmp_path: Path, reply: str, summary: bool = True, skipped: list[int] | None = None
) -> dict[str, Any]:
    data = {
        "reply": reply,
        "proposal": {"212": [1, 2]},
        "summary": summary,
        "preflight_skipped": skipped or [],
    }
    code, out = run(capsys, tmp_path, "parse-bulk-reply", data)
    assert code == 0, out
    return out


def test_bulk_reply_summary_clause(capsys, tmp_path):
    assert parse(capsys, tmp_path, "all")["summary"] == "draft"
    assert parse(capsys, tmp_path, "212:1")["summary"] == "skip"  # a subset never approves the summary
    assert parse(capsys, tmp_path, "212:1; summary")["summary"] == "draft"
    assert parse(capsys, tmp_path, "force-sync 211", skipped=[211])["summary"] == "skip"
    for empty in ("", "   ", "\n"):
        out = parse(capsys, tmp_path, empty)
        assert (out["action"], out["summary"]) == ("ambiguous", None)
    out = parse(capsys, tmp_path, "all; summary:skip")
    assert (out["action"], out["summary"]) == ("apply", "skip")
    assert parse(capsys, tmp_path, "cancel")["summary"] == "skip"
    for reply in ("summary:maybe", "summary:skip; summary", "212:all; summary:skip; summary:all"):
        assert parse(capsys, tmp_path, reply)["action"] == "ambiguous"
    assert parse(capsys, tmp_path, "summary:skip", summary=False)["action"] == "ambiguous"
    assert parse(capsys, tmp_path, "all", summary=False)["summary"] is None


# --- review follow-ups ---------------------------------------------------------


def test_final_stage_keeps_the_step_4b_collapse(capsys, tmp_path):
    preview = ok(capsys, tmp_path, base(stale(5)))
    reports = stale(5)
    for report in reports[:3]:  # the apply loop answered or closed three of them
        report["state"] = "closed"
    data = base(reports, stage="final", collapsed=preview["collapsed"])
    out = ok(capsys, tmp_path, data)
    assert out["collapse"] is True and out["collapsed"] == [100, 101, 102, 103, 104]
    assert out["draft"] is not None and "It replaces 5 separate reminder comments" in out["draft"]["body"]
    code, refused = run(capsys, tmp_path, "nudge-summary", base(reports, stage="final"))
    assert code == 2 and "collapsed" in refused["refused"]
    code, refused = run(capsys, tmp_path, "nudge-summary", base(reports, stage="later"))
    assert code == 2


def test_final_stage_ignores_unapplied_proposals(capsys, tmp_path):
    fix = {"issue": 302, "title": "Unsafe redirect", "current_labels": ["cve allocated"],
           "current_milestone": "3.1.2", "proposed_milestone": "3.2.0 (create)"}  # fmt: skip
    preview = ok(capsys, tmp_path, base([*stale(5), fix]))["draft"]["body"]
    final = ok(capsys, tmp_path, base([*stale(5), fix], stage="final", collapsed=[100]))["draft"]["body"]
    assert "target 3.2.0" in preview
    assert "target 3.1.2" in final and "3.2.0" not in final


@pytest.mark.parametrize(
    ("report", "group"),
    [
        ({"current_labels": ["cve allocated", "pr merged", "announced"], "fix_pr": {"state": "merged"},
          "release_shipped": True, "advisory_shipped": True}, None),
        ({"current_labels": ["pr merged"], "fix_pr": {"state": "merged"}, "advisory_shipped": True}, None),
        ({"current_labels": ["cve allocated", "fix released"], "fix_pr": {"state": "merged"},
          "release_shipped": "unknown"}, "4. Waiting on the release manager"),
        ({"current_labels": ["invalid"]}, None),
        ({"current_labels": ["duplicate"]}, None),
        ({"current_labels": ["wontfix"]}, None),
        ({"current_labels": ["not CVE worthy"]}, None),
    ],
)  # fmt: skip
def test_terminal_states_checked_first(capsys, tmp_path, report, group):
    tracked = {"issue": 400, "title": "Some tracker", "current_milestone": "3.1.1",
               "milestone_due_on": "2026-11-20", **report}  # fmt: skip
    body = ok(capsys, tmp_path, base([*stale(5), tracked]))["draft"]["body"]
    assert "release 3.1.1 cut" not in body  # no false overdue release deadline
    if group is None:
        assert "/issues/400" not in body
        assert "1 other open trackers need nothing from the team" in body
    else:
        assert f"{group} (released, advisory not sent): 1" in body


def test_preflight_skipped_trackers_are_counted_and_grouped(capsys, tmp_path):
    nodes = [
        {"number": 500, "state": "OPEN", "title": "Header injection in proxy",
         "labels": {"nodes": [{"name": "cve allocated"}, {"name": "pr merged"}]},
         "milestone": {"title": "3.1.2", "dueOn": "2026-12-03T00:00:00Z"},
         "comments": {"nodes": [{"body": "SECRET COMMENT BODY"}]}},
        {"number": 501, "state": "OPEN", "title": "Token leak in export",
         "labels": {"nodes": [{"name": "cve allocated"}, {"name": "fix released"}]}, "milestone": None},
        {"number": 100, "state": "OPEN", "title": "dup of a report", "labels": {"nodes": []}},
    ]  # fmt: skip
    body = ok(capsys, tmp_path, base(stale(5), preflight_trackers=nodes))["draft"]["body"]
    assert "the state of the 7 open trackers" in body
    assert (
        f"- Header injection in proxy\n  https://github.com/{TRACKER}/issues/500\n  fix PR merged; release 3.1.2, 2026-12-03"
        in body
    )
    assert (
        f"- Token leak in export\n  https://github.com/{TRACKER}/issues/501\n  Waiting since the release, date unknown"
        in body
    )
    assert "SECRET COMMENT BODY" not in body
    assert "dup of a report" not in body  # a subagent report wins over the pre-flight node


def test_question_and_title_scrub(capsys, tmp_path):
    reports = stale(4)
    reports.append(
        {**asked(120, "2026-11-01", ["alice", "carol"],
                 f"@alice and @carol: is this the same as #77 or other/repo#9 ({RECORD})?"),
         "title": "Carol Example found GHSA-abcd-efgh-ijkl in #12 parser"}
    )  # fmt: skip
    data = base(reports, user=personal("carol"), people={"carol": "Carol Example"})
    draft = ok(capsys, tmp_path, data)["draft"]
    body = draft["body"]
    for gone in ("@", "carol", "Carol", "#77", "other/repo#9", RECORD, "GHSA-", "#12"):
        assert gone not in body.replace("security team", ""), gone
    assert "Question: alice and: is this the same as or?" in body
    assert "- found in parser\n" in body
    assert draft["clean"] is True


def test_residue_makes_the_draft_unclean(capsys, tmp_path):
    from security_management.issue_sync import summary

    found = summary._residue(f"- x @someone\n- y {RECORD}\n- z #42\n- plain")
    assert {f["guardrail"] for f in found} == {
        "Summary carries an @-mention", "Summary carries a CVE or GHSA ID", "Summary carries a bare reference"
    }  # fmt: skip


@pytest.mark.parametrize(
    ("issue_url", "prefix", "kept"),
    [
        (f"https://github.com/{TRACKER}/issues/100", None, True),
        ("https://evil.example/phish/100", None, False),
        (f"https://github.com/{TRACKER}/issues/100.evil.example", None, False),
        ("https://github.com/other/repo/issues/100", None, False),
        ("https://jira.example.org/browse/SEC-100", "https://jira.example.org/browse/", True),
        ("https://jira.example.org/browse/SEC-101", "https://jira.example.org/browse/", False),
    ],
)
def test_issue_url_must_be_the_trackers_own(capsys, tmp_path, issue_url, prefix, kept):
    reports = stale(5)
    reports[0]["issue_url"] = issue_url
    data = base(reports, **({"issue_url_prefix": prefix} if prefix else {}))
    body = ok(capsys, tmp_path, data)["draft"]["body"]
    assert (issue_url in body.split()) is kept
    if not kept:
        assert f"https://github.com/{TRACKER}/issues/100" in body
