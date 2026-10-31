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
"""`security-management issue-invalidate` end to end through the CLI.

The cases of the retired model-graded `security-issue-invalidate` suites
`step-2-import-path`, `step-5a-labels`, `step-5b-closing-comment`,
`step-5d-email-draft`, `step-5e-rollup-entry`, `step-5f-confirm` and
`step-7-recap` live here, named after each former case, with the same
scenario and expected output. `step-3-mine-reasoning` and
`step-4-canned-response` stay model evals.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

TRACKER = "airflow-s/airflow-s"
SCOPES = ["airflow", "providers", "chart"]
ROSTER = ["triager-a", "triager-b", "triager-c"]


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["issue-invalidate", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out)


def body(thread: str, cve_link: str = "_No response_") -> str:
    return (
        "### The issue description\n\nreport\n\n"
        f"### Security mailing list thread\n\n{thread}\n\n"
        "### Reporter credited as\n\nAlice Nguyen\n\n"
        f"### CVE tool link\n\n{cve_link}\n"
    )


def path_of(capsys, tmp_path, thread: str) -> dict[str, Any]:
    _, out = run(capsys, tmp_path, "import-path", {"body": body(thread)})
    return {k: out[k] for k in ("import_path", "email_draft_step", "thread_id")}


# --- step-2-import-path ------------------------------------------------------


def test_step2_case_1_public_archive_url(capsys, tmp_path):
    assert path_of(capsys, tmp_path, "https://lists.apache.org/thread/abc123xyz") == {
        "import_path": "security_at_imported_public",
        "email_draft_step": "required",
        "thread_id": None,
    }


def test_step2_case_2_gmail_only_sentinel(capsys, tmp_path):
    thread = "No public archive URL — tracked privately on Gmail thread 18f3a2b9c1d4e507"
    assert path_of(capsys, tmp_path, thread) == {
        "import_path": "security_at_imported_gmail_only",
        "email_draft_step": "required",
        "thread_id": "18f3a2b9c1d4e507",
    }


def test_step2_case_3_pr_imported_sentinel(capsys, tmp_path):
    thread = "N/A — opened from public PR apache/airflow#45210; no security@ thread"
    assert path_of(capsys, tmp_path, thread) == {
        "import_path": "pr_imported",
        "email_draft_step": "skip",
        "thread_id": None,
    }


def test_step2_case_4_indeterminate_empty(capsys, tmp_path):
    assert path_of(capsys, tmp_path, "_No response_") == {
        "import_path": "indeterminate",
        "email_draft_step": "surface_to_user",
        "thread_id": None,
    }


def test_import_path_rollup_fallback_and_ambiguous_field(capsys, tmp_path):
    data = {
        "body": body("https://lists.apache.org/thread/abc123xyz"),
        "rollup_provenance": "**Imported from Gmail thread `18f3a2b9c1d4e507` on 2026-01-01**",
    }
    _, out = run(capsys, tmp_path, "import-path", data)
    assert out["thread_id"] == "18f3a2b9c1d4e507" and out["thread_source"] == "rollup"
    doubled = body("x") + "\n### Security mailing list thread\n\ny\n"
    code, out = run(capsys, tmp_path, "import-path", {"body": doubled})
    assert code == 2 and "ambiguous" in out["refused"]


# --- Step 0 and the selector ---------------------------------------------------


def stops(capsys, tmp_path, **data: Any) -> dict[str, Any]:
    _, out = run(capsys, tmp_path, "hard-stops", {"state": "OPEN", "labels": [], "body": body("x"), **data})
    return out


def test_hard_stops(capsys, tmp_path):
    assert stops(capsys, tmp_path)["verdict"] == "proceed"
    assert stops(capsys, tmp_path, state="CLOSED")["verdict"] == "noop"
    out = stops(capsys, tmp_path, labels=[{"name": "fix released"}])
    assert out["verdict"] == "stop" and "label: `fix released`" in out["message"]
    linked = body("x", "https://cveprocess.apache.org/cve5/CVE-2026-12345")
    out = stops(capsys, tmp_path, body=linked)
    assert out["verdict"] == "probe" and out["cve_id"] == "CVE-2026-12345"
    out = stops(capsys, tmp_path, body=linked, cve_state="review-ready")
    assert out["verdict"] == "stop" and "Retract the CVE record" in out["message"]
    assert stops(capsys, tmp_path, body=linked, cve_state="public")["verdict"] == "escalate"
    assert stops(capsys, tmp_path, body=linked, cve_state="retracted")["verdict"] == "proceed"
    assert stops(capsys, tmp_path, labels=["cve allocated"], cve_state="unknown")["verdict"] == "ask"


def test_selector_forms(capsys, tmp_path):
    for invocation in (
        "invalidate 240",
        "invalidate #240",
        f"invalidate {TRACKER}#240",
        f"https://github.com/{TRACKER}/issues/240",
    ):
        _, out = run(capsys, tmp_path, "selector", {"invocation": invocation, "tracker": TRACKER})
        assert out["mode"] == "single" and out["numbers"] == [240]
        assert out["command"].startswith("gh issue view 240 --repo airflow-s/airflow-s --json")
    _, out = run(
        capsys,
        tmp_path,
        "selector",
        {"invocation": "invalidate #1-#3, #30", "tracker": TRACKER, "scratch": "/s"},
    )
    assert out["mode"] == "bulk" and out["numbers"] == [1, 2, 3, 30]
    assert out["batches"][0]["command"] == "gh api graphql -F query=@/s/invalidate-batch-1.graphql"
    assert "reactions(first: 50, content: THUMBS_UP)" in out["batches"][0]["query"]
    _, out = run(capsys, tmp_path, "selector", {"invocation": "invalidate proposed", "tracker": TRACKER})
    assert out["mode"] == "proposed" and "--limit 1000" in out["command"]
    code, _ = run(capsys, tmp_path, "selector", {"invocation": "invalidate other/repo#2", "tracker": TRACKER})
    assert code == 2


PROPOSAL = "**Triage proposal**\n\nx\n\n**Proposed disposition: INVALID.**\n"


def issue(number: int, comments: list[dict[str, Any]]) -> dict[str, Any]:
    return {"number": number, "comments": {"nodes": comments}}


def comment(author: str, text: str, thumbs: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "author": {"login": author},
        "body": text,
        "reactions": {"nodes": [{"user": {"login": t}} for t in thumbs]},
    }


def test_consensus(capsys, tmp_path):
    data = {
        "tracker": TRACKER,
        "roster": ROSTER,
        "fetched": 5,
        "trackers": [
            issue(1, [comment("triager-a", PROPOSAL, ("triager-b",))]),
            issue(2, [comment("triager-a", PROPOSAL, ("triager-a", "outsider"))]),
            issue(3, [comment("triager-a", PROPOSAL), comment("triager-c", "I agree, close it")]),
            issue(4, [comment("outsider", PROPOSAL, ("triager-b",))]),
            issue(5, [comment("triager-a", PROPOSAL), comment("triager-a", "LGTM")]),
        ],
    }
    _, out = run(capsys, tmp_path, "consensus", data)
    assert [a["number"] for a in out["agreed"]] == [1, 3]
    assert [a["number"] for a in out["awaiting"]] == [2, 4, 5]
    assert out["awaiting"][0]["note"] == "awaiting consensus on airflow-s/airflow-s#2 — skipped"
    _, out = run(capsys, tmp_path, "consensus", {**data, "fetched": 1000})
    assert out["stop"] and out["agreed"] == []


# --- step-5a-labels ------------------------------------------------------------


def label_plan(capsys, tmp_path, current: list[str], number: int, **extra: Any) -> dict[str, Any]:
    _, out = run(
        capsys,
        tmp_path,
        "labels",
        {"labels": current, "scope_labels": SCOPES, "tracker": TRACKER, "number": number, **extra},
    )
    return out


def test_step5a_case_1_full_label_cleanup(capsys, tmp_path):
    out = label_plan(capsys, tmp_path, ["security issue", "airflow", "needs triage"], 312)
    assert {k: out[k] for k in ("labels_to_add", "labels_to_remove", "security_issue_stays")} == {
        "labels_to_add": ["invalid"],
        "labels_to_remove": ["needs triage", "airflow"],
        "security_issue_stays": True,
    }
    assert out["command"] == (
        'gh issue edit 312 --repo airflow-s/airflow-s --add-label "invalid" '
        '--remove-label "needs triage" --remove-label "airflow"'
    )


def test_step5a_case_2_pr_created_also_present(capsys, tmp_path):
    out = label_plan(capsys, tmp_path, ["security issue", "providers", "pr created"], 341)
    assert out["labels_to_add"] == ["invalid"]
    assert out["labels_to_remove"] == ["providers", "pr created"]
    assert out["security_issue_stays"] is True


FULL = ["security issue", "providers", "needs triage", "pr created", "pr merged"]
EDIT_7 = 'gh issue edit 7 --repo airflow-s/airflow-s --add-label "invalid" '


def test_step5a_default_without_keep_labels_is_unchanged(capsys, tmp_path):
    out = label_plan(capsys, tmp_path, FULL, 7)
    assert out["labels_to_remove"] == ["needs triage", "providers", "pr created", "pr merged"]
    assert "labels_kept" not in out and "warnings" not in out
    assert out == label_plan(capsys, tmp_path, FULL, 7, keep_labels=[])


def test_step5a_keep_scope(capsys, tmp_path):
    out = label_plan(capsys, tmp_path, FULL, 7, keep_labels=["scope"])
    assert out["labels_to_remove"] == ["needs triage", "pr created", "pr merged"]
    assert out["labels_kept"] == ["providers"]
    assert out["command"] == (
        EDIT_7 + '--remove-label "needs triage" --remove-label "pr created" --remove-label "pr merged"'
    )


def test_step5a_keep_pr(capsys, tmp_path):
    out = label_plan(capsys, tmp_path, FULL, 7, keep_labels=["pr"])
    assert out["labels_to_remove"] == ["needs triage", "providers"]
    assert out["labels_kept"] == ["pr created", "pr merged"]


def test_step5a_keep_scope_and_pr(capsys, tmp_path):
    out = label_plan(capsys, tmp_path, FULL, 7, keep_labels=["scope", "pr"])
    assert out["labels_to_remove"] == ["needs triage"]
    assert out["command"] == EDIT_7 + '--remove-label "needs triage"'


def test_step5a_keep_literal_label(capsys, tmp_path):
    out = label_plan(capsys, tmp_path, FULL, 7, keep_labels=["pr merged", "chart"])
    assert out["labels_to_remove"] == ["needs triage", "providers", "pr created"]
    assert out["labels_kept"] == ["pr merged"]


def test_step5a_needs_triage_cannot_be_kept(capsys, tmp_path):
    out = label_plan(capsys, tmp_path, FULL, 7, keep_labels=["needs triage", "scope"])
    assert out["labels_to_remove"] == ["needs triage", "pr created", "pr merged"]
    assert out["labels_to_add"] == ["invalid"]
    assert out["warnings"] == [
        "keep_labels lists `needs triage`: ignored, it is always removed on invalidate"
    ]


def test_apply_plan_honours_keep_labels(capsys, tmp_path):
    _, out = run(
        capsys,
        tmp_path,
        "apply-plan",
        {
            "tracker": TRACKER,
            "number": 7,
            "scratch": "/s",
            "labels": FULL,
            "scope_labels": SCOPES,
            "keep_labels": ["scope", "pr"],
        },
    )
    step = next(s for s in out["steps"] if s["step"] == "6c")
    assert step["command"] == EDIT_7 + '--remove-label "needs triage"'


# --- step-5b-closing-comment -----------------------------------------------------


def close(capsys, tmp_path, number: int, decided: int, rollup: int, case: str) -> str:
    data = {
        "decision_comment": f"https://github.com/{TRACKER}/issues/{number}#issuecomment-{decided}",
        "rollup_comment": f"https://github.com/{TRACKER}/issues/{number}#issuecomment-{rollup}",
        "notification_case": case,
    }
    _, out = run(capsys, tmp_path, "render-close", data)
    return str(out["text"])


def test_step5b_case_1_security_imported(capsys, tmp_path):
    text = close(capsys, tmp_path, 312, 1004, 9001, "direct")
    assert "Closing as `invalid`" in text
    assert "[this discussion](#issuecomment-1004)" in text
    assert "[status rollup](#issuecomment-9001)" in text
    assert "a draft reply to the reporter is in Gmail awaiting review" in text
    assert len(text.split("\n\n")) == 2  # brief: two sentences, no reasoning


def test_step5b_case_2_pr_imported(capsys, tmp_path):
    text = close(capsys, tmp_path, 341, 3001, 9041, "pr_imported")
    assert "[this discussion](#issuecomment-3001)" in text and "[status rollup](#issuecomment-9041)" in text
    assert "Gmail" not in text and "no reporter notification (PR-imported tracker" in text


# --- step-5d-email-draft --------------------------------------------------------


def draft_input(**extra: Any) -> dict[str, Any]:
    return {
        "import_path": "security_at_imported_gmail_only",
        "thread_id": "18f3a2b9c1d4e507",
        "last_message_id": "msg-abc123",
        "root_subject": "Possible RCE via task log endpoint",
        "reporter_email": "alice@example.com",
        "security_cc": "security@airflow.apache.org",
        **extra,
    }


def test_step5d_case_1_draft_created(capsys, tmp_path):
    _, out = run(capsys, tmp_path, "draft-plan", draft_input(existing_drafts=[]))
    assert out["action"] == "create" and out["notification_case"] == "direct"
    assert out["to"] == "alice@example.com" and out["cc"] == "security@airflow.apache.org"
    assert out["subject"] == "Re: Possible RCE via task log endpoint"
    assert out["backend"] == "oauth_curl" and out["anchor"] == {"thread_id": "18f3a2b9c1d4e507"}
    reply = "Dear Alice,\n\nThank you for your report. Per our Security Model this is working as intended.\n"
    _, out = run(capsys, tmp_path, "check-draft", {"body": reply, "tracker": TRACKER})
    assert out == {"clean": True, "hits": []}


def test_step5d_case_2_existing_draft_found(capsys, tmp_path):
    existing = {"id": "r9abc123def456", "subject": "Re: DAG serialization leaks env variable names"}
    _, out = run(capsys, tmp_path, "draft-plan", draft_input(existing_drafts=[existing]))
    assert out["action"] == "surface_existing" and out["existing_draft"]["id"] == "r9abc123def456"


def test_draft_plan_skips_blocks_and_backends(capsys, tmp_path):
    for path, case in (("pr_imported", "pr_imported"), ("internal_audit", "internal_audit")):
        _, out = run(capsys, tmp_path, "draft-plan", draft_input(import_path=path))
        assert out["action"] == "skip" and out["notification_case"] == case
    _, out = run(capsys, tmp_path, "draft-plan", draft_input(security_cc=""))
    assert out["action"] == "blocked"
    _, out = run(capsys, tmp_path, "draft-plan", draft_input(oauth_credentials=False, body_has_links=False))
    assert out["backend"] == "claude_ai_mcp" and out["anchor"] == {"reply_to_message_id": "msg-abc123"}
    code, _ = run(capsys, tmp_path, "draft-plan", draft_input(oauth_credentials=False))
    assert code == 2
    _, out = run(
        capsys, tmp_path, "draft-plan", draft_input(via_forwarder=True, forwarder_contact="relay@example.org")
    )
    assert out["to"] == "relay@example.org" and out["notification_case"] == "via_forwarder"
    _, out = run(
        capsys, tmp_path, "draft-plan", draft_input(ghsa={"only_channel": True, "write_access": True})
    )
    assert out["notification_case"] == "ghsa_comment"


def test_check_draft_flags_leaks(capsys, tmp_path):
    reply = (
        "See airflow-s/airflow-s#312 and https://cveprocess.apache.org/cve5/CVE-2026-1.\n"
        "Your CVSS 7.5 is noted; Tomcat had the same. Happy to discuss further. Also #12.\n"
    )
    _, out = run(
        capsys,
        tmp_path,
        "check-draft",
        {"body": reply, "tracker": TRACKER, "disposition": "duplicate", "organization": "ASF"},
    )
    kinds = {h["kind"] for h in out["hits"]}
    assert kinds == {
        "tracker-reference",
        "cve-tool-url",
        "cvss",
        "asf-project",
        "reopening-phrase",
        "bare-ref",
        "missing-canonical-cve",
    }


def test_check_draft_skips_asf_project_names_for_a_non_asf_project(capsys, tmp_path):
    reply = "Tomcat had the same issue.\n"
    _, out = run(
        capsys,
        tmp_path,
        "check-draft",
        {"body": reply, "tracker": TRACKER, "disposition": "duplicate", "organization": "independent"},
    )
    assert "asf-project" not in {h["kind"] for h in out["hits"]}


def test_check_draft_flags_a_configured_cve_tool_url_without_a_scheme(capsys, tmp_path):
    reply = "See https://cve.example.org/cve5/CVE-2026-1.\n"
    _, out = run(
        capsys,
        tmp_path,
        "check-draft",
        {"body": reply, "tracker": TRACKER, "disposition": "duplicate", "cve_tool_url": "cve.example.org"},
    )
    assert "cve-tool-url" in {h["kind"] for h in out["hits"]}


def test_check_draft_allows_the_public_cve_record_when_cve_org_is_the_tool(capsys, tmp_path):
    reply = "See https://www.cve.org/CVERecord?id=CVE-2026-1.\n"
    _, out = run(
        capsys,
        tmp_path,
        "check-draft",
        {
            "body": reply,
            "tracker": TRACKER,
            "disposition": "duplicate",
            "cve_tool_url": "https://www.cve.org",
        },
    )
    assert "cve-tool-url" not in {h["kind"] for h in out["hits"]}


def test_check_draft_flags_asf_project_names_when_organization_is_unset(capsys, tmp_path):
    reply = "Tomcat had the same issue.\n"
    _, out = run(
        capsys, tmp_path, "check-draft", {"body": reply, "tracker": TRACKER, "disposition": "duplicate"}
    )
    assert "asf-project" in {h["kind"] for h in out["hits"]}


# --- step-5e-rollup-entry -------------------------------------------------------


def entry(
    capsys, tmp_path, number: int, notification: dict[str, Any], quotes: list[tuple[str, int]]
) -> tuple[int, dict[str, Any]]:
    data = {
        "tracker": TRACKER,
        "date": "2025-05-16",
        "decision_comment": f"https://github.com/{TRACKER}/issues/{number}#issuecomment-1004",
        "quotes": [{"author": a, "quote": f"quote {c}", "comment": c} for a, c in quotes],
        "canned_section": "Negative Assessment response",
        "notification": notification,
        "board": {"archived": True, "item_id": "PVTI_lADOCAwKzs4BUzbt"},
    }
    return run(capsys, tmp_path, "render-rollup", data)


def entry_properties(out: dict[str, Any]) -> dict[str, Any]:
    text = out["text"]
    return {
        "has_closed_as_invalid_summary": out["label"] == "Closed as invalid",
        "has_reasoning_quotes": bool(re.search(r"^- @[\w-]+: > ", text, re.M)),
        "has_canned_response_ref": "*Negative Assessment response*" in text,
        "has_project_board_archived": "**Project board:** archived (item `PVTI_" in text,
        "has_next_step_terminal": "**Next:** none — terminal disposition." in text,
        "has_bare_issue_numbers": bool(out["bare_refs"]),
    }


EXPECTED_ENTRY = {
    "has_closed_as_invalid_summary": True,
    "has_reasoning_quotes": True,
    "has_canned_response_ref": True,
    "has_project_board_archived": True,
    "has_next_step_terminal": True,
    "has_bare_issue_numbers": False,
}


def test_step5e_case_1_security_imported_with_draft(capsys, tmp_path):
    notification = {
        "case": "direct",
        "draft_id": "r9def456abc789",
        "thread_id": "18f3a2b9c1d4e507",
        "message_id": "m1",
    }
    code, out = entry(
        capsys, tmp_path, 312, notification, [("triager-a", 1001), ("triager-b", 1002), ("triager-a", 1003)]
    )
    assert code == 0 and entry_properties(out) == EXPECTED_ENTRY
    assert (
        "**Reporter notification:** Gmail draft `r9def456abc789` created on thread `18f3a2b9c1d4e507`"
        in out["text"]
    )
    assert all(not line.startswith(" ") for line in out["text"].split("\n"))


def test_step5e_case_2_pr_imported_no_draft(capsys, tmp_path):
    code, out = entry(
        capsys, tmp_path, 341, {"case": "pr_imported"}, [("triager-b", 2001), ("triager-c", 2002)]
    )
    assert code == 0 and entry_properties(out) == EXPECTED_ENTRY
    assert "**Reporter notification:** none (no reporter; per [Reporter credit policy]" in out["text"]


def test_rollup_entry_refuses_without_a_notification_case_and_caps_quotes(capsys, tmp_path):
    code, out = entry(capsys, tmp_path, 1, {}, [("triager-a", 1)])
    assert code == 2 and "Reporter notification" in out["refused"]
    _, out = entry(capsys, tmp_path, 1, {"case": "indeterminate"}, [("triager-a", n) for n in range(1, 8)])
    assert out["quotes_dropped"] == 2 and out["text"].count("- @triager-a") == 5
    _, out = entry(capsys, tmp_path, 1, {"case": "direct"}, [("triager-a", 1)])
    assert out["needs_amend"] is True


# --- step-5f-confirm ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("reply", "action"),
    [("go", "apply"), ("silent", "apply_silent"), ("cancel", "cancel")],
    ids=["case-1-go", "case-2-silent", "case-3-cancel"],
)
def test_step5f_confirm(capsys, tmp_path, reply, action):
    _, out = run(capsys, tmp_path, "parse-reply", {"reply": reply})
    assert out["action"] == action
    assert out["email_body_override"] is None and out["canned_section_override"] is None


def test_confirm_forms_with_arguments(capsys, tmp_path):
    _, out = run(capsys, tmp_path, "parse-reply", {"reply": "email: Dear Alice, thanks."})
    assert out["action"] == "replace_email_body" and out["email_body_override"] == "Dear Alice, thanks."
    _, out = run(
        capsys, tmp_path, "parse-reply", {"reply": "canned: DoS issues triggered by Authenticated users"}
    )
    assert out["canned_section_override"] == "DoS issues triggered by Authenticated users"
    for reply in ("ok then", "don't go", ""):
        _, out = run(capsys, tmp_path, "parse-reply", {"reply": reply})
        assert out["action"] == "ambiguous"
    _, out = run(capsys, tmp_path, "parse-reply", {"reply": "email: x", "draft_proposed": False})
    assert out["action"] == "ambiguous"


# --- Step 5c and Step 6 ---------------------------------------------------------------


def test_board_and_apply_plan(capsys, tmp_path):
    base = {
        "tracker": TRACKER,
        "number": 312,
        "scratch": "/s",
        "project_number": 2,
        "project_node_id": "PVT_x",
    }
    _, out = run(capsys, tmp_path, "board", base)
    assert out["read"]["command"] == "gh api graphql -F query=@/s/invalidate-312-board.graphql -F n=312"
    items = [{"id": "PVTI_1", "isArchived": False, "project": {"number": 2}}]
    _, out = run(capsys, tmp_path, "board", {**base, "items": items})
    assert out["archive"]["command"].endswith("-F pid=PVT_x -F iid=PVTI_1")
    assert "archiveProjectV2Item" in out["archive"]["query"] and "delete" not in out["archive"]["query"]
    _, out = run(capsys, tmp_path, "board", {**base, "items": []})
    assert out["archive"] is None and "not on the board" in out["note"]
    _, out = run(
        capsys,
        tmp_path,
        "apply-plan",
        {**base, "labels": ["needs triage", "airflow"], "scope_labels": SCOPES},
    )
    assert [s["step"] for s in out["steps"]] == ["6a", "6b", "6c", "6d", "6e", "6f", "6f-amend", "6g"]
    assert out["steps"][0]["command"].endswith(
        'rollup-append 312 "Closed as invalid" /s/invalidate-312-rollup.md'
    )
    assert (
        out["steps"][3]["command"] == "gh issue close 312 --repo airflow-s/airflow-s --reason 'not planned'"
    )


# --- step-7-recap -----------------------------------------------------------------------


def recap_properties(text: str, bare: list[str]) -> dict[str, bool]:
    return {
        "has_tracker_link": f"](https://github.com/{TRACKER}/issues/" in text,
        "has_closed_not_planned_state": "`closed - not planned`" in text,
        "has_labels_applied": "added `invalid`" in text,
        "has_labels_removed": "removed `needs triage`" in text,
        "has_rollup_permalink": "Rollup entry: [permalink](" in text,
        "has_closing_comment_permalink": "Closing comment: [permalink](" in text,
        "has_board_status": "Project board: archived" in text,
        "has_gmail_draft_ref": "Reporter draft: " in text,
        "has_handoff_line": "> Terminal disposition." in text,
        "has_bare_issue_numbers": bool(bare),
    }


EXPECTED_RECAP = dict.fromkeys(
    (
        "has_tracker_link", "has_closed_not_planned_state", "has_labels_applied", "has_labels_removed",
        "has_rollup_permalink", "has_closing_comment_permalink", "has_board_status", "has_gmail_draft_ref",
        "has_handoff_line",
    ),
    True,
) | {"has_bare_issue_numbers": False}  # fmt: skip


def closed(number: int, rollup: int, close_id: int, scope: str, draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": number,
        "labels_added": ["invalid"],
        "labels_removed": ["needs triage", scope],
        "rollup_url": f"https://github.com/{TRACKER}/issues/{number}#issuecomment-{rollup}",
        "close_url": f"https://github.com/{TRACKER}/issues/{number}#issuecomment-{close_id}",
        "board": {"archived": True, "item_id": "PVTI_kwDO_abc123"},
        "draft": draft,
    }


def test_step7_case_1_security_imported_with_draft(capsys, tmp_path):
    draft = {"id": "r8234fab9cc1e2d3f", "url": "https://mail.google.com/mail/u/0/#drafts/r8234fab9cc1e2d3f"}
    _, out = run(
        capsys,
        tmp_path,
        "render-recap",
        {"tracker": TRACKER, "closed": [closed(312, 9001, 9050, "airflow", draft)]},
    )
    assert recap_properties(out["text"], out["bare_refs"]) == EXPECTED_RECAP
    assert "`r8234fab9cc1e2d3f`" in out["text"]


def test_step7_case_2_pr_imported_no_draft(capsys, tmp_path):
    draft = {"reason": "PR-imported tracker; no reporter to notify per the reporter credit policy"}
    _, out = run(
        capsys,
        tmp_path,
        "render-recap",
        {"tracker": TRACKER, "closed": [closed(341, 9041, 9090, "providers", draft)]},
    )
    assert recap_properties(out["text"], out["bare_refs"]) == EXPECTED_RECAP
    assert "Reporter draft: none — PR-imported tracker" in out["text"]
