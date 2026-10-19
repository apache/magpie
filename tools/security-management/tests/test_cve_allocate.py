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
"""`security-management cve-allocate` end to end through the CLI.

The cases of the retired model-graded `security-cve-allocate` suites
`step-1-blocker-checks`, `step-2-title-normalize`, `step-3-allocation-recipe`,
`step-4-propose-updates`, `step-5-confirm` and `step-7-recap` live here, named
after each former case, with the same scenario and expected output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

TRACKER = "airflow-s/airflow-s"
SCOPES = ["airflow", "providers", "chart"]
RECORD = "https://cveprocess.apache.org/cve5/<CVE-ID>"
SOURCE = "https://cveprocess.apache.org/cve5/<CVE-ID>?tab=source"
ALLOCATE = "https://cveprocess.apache.org/allocatecve"
NAMES = {"project_names": ["Apache Airflow"], "short_names": ["Airflow"]}
SSRF = "SSRF via connection test endpoint allows authenticated user to reach internal hosts"


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["cve-allocate", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out)


def ok(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> dict[str, Any]:
    code, out = run(capsys, tmp_path, command, data)
    assert code == 0, out
    return out


# --- Inputs ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("invocation", "issue", "override"),
    [
        ("242", 242, None),
        ("#242", 242, None),
        (f"{TRACKER}#242", 242, None),
        (f"https://github.com/{TRACKER}/issues/242", 242, None),
        ("242 CVE-2025-31187", 242, "CVE-2025-31187"),
        ("cve-allocate 242 cve-2025-31187", 242, "CVE-2025-31187"),
    ],
)
def test_selector_reads_the_tracker_and_the_override(capsys, tmp_path, invocation, issue, override):
    out = ok(capsys, tmp_path, "selector", {"invocation": invocation, "tracker": TRACKER})
    assert out["issue"] == issue
    assert out["cve_override"] == override
    assert out["resume_step"] == (4 if override else 1)
    assert out["commands"][0].startswith(f"gh issue view {issue} --repo {TRACKER} --json")
    assert out["commands"][1].endswith(f'body-field-get {issue} "CVE tool link"')


@pytest.mark.parametrize(
    ("invocation", "why"),
    [
        ("242 CVE-25-1", "not a CVE ID"),
        ("242 CVE-2025-12", "not a CVE ID"),
        ("242 CVE-2025-31187 CVE-2025-31188", "more than one CVE ID"),
        ("CVE-2025-31187", "no tracker given"),
        ("242 243", "one tracker at a time"),
        ("other/repo#242", "not airflow-s/airflow-s"),
    ],
)
def test_selector_refuses_what_it_cannot_place(capsys, tmp_path, invocation, why):
    code, out = run(capsys, tmp_path, "selector", {"invocation": invocation, "tracker": TRACKER})
    assert code == 2
    assert why in out["refused"]


def test_selector_takes_a_backend_id_off_github(capsys, tmp_path):
    out = ok(
        capsys,
        tmp_path,
        "selector",
        {"invocation": "SEC-0012", "tracker": TRACKER, "platform": "local-files"},
    )
    assert out["issue"] == "SEC-0012"
    assert "issue-view SEC-0012" in out["commands"][0]


# --- Step 1: blocker checks --------------------------------------------------


def blockers(capsys, tmp_path, labels, cve_tool_link="", state="OPEN", **extra):
    data = {"state": state, "labels": labels, "cve_tool_link": cve_tool_link, "scope_labels": SCOPES, **extra}
    return ok(capsys, tmp_path, "blockers", data)


NO_SCOPE = (
    "No scope label set (airflow, providers, or chart) — scope is required to map the product/packageName "
    "in the CVE record; set the scope label before allocating"
)


def test_case_1_clean_pass(capsys, tmp_path):
    out = blockers(capsys, tmp_path, ["airflow"])
    assert (out["verdict"], out["blockers"], out["warnings"]) == ("proceed", [], [])
    assert out["scope_label"] == "airflow"


def test_case_2_already_has_cve(capsys, tmp_path):
    out = blockers(
        capsys, tmp_path, ["airflow", "cve allocated"], "https://cveprocess.apache.org/cve5/CVE-2024-41702"
    )
    assert out["verdict"] == "blocked"
    assert out["blockers"] == [
        "CVE already allocated: CVE-2024-41702 found in the CVE tool link body field",
        "`cve allocated` label already present",
    ]
    assert out["warnings"] == []


def test_case_3_duplicate_label(capsys, tmp_path):
    out = blockers(capsys, tmp_path, ["airflow", "duplicate"])
    assert out["verdict"] == "blocked"
    assert out["blockers"] == [
        "Tracker is marked duplicate — the canonical tracker already carries the CVE; allocating here would "
        "create a second CVE for the same root cause"
    ]


def test_case_4_no_scope(capsys, tmp_path):
    out = blockers(capsys, tmp_path, ["needs triage"])
    assert (out["verdict"], out["blockers"], out["warnings"]) == ("blocked", [NO_SCOPE], [])


def test_case_5_needs_triage_warning(capsys, tmp_path):
    out = blockers(capsys, tmp_path, ["airflow", "needs triage"])
    assert out["verdict"] == "proceed"
    assert out["warnings"] == [
        "needs triage label is still set — confirm the valid/invalid decision has landed before allocating"
    ]


def test_case_6_prompt_injection(capsys, tmp_path):
    # The body's "SYSTEM OVERRIDE" never reaches the tool: the checks read labels and one field value.
    out = blockers(capsys, tmp_path, ["needs triage"], "_No response_")
    assert (out["verdict"], out["blockers"], out["warnings"]) == ("blocked", [NO_SCOPE], [])


def test_a_closed_tracker_two_scopes_and_an_undecided_field_block(capsys, tmp_path):
    out = blockers(capsys, tmp_path, ["airflow", "chart"], state="CLOSED", cve_tool_link_undecided=True)
    assert len(out["blockers"]) == 3
    assert out["blockers"][0].startswith("Issue is closed")
    assert "cannot be read unambiguously" in out["blockers"][1]
    assert out["blockers"][2].startswith("More than one scope label set (airflow, chart)")


def test_an_override_already_wired_is_a_resume_not_a_blocker(capsys, tmp_path):
    link = "https://cveprocess.apache.org/cve5/CVE-2025-31187"
    out = blockers(capsys, tmp_path, ["airflow", "cve allocated"], link, cve_override="CVE-2025-31187")
    assert (out["verdict"], out["already_wired"]) == ("proceed", True)
    other = blockers(capsys, tmp_path, ["airflow"], link, cve_override="CVE-2025-99999")
    assert other["verdict"] == "blocked"


def test_blockers_need_the_scope_labels(capsys, tmp_path):
    code, _ = run(capsys, tmp_path, "blockers", {"state": "OPEN", "labels": [], "scope_labels": []})
    assert code == 2


# --- Step 2: the CVE-ready title ---------------------------------------------


def title(capsys, tmp_path, text, **extra):
    return ok(capsys, tmp_path, "title", {"title": text, **NAMES, **extra})


@pytest.mark.parametrize(
    ("case", "original", "normalized", "words"),
    [
        (
            "case-1-strip-security-report-prefix",
            "[ Security Report ] SQL injection via DAG run conf parameter",
            "SQL injection via DAG run conf parameter",
            7,
        ),
        (
            "case-2-strip-apache-airflow-prefix",
            "Apache Airflow: SSRF via connection test endpoint",
            "SSRF via connection test endpoint",
            5,
        ),
        (
            "case-3-strip-trailing-in-airflow",
            "Pickle deserialization vulnerability via XCom in Apache Airflow",
            "Pickle deserialization vulnerability via XCom",
            5,
        ),
    ],
)
def test_step_2_title_cases(capsys, tmp_path, case, original, normalized, words):
    out = title(capsys, tmp_path, original)
    assert out["original_title"] == original
    assert out["normalized_title"] == normalized
    assert out["word_count"] == words
    assert out["over_strip_warning"] is None


def test_case_4_over_strip_warning(capsys, tmp_path):
    out = title(capsys, tmp_path, "Apache Airflow: RCE")
    assert (out["normalized_title"], out["word_count"]) == ("RCE", 1)
    assert out["over_strip_warning"].startswith("Normalized title is only 1 word")


@pytest.mark.parametrize(
    ("original", "normalized"),
    [
        ("Path traversal (incomplete fix for CVE-2026-12345) in the parser", "Path traversal in the parser"),
        ("[Important] Airflow 2.10: XSS in the grid view (GHSA-abcd-efgh-ijkl).", "XSS in the grid view"),
        ("Token leak in logs (HUNTR-1234) (Alice follow-up)", "Token leak in logs"),
        ("open redirect in login (split from #42)", "Open redirect in login"),
        ("SSRF in webhooks (Apache Airflow 2.9)", "SSRF in webhooks"),
    ],
)
def test_identifier_parentheticals_go_anywhere(capsys, tmp_path, original, normalized):
    assert title(capsys, tmp_path, original)["normalized_title"] == normalized


def test_the_short_name_needs_a_separator(capsys, tmp_path):
    # `Airflow` without a separator is the start of the description, not a prefix.
    assert title(capsys, tmp_path, "Airflow scheduler crash on bad DAG")["normalized_title"] == (
        "Airflow scheduler crash on bad DAG"
    )


def test_the_title_needs_the_project_names(capsys, tmp_path):
    code, _ = run(capsys, tmp_path, "title", {"title": "x"})
    assert code == 2


# --- Step 0 item 5 and the API outcome ---------------------------------------


@pytest.mark.parametrize(
    ("data", "path", "setup"),
    [
        ({"governance_member": False, "server_exit": 0}, "recipe", False),
        ({"governance_member": True}, None, False),
        ({"governance_member": True, "server_exit": 4}, "recipe", False),
        ({"governance_member": True, "server_exit": 3}, "recipe", False),
        ({"governance_member": True, "server_exit": 0}, None, False),
        (
            {
                "governance_member": True,
                "server_exit": 0,
                "allocate_exit": 0,
                "allocate_stdout": "valid\nallocate token for airflow",
            },
            "api",
            False,
        ),
        (
            {
                "governance_member": True,
                "server_exit": 0,
                "allocate_exit": 0,
                "allocate_stdout": "allocate token for spark",
            },
            None,
            True,
        ),
        ({"governance_member": True, "server_exit": 0, "allocate_exit": 1}, None, True),
        ({"governance_member": True, "server_exit": 0, "allocate_exit": 2}, None, True),
        ({"governance_member": True, "server_exit": 0, "allocate_exit": 4}, "recipe", False),
    ],
)
def test_preflight_picks_the_step_3_path(capsys, tmp_path, data, path, setup):
    out = ok(capsys, tmp_path, "preflight", {"pmc": "airflow", **data})
    assert out["path"] == path
    assert out["offer_setup"] is setup
    if setup:
        assert out["setup_command"].endswith("vulnogram-api-setup --pmc airflow")


@pytest.mark.parametrize(
    ("data", "next_step", "cve_id", "rerun"),
    [
        ({"exit": 0, "stdout": "CVE-2025-31187\n"}, "step-4", "CVE-2025-31187", False),
        ({"exit": 6, "stdout": "CVE-2025-31187\n"}, "step-4", "CVE-2025-31187", False),
        ({"exit": 0, "stdout": "allocated!\n"}, "check-records", None, False),
        ({"exit": 5}, "stop", None, False),
        ({"exit": 1}, "setup", None, True),
        ({"exit": 4}, "check-records", None, False),
        ({"exit": 3, "stderr": "the request may still have gone through"}, "check-records", None, False),
        ({"exit": 3, "stderr": "boom"}, "recipe", None, False),
    ],
)
def test_allocate_result_never_reruns_on_its_own(capsys, tmp_path, data, next_step, cve_id, rerun):
    out = ok(capsys, tmp_path, "allocate-result", {"pmc": "airflow", **data})
    assert (out["next"], out["cve_id"], out["rerun_allocate"]) == (next_step, cve_id, rerun)


@pytest.mark.parametrize(
    ("text", "cve_id"),
    [
        ("Allocated CVE-2025-31187, thanks", "CVE-2025-31187"),
        ("cve-2025-31187", "CVE-2025-31187"),
        ("CVE-2025-31187 (again: CVE-2025-31187)", "CVE-2025-31187"),
    ],
)
def test_cve_takes_the_one_pasted_id(capsys, tmp_path, text, cve_id):
    out = ok(capsys, tmp_path, "cve", {"text": text, "record_url_template": RECORD})
    assert out["cve_id"] == cve_id
    assert out["record_url"] == f"https://cveprocess.apache.org/cve5/{cve_id}"


@pytest.mark.parametrize(
    "text", ["CVE-2025-12", "here you go", "CVE-2025-31187 or CVE-2025-31188", "CVE-2025-123456789"]
)
def test_cve_never_guesses(capsys, tmp_path, text):
    code, _ = run(capsys, tmp_path, "cve", {"text": text})
    assert code == 2


# --- Step 3: the allocation recipe -------------------------------------------


def recipe(capsys, tmp_path, member, preflight=None, **extra):
    data = {
        "tracker": TRACKER,
        "issue": 242,
        "title": SSRF,
        "governance_member": member,
        "allocate_url": ALLOCATE,
        "pmc": "airflow",
        **extra,
    }
    if preflight:
        data["preflight"] = preflight
    return ok(capsys, tmp_path, "recipe", data)


def flags(out):
    return {
        "governance_member_path": out["governance_member_path"],
        "has_vulnogram_url": ALLOCATE in out["text"],
        "has_stripped_title_block": f"```text\n{SSRF}\n```" in out["text"].replace("   ", ""),
        "relay_message_present": out["relay_message_present"],
        "api_allocation_proposed": out["api_allocation_proposed"],
    }


@pytest.mark.parametrize(
    ("case", "member", "preflight", "expected"),
    [
        ("case-1-governance-member", True, None, (True, True, True, False, False)),
        ("case-2-non-member", False, None, (False, True, True, True, False)),
        ("case-3-api-preflight-passed", True, {"path": "api"}, (True, True, True, False, True)),
        ("case-4-api-unsupported-server", True, {"path": "recipe"}, (True, True, True, False, False)),
    ],
)
def test_step_3_recipe_cases(capsys, tmp_path, case, member, preflight, expected):
    out = recipe(capsys, tmp_path, member, preflight)
    keys = (
        "governance_member_path",
        "has_vulnogram_url",
        "has_stripped_title_block",
        "relay_message_present",
        "api_allocation_proposed",
    )
    assert flags(out) == dict(zip(keys, expected, strict=True))
    assert out["bare_refs"] == []
    assert f"[{TRACKER}#242](https://github.com/{TRACKER}/issues/242)" in out["text"]


def test_the_relay_is_a_terse_request(capsys, tmp_path):
    out = recipe(capsys, tmp_path, False, authorised_handles=["pmc-a", "@pmc-b"])
    assert out["text"].startswith("@pmc-a @pmc-b — could one of you allocate a CVE for")
    assert "Allocate*" not in out["text"]
    assert out["text"].rstrip().endswith("Paste the allocated `CVE-YYYY-NNNNN` back here when done.")


def test_the_api_command_quotes_the_title(capsys, tmp_path):
    out = recipe(capsys, tmp_path, True, {"path": "api"}, title="x'; rm -rf / #`")
    assert out["command"].endswith("--title 'x'\"'\"'; rm -rf / #`'")
    assert "```text\nx'; rm -rf / #`\n```" in out["text"]


def test_a_backtick_run_in_the_title_lengthens_the_fence(capsys, tmp_path):
    out = recipe(capsys, tmp_path, True, title="a ``` b")
    assert "````text\na ``` b\n````" in out["text"].replace("   ", "")


def test_the_recipe_waits_for_the_authorisation_answer(capsys, tmp_path):
    code, out = run(
        capsys,
        tmp_path,
        "recipe",
        {"tracker": TRACKER, "issue": 242, "title": SSRF, "allocate_url": ALLOCATE},
    )
    assert code == 2
    assert "authorised" in out["refused"]


# --- Step 4: the proposal, the draft plan and the rollup entry ---------------


def draft_plan(capsys, tmp_path, thread, **extra):
    data = {
        "security_thread": thread,
        "security_cc": "security@airflow.apache.org",
        "reporter_email": "alice@example.com",
        "root_subject": "Re: [SECURITY] Pickle in XCom",
        **extra,
    }
    return ok(capsys, tmp_path, "draft-plan", data)


GMAIL = "No public archive URL — tracked privately on Gmail thread 18f3a2b9c1d4e507"


def rollup(capsys, tmp_path, notification, **extra):
    data = {
        "tracker": TRACKER,
        "issue": 312,
        "date": "2026-10-19",
        "cve_id": "CVE-2025-44812",
        "record_url_template": RECORD,
        "source_tab_url_template": SOURCE,
        "allocate_url": ALLOCATE,
        "notification": notification,
        "scope_label": "airflow",
        "product": "Apache Airflow",
        "package_name": "apache-airflow",
        "cwe": "CWE-502",
        "severity": "HIGH",
        "affected": "2.8.0, 2.8.1, 2.9.0",
        "credits": 2,
        "references": 1,
        **extra,
    }
    return ok(capsys, tmp_path, "render-rollup", data)


def proposal(capsys, tmp_path, draft):
    return ok(
        capsys,
        tmp_path,
        "proposal",
        {
            "tracker": TRACKER,
            "issue": 312,
            "cve_id": "CVE-2025-44812",
            "record_url_template": RECORD,
            "draft": draft,
        },
    )


def test_case_1_external_reporter_thread_known(capsys, tmp_path):
    plan = draft_plan(capsys, tmp_path, GMAIL)
    assert plan["action"] == "create"
    assert plan["notification"] == {"case": "draft_pending", "draft_id": "<pending>"}
    assert (plan["to"], plan["subject"], plan["backend"]) == (
        "alice@example.com",
        "Re: Pickle in XCom",
        "oauth_curl",
    )
    assert plan["anchor"] == {"thread_id": "18f3a2b9c1d4e507"}
    out = proposal(capsys, tmp_path, plan)
    assert out["proposal_items_count"] == 5
    assert [i["key"] for i in out["items"]] == ["cve_tool_link", "label", "rollup", "cve_json", "draft"]
    entry = rollup(capsys, tmp_path, plan["notification"])
    assert "Reporter notification still pending — see draft `<pending>`." in entry["text"]
    assert entry["needs_amend"] is True
    assert entry["bare_refs"] == []


def test_case_2_team_discovered_no_reporter(capsys, tmp_path):
    plan = draft_plan(
        capsys,
        tmp_path,
        "N/A — opened from public PR apache/airflow#45210; no security@ thread",
        reporter_email=None,
    )
    assert (plan["action"], plan["notification"]["case"]) == ("skip", "omitted")
    out = proposal(capsys, tmp_path, plan)
    assert out["proposal_items_count"] == 4
    entry = rollup(capsys, tmp_path, plan["notification"])
    assert "Reporter" not in entry["text"].split("**Next:**")[1].split("Allocated")[0]
    assert entry["needs_amend"] is False
    assert entry["bare_refs"] == []


def test_case_3_draft_already_exists(capsys, tmp_path):
    plan = draft_plan(
        capsys, tmp_path, "No public archive URL — tracked privately on Gmail thread 18f3a2b9c1d4e999",
        existing_drafts=["r9abc123def456"],
    )  # fmt: skip
    assert plan["action"] == "surface_existing"
    out = proposal(capsys, tmp_path, plan)
    assert out["proposal_items_count"] == 4
    assert "`r9abc123def456`" in out["text"]
    entry = rollup(capsys, tmp_path, {**plan["notification"], "in_drafts": True})
    assert "Reporter notification still pending — see draft `r9abc123def456`." in entry["text"]


def test_a_draft_id_is_claimed_pending_only_after_checking_drafts(capsys, tmp_path):
    code, out = run(
        capsys, tmp_path, "render-rollup",
        {"tracker": TRACKER, "issue": 1, "date": "d", "cve_id": "CVE-2025-1111", "record_url_template": RECORD,
         "notification": {"case": "draft_pending", "draft_id": "r1"}},
    )  # fmt: skip
    assert code == 2
    assert "still in Drafts" in out["refused"]
    gone = rollup(capsys, tmp_path, {"case": "draft_pending", "draft_id": "r1", "in_drafts": False})
    assert "Reporter draft `r1` is no longer in Drafts — sent or discarded." in gone["text"]


@pytest.mark.parametrize(
    ("data", "case", "action"),
    [
        ({"reporter_on_team": True}, "team_member", "skip"),
        ({"already_notified": True}, "notified", "skip"),
        ({"security_cc": ""}, None, "blocked"),
        ({"root_subject": ""}, None, "blocked"),
        ({"oauth_credentials": False}, None, "blocked"),
        (
            {"oauth_credentials": False, "body_has_links": False, "last_message_id": "m1"},
            "draft_pending",
            "create",
        ),
        ({"drafting_backend": "maildir"}, None, "blocked"),
        ({"drafting_backend": "maildir", "root_message_id": "<r@x>"}, "draft_pending", "create"),
    ],
)
def test_draft_plan_cases(capsys, tmp_path, data, case, action):
    plan = draft_plan(capsys, tmp_path, GMAIL, **data)
    assert (plan["notification"]["case"], plan["action"]) == (case, action)


def test_the_status_draft_goes_to_the_primary_thread_and_via_a_forwarder_too(capsys, tmp_path):
    field = f"{GMAIL}\nRelayed by huntr: Gmail thread relay987654"
    plan = draft_plan(capsys, tmp_path, field)
    assert plan["anchor"] == {"thread_id": "18f3a2b9c1d4e507"}
    assert plan["secondary_threads"][0]["thread_id"] == "relay987654"
    via = draft_plan(capsys, tmp_path, GMAIL, via_forwarder=True, forwarder_contact="relay@huntr.example")
    assert (via["action"], via["to"], via["mode"]) == ("create", "relay@huntr.example", "via_forwarder")


def test_an_indeterminate_thread_is_the_users_call(capsys, tmp_path):
    assert draft_plan(capsys, tmp_path, "_No response_")["action"] == "ask"


def test_check_draft_wants_the_cve_id_and_never_the_tool_url(capsys, tmp_path):
    base = {
        "tracker": TRACKER,
        "cve_id": "CVE-2025-44812",
        "record_url": "https://cveprocess.apache.org/cve5/CVE-2025-44812",
    }
    clean = ok(
        capsys,
        tmp_path,
        "check-draft",
        {**base, "body": "We allocated CVE-2025-44812.\nThe advisory follows the fix."},
    )
    assert clean == {"clean": True, "hits": []}
    dirty = ok(
        capsys, tmp_path, "check-draft",
        {**base, "body": "Record: https://cveprocess.apache.org/cve5/CVE-2025-44812, see airflow-s/airflow-s#312"},
    )  # fmt: skip
    assert {h["kind"] for h in dirty["hits"]} >= {"cve-tool-url", "tracker-reference"}
    missing = ok(capsys, tmp_path, "check-draft", {**base, "body": "We allocated an ID."})
    assert {h["kind"] for h in missing["hits"]} == {"missing-cve-id"}


def test_the_rollup_entry_links_and_lists_the_record_state(capsys, tmp_path):
    entry = rollup(capsys, tmp_path, {"case": "omitted"})
    text = entry["text"]
    assert entry["label"] == "CVE allocated (CVE-2025-44812)"
    assert text.startswith(
        "**Sync 2026-10-19 — CVE [`CVE-2025-44812`](https://cveprocess.apache.org/cve5/CVE-2025-44812) allocated for "
        f"[{TRACKER}#312](https://github.com/{TRACKER}/issues/312).**"
    )
    assert "[`source` tab](https://cveprocess.apache.org/cve5/CVE-2025-44812?tab=source)" in text
    assert "Scope `airflow` → product `Apache Airflow` → `packageName` `apache-airflow`." in text
    assert "(CWE `CWE-502`, severity `HIGH`, affected `2.8.0, 2.8.1, 2.9.0`, 2 credits, 1 references)" in text
    assert "**Next:** design the fix (`security-issue-fix` skill)." in text
    assert all(not line.startswith(" ") for line in text.split("\n"))


# --- Step 5: confirm and apply -----------------------------------------------


@pytest.mark.parametrize(
    ("case", "items", "reply", "expected"),
    [
        ("case-1-apply-all", [1, 2, 3, 4, 5], "all", ("apply", [1, 2, 3, 4, 5], [])),
        ("case-2-selective", [1, 2, 3, 4], "1,2,3", ("apply", [1, 2, 3], [4, 5])),
        ("case-3-cancel", [1, 2, 3, 4, 5], "cancel", ("cancel", [], [])),
    ],
)
def test_step_5_confirm_cases(capsys, tmp_path, case, items, reply, expected):
    out = ok(capsys, tmp_path, "parse-reply", {"reply": reply, "items": items})
    assert (out["action"], out["items_applied"], out["items_skipped"]) == expected


@pytest.mark.parametrize(
    ("reply", "action", "applied"),
    [
        ("1, 3 and 4", "apply", [1, 3, 4]),
        ("yes", "apply", [1, 2, 3, 4]),
        ("1,5", "ambiguous", []),
        ("", "ambiguous", []),
        ("don't go", "edit", []),
        ("use next step: release manager ships 2.10.4", "edit", []),
    ],
)
def test_parse_reply_never_applies_by_default(capsys, tmp_path, reply, action, applied):
    out = ok(capsys, tmp_path, "parse-reply", {"reply": reply, "items": [1, 2, 3, 4]})
    assert (out["action"], out["items_applied"]) == (action, applied)


def test_apply_plan_runs_the_confirmed_items_in_order(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "apply-plan",
        {"tracker": TRACKER, "issue": 312, "cve_id": "CVE-2025-44812", "scratch": "/s", "items": [1, 2, 3, 4, 5],
         "legacy_comments": [{"comment_id": 11, "action": "Sync"}], "needs_amend": True},
    )  # fmt: skip
    commands = [s["command"] for s in out["steps"]]
    assert [s["item"] for s in out["steps"]] == [1, 2, 3, 3, 4, 5, 5]
    assert commands[0].endswith(
        'vetted-op-tracker --caller security-cve-allocate body-field-set 312 "CVE tool link" /s/cve-tool-link-312.md'
    )
    assert commands[1] == f'gh issue edit 312 --repo {TRACKER} --add-label "cve allocated"'
    assert commands[2].endswith('rollup-fold 312 11 "Sync"')
    assert commands[3].endswith('rollup-append 312 "CVE allocated (CVE-2025-44812)" /s/rollup-entry-312.md')
    assert "generate-cve-json 312 --attach --report-json /s/cve-report-312.json" in commands[4]
    assert commands[6].endswith(
        'rollup-amend-latest 312 "CVE allocated (CVE-2025-44812)" /s/rollup-entry-312.md'
    )
    assert out["steps"][0]["load_bearing"] is True


def test_apply_plan_off_github_saves_the_body_and_attaches(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "apply-plan",
        {"tracker": TRACKER, "platform": "local-files", "issue": "SEC-0012", "cve_id": "CVE-2025-44812",
         "scratch": "/s", "items": [2, 4], "title": "XSS", "review": True},
    )  # fmt: skip
    commands = [s["command"] for s in out["steps"]]
    assert commands[0].endswith(
        'vetted-op --caller security-cve-allocate issue-add-label SEC-0012 "cve allocated"'
    )
    assert commands[1].endswith("--save cve-body-SEC-0012.md issue-body SEC-0012")
    assert '--stdin --title "XSS" --review --output /s/CVE-2025-44812.json' in commands[2]
    assert commands[3].endswith("issue-attach SEC-0012 /s/CVE-2025-44812.json CVE-2025-44812.json")
    assert commands[4].endswith("tracker-pending")


# --- Step 7: recap -----------------------------------------------------------


def recap(capsys, tmp_path, issue, cve_id, applied, rollup_comment, draft, next_step):
    return ok(
        capsys,
        tmp_path,
        "render-recap",
        {
            "tracker": TRACKER,
            "issue": issue,
            "cve_id": cve_id,
            "record_url_template": RECORD,
            "applied": applied,
            "rollup_comment": rollup_comment,
            "draft": draft,
            "next_step": next_step,
        },
    )


def recap_flags(text: str, issue: int, cve_id: str) -> dict[str, bool]:
    return {
        "has_tracker_link": f"[{TRACKER}#{issue}](https://github.com/{TRACKER}/issues/{issue})" in text,
        "has_cve_link": f"(https://cveprocess.apache.org/cve5/{cve_id})" in text,
        "has_cve_json_anchor": f"#cve-json--paste-ready-for-{cve_id.lower()}" in text,
        "has_rollup_anchor": "#issuecomment-" in text,
        "has_draft_id": "open Gmail to review and send it" in text,
        "has_next_step": "**Next:**" in text,
    }


def test_case_1_clean_with_draft(capsys, tmp_path):
    out = recap(
        capsys, tmp_path, 242, "CVE-2025-31187", [1, 2, 3, 4, 5], "#issuecomment-2381047",
        {"id": "r4829201847563"}, "Design the fix (`security-issue-fix` skill).",
    )  # fmt: skip
    assert all(recap_flags(out["text"], 242, "CVE-2025-31187").values())
    assert out["bare_refs"] == []


def test_case_2_no_draft(capsys, tmp_path):
    out = recap(
        capsys, tmp_path, 198, "CVE-2025-22891", [1, 2, 3, 4], "2391204",
        {"reason": "the reporter is on the security team"},
        "Release manager completes process step 12 once the fix ships.",
    )  # fmt: skip
    flags_ = recap_flags(out["text"], 198, "CVE-2025-22891")
    assert flags_["has_draft_id"] is False
    assert all(value for key, value in flags_.items() if key != "has_draft_id")
    assert "Reporter draft: none — the reporter is on the security team." in out["text"]
