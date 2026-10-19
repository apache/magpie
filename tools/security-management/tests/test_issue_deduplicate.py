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
"""`security-management issue-deduplicate` end to end through the CLI.

The cases of the retired model-graded `security-issue-deduplicate` suites
`step-1-classify`, `step-2-extract-fields`, `step-3-merge-body`,
`step-4-rollup-entries`, `step-5-confirm` and `step-6-recap` live here, named
after each former case, with the same scenario and expected output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from github_body_field import parser as gbf

from security_management.cli import main

TRACKER = "airflow-s/airflow-s"
SCOPES = ["airflow", "providers", "chart"]
RECORD = "https://cveprocess.apache.org/cve5/<CVE-ID>"
FIELDS = (
    ("The issue description", "issue_description"),
    ("Short public summary for publish", "public_summary"),
    ("Affected versions", "affected_versions"),
    ("Security mailing list thread", "mailing_thread"),
    ("Public advisory URL", "public_advisory_url"),
    ("Reporter credited as", "reporter_credit"),
    ("PR with the fix", "pr_with_fix"),
    ("Remediation developer", "remediation_developer"),
    ("CWE", "cwe"),
    ("Severity", "severity"),
    ("CVE tool link", "cve_link"),
)


def body(**values: str) -> str:
    return "\n\n".join(f"### {h}\n\n{values.get(role) or '_No response_'}" for h, role in FIELDS) + "\n"


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["issue-deduplicate", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out)


def ok(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> dict[str, Any]:
    code, out = run(capsys, tmp_path, command, data)
    assert code == 0, out
    return out


# --- Inputs ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("invocation", "keep", "drop"),
    [
        ("dedupe #42 67", 42, 67),
        ("42 67", 42, 67),
        (f"{TRACKER}#42 into {TRACKER}#67", 42, 67),
        (f"https://github.com/{TRACKER}/issues/42 #67", 42, 67),
    ],
)
def test_selector_reads_keep_then_drop(capsys, tmp_path, invocation, keep, drop):
    out = ok(capsys, tmp_path, "selector", {"invocation": invocation, "tracker": TRACKER})
    assert (out["keep"], out["drop"]) == (keep, drop)
    assert out["commands"][0].startswith(f"gh issue view {keep} --repo {TRACKER} --json")


@pytest.mark.parametrize(
    ("invocation", "why"),
    [
        ("dedupe #42", "the kept one first"),
        ("dedupe #42 #42", "the kept one first"),
        ("dedupe 42 67 68", "exactly two"),
        ("dedupe 42-44", "not a range"),
        ("dedupe other/repo#42 67", "not airflow-s/airflow-s"),
    ],
)
def test_selector_never_guesses_the_kept_side(capsys, tmp_path, invocation, why):
    code, out = run(capsys, tmp_path, "selector", {"invocation": invocation, "tracker": TRACKER})
    assert code == 2
    assert why in out["refused"]


# --- Step 1: classify --------------------------------------------------------


def side(number, labels, state="OPEN", cve_link="", cve_state=None):
    return {"number": number, "labels": labels, "state": state, "cve_link": cve_link, "cve_state": cve_state}


def classify(capsys, tmp_path, keep, drop):
    return ok(
        capsys, tmp_path, "classify", {"tracker": TRACKER, "scope_labels": SCOPES, "keep": keep, "drop": drop}
    )


def test_case_1_clean_pass(capsys, tmp_path):
    out = classify(capsys, tmp_path, side(42, ["airflow"]), side(67, ["airflow"]))
    assert (out["verdict"], out["blocker"], out["blocker_detail"]) == ("proceed", None, None)
    assert out["scope_label"] == "airflow"


def test_case_2_scope_mismatch(capsys, tmp_path):
    out = classify(capsys, tmp_path, side(42, ["airflow"]), side(67, ["providers"]))
    assert (out["verdict"], out["blocker"]) == ("blocked", "scope_mismatch")
    assert out["blocker_detail"] == (
        f"Kept tracker [{TRACKER}#42](https://github.com/{TRACKER}/issues/42) has scope label 'airflow'; "
        f"drop tracker [{TRACKER}#67](https://github.com/{TRACKER}/issues/67) has scope label 'providers'. "
        "Different scopes must not be merged — use security-issue-sync scope-split flow instead."
    )


def test_case_3_closed_tracker(capsys, tmp_path):
    out = classify(capsys, tmp_path, side(42, ["airflow"]), side(67, ["airflow"], state="CLOSED"))
    assert (out["verdict"], out["blocker"]) == ("blocked", "closed_tracker")
    assert "is already closed" in out["blocker_detail"]


def test_case_4_already_duplicate(capsys, tmp_path):
    out = classify(capsys, tmp_path, side(42, ["airflow"]), side(67, ["airflow", "duplicate"]))
    assert (out["verdict"], out["blocker"]) == ("blocked", "already_duplicate")
    assert "partial merge" in out["blocker_detail"]


C1 = "https://cveprocess.apache.org/cve5/CVE-2025-1111"
C2 = "https://cveprocess.apache.org/cve5/CVE-2025-2222"


@pytest.mark.parametrize(
    ("keep", "drop", "verdict", "blocker", "retract"),
    [
        (
            side(42, ["airflow"]),
            side(67, ["airflow"], cve_link=C2, cve_state="allocated"),
            "blocked",
            "cve_on_drop",
            None,
        ),
        (side(42, ["airflow"], cve_link=C1), side(67, ["airflow"]), "probe", None, None),
        (
            side(42, ["airflow"], cve_link=C1, cve_state="allocated"),
            side(67, ["airflow"]),
            "proceed",
            None,
            None,
        ),
        (
            side(42, ["airflow"], cve_link=C1, cve_state="review-ready"),
            side(67, ["airflow"], cve_link=C2, cve_state="allocated"),
            "proceed",
            None,
            "CVE-2025-2222",
        ),
        (
            side(42, ["airflow"], cve_link=C1, cve_state="allocated"),
            side(67, ["airflow"], cve_link=C2, cve_state="publish-ready"),
            "blocked",
            "drop_further_along",
            None,
        ),
        (
            side(42, ["airflow"], cve_link=C1, cve_state="public"),
            side(67, ["airflow"], cve_link=C2, cve_state="allocated"),
            "blocked",
            "cve_public",
            None,
        ),
        (side(42, []), side(67, ["airflow"]), "blocked", "scope_unclear", None),
    ],
)
def test_classify_applies_the_cve_rules(capsys, tmp_path, keep, drop, verdict, blocker, retract):
    out = classify(capsys, tmp_path, keep, drop)
    assert (out["verdict"], out["blocker"]) == (verdict, blocker)
    if verdict == "proceed":
        assert out["retract"] == retract


# --- Step 2: extract fields --------------------------------------------------


def tracker(number, labels, milestone=None, attachment=False, **values):
    text = body(**values)
    if attachment:
        text += "\n<!-- generate-cve-json: cve=CVE-2025-44812 version=v1 -->\n## CVE JSON\n"
    return {"number": number, "labels": labels, "milestone": milestone, "body": text, "comments": []}


def test_case_1_both_fully_populated(capsys, tmp_path):
    keep = tracker(
        312, ["security issue", "airflow", "cve allocated", "pr merged"], {"title": "Airflow 3.2.2"}, attachment=True,
        issue_description="Pickle in XCom.", affected_versions="apache/airflow 2.8.0, 2.8.1, 2.9.0",
        mailing_thread="No public archive URL — tracked privately on Gmail thread 18f3a2b9c1d4e507",
        reporter_credit="Alice Nguyen (alice@example.com)", pr_with_fix="https://github.com/apache/airflow/pull/52199",
        cwe="CWE-502 Deserialization of Untrusted Data", severity="HIGH",
        cve_link="https://cveprocess.apache.org/cve5/CVE-2025-44812",
    )  # fmt: skip
    drop = tracker(
        328, ["security issue", "airflow", "needs triage"],
        issue_description="Scheduler RCE via XCom.", affected_versions="apache/airflow 2.8.0, 2.8.1",
        mailing_thread="https://lists.apache.org/thread/xyz987abc", reporter_credit="Carlos Mendez (carlos@infosec.io)",
        cwe="CWE-502 Deserialization of Untrusted Data", severity="HIGH",
    )  # fmt: skip
    out = ok(capsys, tmp_path, "fields", {"keep": keep, "drop": drop})
    assert out["keep"]["cve_link"] == "https://cveprocess.apache.org/cve5/CVE-2025-44812"
    assert out["keep"]["has_cve_json_attachment"] is True
    assert out["keep"]["milestone"] == "Airflow 3.2.2"
    assert out["drop"]["cve_link"] is None
    assert out["drop"]["pr_with_fix"] is None
    assert out["drop"]["has_cve_json_attachment"] is False
    assert (out["cwe_conflict"], out["severity_propagation_risk"]) == (False, False)


def test_case_2_drop_side_missing_severity(capsys, tmp_path):
    keep = tracker(
        287,
        ["airflow"],
        issue_description="x",
        cwe="CWE-200 Exposure of Sensitive Information",
        severity="MEDIUM",
    )
    drop = tracker(
        301,
        ["airflow"],
        issue_description="y",
        cwe="CWE-200 Exposure of Sensitive Information",
        severity="HIGH",
    )
    out = ok(capsys, tmp_path, "fields", {"keep": keep, "drop": drop})
    assert (out["cwe_conflict"], out["severity_propagation_risk"]) == (False, True)


def test_case_3_cwe_conflict(capsys, tmp_path):
    keep = tracker(
        319,
        ["airflow"],
        issue_description="x",
        cwe="CWE-918 Server-Side Request Forgery (SSRF)",
        severity="HIGH",
    )
    drop = tracker(
        334,
        ["airflow"],
        issue_description="y",
        cwe="CWE-441 Unintended Proxy or Intermediary",
        severity="HIGH",
    )
    out = ok(capsys, tmp_path, "fields", {"keep": keep, "drop": drop})
    assert (out["cwe_conflict"], out["severity_propagation_risk"]) == (True, False)


def test_fields_refuse_a_body_with_a_repeated_field(capsys, tmp_path):
    keep = tracker(1, ["airflow"], issue_description="x")
    keep["body"] += "\n### CWE\n\nCWE-79\n"
    code, _ = run(
        capsys, tmp_path, "fields", {"keep": keep, "drop": tracker(2, ["airflow"], issue_description="y")}
    )
    assert code == 2


# --- Step 3: the merged body -------------------------------------------------


KEEP_BODY = body(
    issue_description="Authenticated user can send a crafted connection URL to /api/v1/connections/test.",
    public_summary="SSRF via connection test API endpoint allows authenticated users to probe internal hosts.",
    affected_versions=">= 2.9.0, < 2.10.3",
    mailing_thread="Alice Example (initial report): https://lists.apache.org/thread/abc123",
    reporter_credit="Alice Example",
    cwe="CWE-918",
    cve_link="https://cveprocess.apache.org/cve5/CVE-2024-12345",
)
DROP_BODY = body(
    issue_description="The /api/v1/connections/test endpoint follows HTTP redirects to RFC-1918 addresses.",
    public_summary="SSRF via redirect follow in connection test allows authenticated users to reach cloud metadata.",
    affected_versions=">= 2.8.0, < 2.10.3",
    mailing_thread="Bob Researcher (redirect-chain vector): https://lists.apache.org/thread/xyz789",
    reporter_credit="Bob Researcher",
    cwe="CWE-918",
)


def merge(capsys, tmp_path, keep_body=KEEP_BODY, drop_body=DROP_BODY, **extra):
    data = {
        "tracker": TRACKER,
        "date": "2026-10-19",
        "headline": "Same SSRF in the connection test, reached through a redirect chain.",
        "analysis": "Both reports land in the same unvalidated outbound request; the redirect is a second path to it.",
        "keep": {"number": 42, "body": keep_body, "created": "2026-01-01"},
        "drop": {"number": 67, "body": drop_body, "created": "2026-01-05"},
        "merged_summary": "SSRF via the connection test endpoint, directly or through redirects.",
        "affected_versions": ">= 2.8.0, < 2.10.3",
        **extra,
    }
    return run(capsys, tmp_path, "merge-body", data)


def field(text: str, name: str) -> str:
    return gbf.extract_field(text, name).strip()


def test_case_1_basic_merge(capsys, tmp_path):
    code, out = merge(capsys, tmp_path)
    assert code == 0, out
    text = out["text"]
    description = field(text, "The issue description")
    assert description.startswith("Authenticated user can send a crafted connection URL")
    assert (
        f"**Second independent report: [{TRACKER}#67](https://github.com/{TRACKER}/issues/67) — merged on 2026-10-19.**"
        in description
    )
    assert "<details>\n<summary>Full report from Bob Researcher (click to expand)</summary>" in description
    assert "follows HTTP redirects to RFC-1918 addresses." in description
    assert field(text, "Reporter credited as") == "Alice Example\nBob Researcher"
    assert field(text, "Security mailing list thread").split("\n") == [
        "Alice Example (initial report): https://lists.apache.org/thread/abc123",
        "Bob Researcher (redirect-chain vector): https://lists.apache.org/thread/xyz789",
    ]
    assert field(text, "Severity") == "_No response_"
    assert field(text, "CVE tool link") == "https://cveprocess.apache.org/cve5/CVE-2024-12345"
    assert out["blockers"] == []
    assert out["bare_refs"] == []


def test_case_2_version_widening(capsys, tmp_path):
    code, out = merge(capsys, tmp_path)
    assert code == 0
    assert field(out["text"], "Affected versions") == ">= 2.8.0, < 2.10.3"
    code, missing = merge(capsys, tmp_path, affected_versions="")
    assert code == 2
    assert "affected_versions" in missing["refused"]


def test_case_3_cvss_not_propagated(capsys, tmp_path):
    drop = body(
        issue_description="Same SSRF via redirect chain. Reporter assessed CVSS 8.8 (High).\n"
        "Vector: CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H\nSeverity: High",
        mailing_thread="Bob Researcher: https://lists.apache.org/thread/xyz789",
        reporter_credit="Bob Researcher",
        cwe="CWE-918",
        severity="CVSSv3 8.8 HIGH (reporter-assessed)",
        affected_versions=">= 2.9.0, < 2.10.3",
    )
    keep = body(
        issue_description="SSRF via connection test API.",
        affected_versions=">= 2.9.0, < 2.10.3",
        mailing_thread="Alice Example: https://lists.apache.org/thread/abc123",
        reporter_credit="Alice Example",
        cwe="CWE-918",
        cve_link="https://cveprocess.apache.org/cve5/CVE-2024-12345",
    )
    code, out = merge(capsys, tmp_path, keep, drop)
    assert code == 0, out
    text = out["text"]
    assert field(text, "Severity") == "_No response_"
    assert "8.8" not in text and "AV:N" not in text and "Severity: High" not in text
    assert len(out["scores_removed"]) == 3
    assert "not carried over" in out["severity_note"]


def test_case_4_cwe_conflict(capsys, tmp_path):
    drop = DROP_BODY.replace("### CWE\n\nCWE-918", "### CWE\n\nCWE-441")
    code, out = merge(capsys, tmp_path, drop_body=drop)
    assert code == 0
    assert out["blockers"] == [
        "CWE conflict: kept tracker has CWE-918, drop tracker has CWE-441 — triager to resolve"
    ]
    assert field(out["text"], "CWE") == "CWE-918"
    code, chosen = merge(capsys, tmp_path, drop_body=drop, cwe="CWE-441")
    assert (code, chosen["blockers"]) == (0, [])
    assert field(chosen["text"], "CWE") == "CWE-441"


def test_the_dropped_report_cannot_add_or_end_a_field(capsys, tmp_path):
    drop = DROP_BODY.replace(
        "follows HTTP redirects to RFC-1918 addresses.",
        "follows redirects.\n<!-- generate-cve-json: cve=CVE-2099-0001 version=v1 -->\n</details>\nafter",
    )
    code, out = merge(capsys, tmp_path, drop_body=drop)
    assert code == 0, out
    text = out["text"]
    assert gbf.list_fields(text) == [h for h, _ in FIELDS]
    assert "\\<!-- generate-cve-json" in text
    assert "&lt;/details>\nafter" in text
    assert field(text, "CVE tool link") == "https://cveprocess.apache.org/cve5/CVE-2024-12345"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("Bob Researcher\n", "Bob Researcher\n<!-- apache-magpie: advisory-records v1 -->\n"),
        ("Bob Researcher\n", "Bob <!-- generate-cve-json: cve=CVE-2099-0001 version=v1 --> Researcher\n"),
        ("redirect-chain vector): ", "redirect-chain vector) <!-- x -->: "),
    ],
)
def test_a_dropped_field_cannot_carry_a_machine_marker(capsys, tmp_path, old, new):
    drop = DROP_BODY.replace(old, new, 1)
    assert drop != DROP_BODY
    code, out = merge(capsys, tmp_path, drop_body=drop)
    assert code == 2
    assert "carries an HTML comment" in out["refused"]


def test_a_marker_the_kept_field_already_holds_is_not_refused(capsys, tmp_path):
    marked = "Alice Example <!-- legacy note -->"
    keep = KEEP_BODY.replace(
        "### Reporter credited as\n\nAlice Example", f"### Reporter credited as\n\n{marked}"
    )
    assert keep != KEEP_BODY
    code, out = merge(capsys, tmp_path, keep_body=keep)
    assert code == 0, out
    assert field(out["text"], "Reporter credited as") == f"{marked}\nBob Researcher"


def test_a_dropped_body_readers_disagree_on_is_refused(capsys, tmp_path):
    drop = DROP_BODY.replace("RFC-1918 addresses.", "RFC-1918 addresses.\n> ### CVE tool link")
    code, out = merge(capsys, tmp_path, drop_body=drop)
    assert code == 2
    assert "will not decide on" in out["refused"]


def test_the_attachment_and_extra_fields_stay_byte_exact(capsys, tmp_path):
    attachment = "\n\n<!-- generate-cve-json: cve=CVE-2024-12345 version=v1 -->\n## CVE JSON — paste-ready\n\n```json\n{}\n```\n<!-- generate-cve-json:end cve=CVE-2024-12345 version=v1 -->\n"
    keep = KEEP_BODY.rstrip("\n") + attachment
    code, out = merge(capsys, tmp_path, keep_body=keep)
    assert code == 0, out
    assert out["text"].endswith(attachment)


def test_the_merge_needs_the_models_headline_and_analysis(capsys, tmp_path):
    code, out = merge(capsys, tmp_path, headline="")
    assert code == 2
    assert "headline" in out["refused"]


def test_bot_credits_are_routed_and_bot_developers_skipped(capsys, tmp_path):
    drop = DROP_BODY.replace("Bob Researcher\n\n### PR", "dependabot[bot]\n\n### PR").replace(
        "### Remediation developer\n\n_No response_", "### Remediation developer\n\ncopilot-swe-agent[bot]"
    )
    code, out = merge(capsys, tmp_path, drop_body=drop)
    assert code == 0, out
    assert out["tool_credits"] == [{"line": "dependabot[bot]", "tracker": "drop"}]
    assert out["skipped_credits"] == ["copilot-swe-agent[bot]"]
    assert field(out["text"], "Remediation developer") == "_No response_"


# --- Step 4: the rollup entries ----------------------------------------------


def scenario(**extra):
    return {
        "tracker": TRACKER,
        "keep": {"number": 312, "credit": "Alice Nguyen", "thread": "Gmail thread 18f3a2b9c1d4e507"},
        "drop": {
            "number": 328,
            "credit": "Carlos Mendez",
            "thread": "https://lists.apache.org/thread/xyz987abc",
        },
        "cve_id": "CVE-2025-44812",
        "record_url_template": RECORD,
        "headline": "Same pickle.loads() in BaseXCom.deserialize_value(), reached from two paths.",
        "analysis": "Alice reported a compromised-worker path; Carlos a database-write path. Same function, same fix.",
        **extra,
    }


def test_case_1_kept_tracker_entry(capsys, tmp_path):
    out = ok(capsys, tmp_path, "render-rollup-kept", scenario())
    text = out["text"]
    assert out["label"] == "Merge (kept) (from #328)"
    assert text.startswith(
        f"**Merged [{TRACKER}#328](https://github.com/{TRACKER}/issues/328) into this tracker.**"
    )
    assert "- Credits: **Alice Nguyen** + **Carlos Mendez**." in text
    assert "18f3a2b9c1d4e507" in text and "xyz987abc" in text
    assert "**Next:**" in text
    assert (
        "[`CVE-2025-44812`](https://cveprocess.apache.org/cve5/CVE-2025-44812) stays allocated here" in text
    )
    assert out["bare_refs"] == []
    assert all(not line.startswith(" ") for line in text.split("\n"))


def test_case_2_dropped_tracker_entry(capsys, tmp_path):
    out = ok(capsys, tmp_path, "render-rollup-dropped", scenario())
    text = out["text"]
    keep = f"[{TRACKER}#312](https://github.com/{TRACKER}/issues/312)"
    assert out["label"] == "Merge (dropped) (into #312)"
    assert text.startswith(f"**Closing as duplicate of {keep}.**")
    assert f'Full content merged into {keep} as *"Second independent report"*' in text
    assert f"**Next:** all triage and advisory work continues on {keep}." in text
    assert out["bare_refs"] == []


def test_the_kept_entry_needs_both_credits(capsys, tmp_path):
    data = scenario()
    data["drop"]["credit"] = ""
    code, _ = run(capsys, tmp_path, "render-rollup-kept", data)
    assert code == 2


# --- Step 5: confirm and apply -----------------------------------------------


@pytest.mark.parametrize(
    ("case", "reply", "expected"),
    [
        ("case-1-apply-all", "all", ("apply", [1, 2, 3, 4, 5, 6])),
        (
            "case-2-selective",
            "1,2,3,4 — skip 5 and 6 for now, I want to triple-check before closing",
            ("apply", [1, 2, 3, 4]),
        ),
        ("case-3-cancel", "cancel", ("cancel", [])),
    ],
)
def test_step_5_confirm_cases(capsys, tmp_path, case, reply, expected):
    out = ok(capsys, tmp_path, "parse-reply", {"reply": reply, "items": [1, 2, 3, 4, 5, 6]})
    assert (out["action"], out["items_applied"]) == expected


def test_proposal_adds_the_retraction_only_with_two_cves(capsys, tmp_path):
    base = {"tracker": TRACKER, "keep": {"number": 42}, "drop": {"number": 67}, "cve_id": "CVE-2025-1111"}
    one = ok(capsys, tmp_path, "proposal", base)
    assert [i["n"] for i in one["items"]] == [1, 2, 3, 4, 5, 6]
    two = ok(capsys, tmp_path, "proposal", {**base, "retract_cve": "CVE-2025-2222"})
    assert two["items"][-1]["key"] == "retract"
    assert two["bare_refs"] == []


def test_apply_plan_closes_the_dropped_side_only(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "apply-plan",
        {"tracker": TRACKER, "keep": {"number": 42, "legacy_comments": [{"comment_id": 5, "action": "Sync"}]},
         "drop": {"number": 67}, "scratch": "/s", "items": [1, 2, 3, 4, 5, 6, 7], "cve_id": "CVE-2025-1111",
         "retract_cve": "CVE-2025-2222", "date": "2026-10-19"},
    )  # fmt: skip
    commands = [s["command"] for s in out["steps"]]
    assert commands[0] == f"gh issue edit 42 --repo {TRACKER} --body-file /s/dedupe-42-body.md"
    assert commands[1].endswith('rollup-fold 42 5 "Sync"')
    assert commands[2].endswith('rollup-append 42 "Merge (kept) (from #67)" /s/dedupe-42-rollup.md')
    assert commands[3].endswith('rollup-append 67 "Merge (dropped) (into #42)" /s/dedupe-67-rollup.md')
    assert commands[4] == f'gh issue edit 67 --repo {TRACKER} --add-label "duplicate"'
    assert commands[5] == f"gh issue close 67 --repo {TRACKER} --reason 'not planned'"
    assert "generate-cve-json 42 --attach" in commands[6]
    assert "push_update(CVE-2025-1111" in commands[7]
    assert "retract(CVE-2025-2222" in commands[8]


def test_apply_plan_refuses_with_an_open_blocker_or_the_same_tracker(capsys, tmp_path):
    base = {"tracker": TRACKER, "keep": {"number": 42}, "drop": {"number": 67}, "scratch": "/s", "items": [1]}
    assert run(capsys, tmp_path, "apply-plan", {**base, "blockers": ["CWE conflict"]})[0] == 2
    assert run(capsys, tmp_path, "apply-plan", {**base, "drop": {"number": 42}})[0] == 2


# --- Step 6: recap -----------------------------------------------------------


def test_case_1_clean_merge(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "render-recap",
        {"tracker": TRACKER, "keep": {"number": 42}, "drop": {"number": 67}, "applied": [1, 2, 3, 4, 5, 6],
         "credits": "Alice Example\nBob Researcher", "cve_json_url": f"https://github.com/{TRACKER}/issues/42#cve-json"},
    )  # fmt: skip
    assert out["blockers"] == []
    assert f"[{TRACKER}#42](https://github.com/{TRACKER}/issues/42)" in out["text"]
    assert "closed as not planned, labelled `duplicate`" in out["text"]
    assert "- CVE JSON:" in out["text"]
    assert out["bare_refs"] == []


def test_case_2_with_blockers(capsys, tmp_path):
    blockers = [
        "CWE conflict: kept tracker has CWE-502, dropped tracker has CWE-94 — triager must resolve before CVE JSON is finalised.",
        "Credit preference for Dave Security (drop reporter) not yet confirmed — send confirmation request before advisory publication.",
    ]
    out = ok(
        capsys, tmp_path, "render-recap",
        {"tracker": TRACKER, "keep": {"number": 55}, "drop": {"number": 71}, "applied": [1, 2, 3, 4, 5, 6], "blockers": blockers},
    )  # fmt: skip
    assert out["blockers"] == blockers
    assert "**Still to resolve:**" in out["text"]


def test_apply_plan_refuses_a_malformed_cve_id(capsys, tmp_path):
    base = {
        "tracker": TRACKER,
        "keep": {"number": 42},
        "drop": {"number": 67},
        "scratch": "/s",
        "items": [6, 7],
    }
    assert (
        run(capsys, tmp_path, "apply-plan", {**base, "cve_id": "CVE-2025-1111", "retract_cve": "$(id)"})[0]
        == 2
    )
    assert (
        run(capsys, tmp_path, "apply-plan", {**base, "cve_id": "CVE-1; x", "retract_cve": "CVE-2025-2222"})[0]
        == 2
    )
