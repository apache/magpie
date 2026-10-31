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
"""`security-management issue-sync` end to end through the CLI.

The cases of the retired model-graded `security-issue-sync` suites
`step-bulk-selectors`, `step-bulk-orchestration`, `step-3-confirm`,
`step-6-recap` and `step-guardrails` live here, named after each former
case, with the same scenario and expected output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

TRACKER = "airflow-s/airflow-s"
NOW = "2026-10-03T12:00:00Z"
MARKER = "<!-- apache-magpie: status-rollup v1 -->\nproposal"
RECORD = "https://cveprocess.apache.org/cve5/<CVE-ID>"


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["issue-sync", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out)


def ok(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> dict[str, Any]:
    code, out = run(capsys, tmp_path, command, data)
    assert code == 0, out
    return out


def labels(*names: str) -> list[dict[str, str]]:
    return [{"name": n} for n in names]


def node(number, state, updated, names, author, created, body, closed=None):
    return {
        "number": number,
        "state": state,
        "closedAt": closed,
        "updatedAt": updated,
        "labels": {"nodes": labels(*names)},
        "comments": {"nodes": [{"author": {"login": author}, "createdAt": created, "body": body}]},
    }


def sweep(capsys, tmp_path, invocation, results, nodes, known_labels=()):
    plan = ok(
        capsys,
        tmp_path,
        "selector",
        {"invocation": invocation, "tracker": TRACKER, "known_labels": list(known_labels)},
    )
    if plan["error"]:
        return plan, None, None
    resolved = ok(
        capsys, tmp_path, "resolve", {**plan, "tracker": TRACKER, "now": NOW, "results": results(plan)}
    )
    classified = ok(
        capsys, tmp_path, "preflight",
        {"tracker": TRACKER, "now": NOW, "issues": nodes, "explicit": resolved["explicit"], "no_preflight": plan["no_preflight"]},
    )  # fmt: skip
    return plan, resolved, classified


# --- Bulk selectors and pre-flight -------------------------------------------


def test_case_1_cve_token_injection(capsys, tmp_path):
    plan, _, _ = sweep(capsys, tmp_path, "sync CVE-2026-40913, CVE-2026-1$(id)", lambda p: {}, [])
    assert plan["error"] == "invalid_cve_token"
    assert plan["invalid_tokens"] == ["CVE-2026-1$(id)"]
    assert plan["queries"] == [] and plan["numbers"] == []


def test_case_2_cve_list_expands(capsys, tmp_path):
    searches = {
        "CVE-2026-40913": [
            {
                "number": 232,
                "body": "### CVE tool link\n\nhttps://cveprocess.apache.org/cve5/CVE-2026-40913\n\n### Severity\n\n_No response_",
            },
            {
                "number": 240,
                "body": "### CVE tool link\n\n_No response_\n\n### Severity\n\nsee CVE-2026-40913",
            },
        ],
        "CVE-2026-40690": [
            {"number": 251, "body": "### CVE tool link\n\nhttps://cveprocess.apache.org/cve5/CVE-2026-40690"},
            {"number": 252, "body": "### CVE tool link\n\nhttps://cveprocess.apache.org/cve5/CVE-2026-40690"},
        ],
    }
    nodes = [
        node(
            232,
            "OPEN",
            "2026-10-01T09:00:00Z",
            ["airflow", "cve allocated"],
            "alice-reporter",
            "2026-10-01T09:00:00Z",
            "Thanks",
        ),
        node(
            251,
            "OPEN",
            "2026-09-30T15:00:00Z",
            ["airflow", "cve allocated"],
            "bob-maintainer",
            "2026-09-30T15:00:00Z",
            "CWE",
        ),
        node(
            252,
            "OPEN",
            "2026-09-29T08:00:00Z",
            ["providers", "cve allocated"],
            "carol",
            "2026-09-29T08:00:00Z",
            "review",
        ),
    ]
    plan, resolved, classified = sweep(
        capsys, tmp_path, "sync CVE-2026-40913, CVE-2026-40690",
        lambda p: {q["id"]: searches[q["value"]] for q in p["queries"]}, nodes,
    )  # fmt: skip
    assert plan["searched_cve_ids"] == ["CVE-2026-40913", "CVE-2026-40690"]
    assert all(q["command"].startswith('gh search issues "CVE-') for q in plan["queries"])
    assert resolved["resolved"] == [232, 251, 252]
    assert classified["dispatched"] == [232, 251, 252]
    assert classified["skipped"] == []


SYNC_ALL_OPEN = [
    {"number": 99, "labels": labels("rejections-ledger")},
    {"number": 210, "labels": labels("airflow", "cve allocated", "pr merged")},
    {"number": 211, "labels": labels("airflow", "cve allocated", "fix released")},
    {"number": 212, "labels": labels("airflow", "cve allocated", "pr merged")},
    {"number": 214, "labels": labels("airflow", "cve allocated", "pr merged", "announced")},
    {"number": 215, "labels": labels("airflow", "needs triage")},
]
SYNC_ALL_CLOSED = [
    {"number": 150, "labels": labels("announced"), "closedAt": "2026-06-05T10:00:00Z"},
    {"number": 180, "labels": labels("announced"), "closedAt": "2026-08-19T10:00:00Z"},
    {"number": 195, "labels": labels("announced"), "closedAt": "2026-09-23T10:00:00Z"},
]
DONE = ["airflow", "cve allocated", "pr merged", "fix released", "announced"]
SYNC_ALL_NODES = [
    node(180, "CLOSED", "2026-08-19T10:00:00Z", DONE, "potiuk", "2026-08-19T10:00:00Z", MARKER, "2026-08-19T10:00:00Z"),
    node(195, "CLOSED", "2026-09-23T10:00:00Z", DONE, "potiuk", "2026-09-23T10:00:00Z", MARKER, "2026-09-23T10:00:00Z"),
    node(210, "OPEN", "2026-10-01T08:00:00Z", ["airflow", "cve allocated", "pr merged"], "potiuk", "2026-10-01T08:00:00Z", MARKER),
    node(211, "OPEN", "2026-09-20T08:00:00Z", ["airflow", "cve allocated", "fix released"], "potiuk", "2026-09-20T08:00:00Z", MARKER),
    node(212, "OPEN", "2026-09-30T11:00:00Z", ["airflow", "cve allocated", "pr merged"], "dave-reporter", "2026-09-30T11:00:00Z", "release date?"),
    node(214, "OPEN", "2026-09-10T08:00:00Z", ["airflow", "cve allocated", "pr merged", "announced"], "github-actions[bot]", "2026-09-10T08:00:00Z", "Milestone closed."),
    node(215, "OPEN", "2026-09-28T08:00:00Z", ["airflow", "needs triage"], "potiuk", "2026-09-28T08:00:00Z", MARKER),
]  # fmt: skip


def all_results(plan):
    return {q["id"]: SYNC_ALL_OPEN if q["kind"] == "open" else SYNC_ALL_CLOSED for q in plan["queries"]}


def test_case_3_sync_all_preflight(capsys, tmp_path):
    _, resolved, classified = sweep(capsys, tmp_path, "sync all", all_results, SYNC_ALL_NODES)
    assert resolved["resolved"] == [180, 195, 210, 211, 212, 214, 215]
    assert resolved["groups"] == {"open": 5, "recently_closed": 2}
    assert classified["dispatched"] == [195, 212, 215]
    assert classified["skipped"] == [
        {"issue": 180, "rule": "post_announce_cve_published"},
        {"issue": 210, "rule": "awaiting_release"},
        {"issue": 211, "rule": "fix_released_awaiting_advisory"},
        {"issue": 214, "rule": "all_phases_done_awaiting_closure"},
    ]
    assert classified["skipped_text"].startswith("Pre-flight skipped\n- [airflow-s/airflow-s#180]")


def test_case_4_named_numbers_never_skipped(capsys, tmp_path):
    nodes = [n for n in SYNC_ALL_NODES if n["number"] in (210, 211, 214)]
    _, resolved, classified = sweep(capsys, tmp_path, "sync #210, #211, #214", lambda p: {}, nodes)
    assert resolved["resolved"] == [210, 211, 214]
    assert classified["dispatched"] == [210, 211, 214]
    assert classified["skipped"] == []
    assert all(r["named_but_idle"] for r in classified["rows"])


def test_case_5_force_sync(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "parse-bulk-reply",
        {"reply": "force-sync #211", "proposal": {"195": [1], "212": [1, 2], "215": [1]}, "preflight_skipped": [180, 210, 211, 214]},
    )  # fmt: skip
    assert (out["action"], out["force_sync"], out["apply"]) == ("force_sync", [211], {})


def test_case_6_review_ready_push_exempt(capsys, tmp_path):
    report = {
        "issue": 212,
        "cve_id": "CVE-2026-41002",
        "proposed_label_add": ["fix released"],
        "proposed_label_remove": ["pr merged"],
        "proposed_body_field_updates": ["CWE — rewrite bare `CWE-918` to long form"],
    }
    out = ok(capsys, tmp_path, "bucket", {"reports": [report]})
    assert out["review_ready_push_bucket"] == "non_cve_affecting"
    assert out["cve_affecting"] == [212]  # the CWE wording still gets its content review


def test_case_7_cve_selector_never_skipped(capsys, tmp_path):
    rows = [{"number": 260, "body": "### CVE tool link\n\nhttps://cveprocess.apache.org/cve5/CVE-2026-40777"}]
    nodes = [
        node(
            260,
            "OPEN",
            "2026-09-12T10:00:00Z",
            ["airflow", "cve allocated", "pr merged"],
            "potiuk",
            "2026-09-12T10:00:00Z",
            MARKER,
        )
    ]
    plan, resolved, classified = sweep(capsys, tmp_path, "sync CVE-2026-40777", lambda p: {"q1": rows}, nodes)
    assert plan["searched_cve_ids"] == ["CVE-2026-40777"]
    assert resolved["resolved"] == [260]
    assert classified["dispatched"] == [260]
    assert classified["skipped"] == []


def test_case_8_reporter_reply_urgent(capsys, tmp_path):
    rows = [
        {"number": 270, "labels": labels("airflow", "cve allocated")},
        {"number": 271, "labels": labels("airflow", "needs triage")},
    ]
    nodes = [
        node(
            270,
            "OPEN",
            "2026-10-03T09:00:00Z",
            ["airflow", "cve allocated"],
            "dana-reporter",
            "2026-10-03T09:00:00Z",
            "Any news?",
        ),
        node(
            271,
            "OPEN",
            "2026-09-30T14:00:00Z",
            ["airflow", "needs triage"],
            "erik",
            "2026-09-30T14:00:00Z",
            "I can reproduce",
        ),
    ]
    _, resolved, classified = sweep(capsys, tmp_path, "sync all open", lambda p: {"q1": rows}, nodes)
    assert resolved["resolved"] == [270, 271]
    assert classified["dispatched"] == [270, 271]
    assert classified["urgent"] == [270]


def test_a_capped_list_is_flagged_and_an_empty_one_stops(capsys, tmp_path):
    plan = ok(capsys, tmp_path, "selector", {"invocation": "sync open", "tracker": TRACKER})
    full = [{"number": n, "labels": labels("airflow")} for n in range(1, 101)]
    capped = ok(
        capsys, tmp_path, "resolve", {**plan, "tracker": TRACKER, "now": NOW, "results": {"q1": full}}
    )
    assert "cap" in capped["warnings"][0]
    empty = ok(capsys, tmp_path, "resolve", {**plan, "tracker": TRACKER, "now": NOW, "results": {"q1": []}})
    assert empty["resolved"] == [] and "never fall back" in empty["message"]


def test_labels_titles_and_no_preflight(capsys, tmp_path):
    plan = ok(
        capsys, tmp_path, "selector",
        {"invocation": "sync pr merged, JWT --no-preflight", "tracker": TRACKER, "known_labels": ["pr merged"]},
    )  # fmt: skip
    assert [q["kind"] for q in plan["queries"]] == ["label", "title"]
    assert plan["queries"][1]["command"].endswith(
        '--search "JWT in:title" --limit 100 --json number,title,labels'
    )
    assert plan["no_preflight"] is True
    nodes = [
        node(
            210,
            "OPEN",
            "2026-10-01T08:00:00Z",
            ["airflow", "cve allocated", "pr merged"],
            "potiuk",
            "2026-10-01T08:00:00Z",
            MARKER,
        )
    ]
    out = ok(
        capsys, tmp_path, "preflight", {"tracker": TRACKER, "now": NOW, "issues": nodes, "no_preflight": True}
    )
    assert out["dispatched"] == [210]


# --- Bulk orchestration: the CVE-impact buckets ------------------------------


def reports(*updates):
    return [{"issue": n, "proposed_body_field_updates": u} for n, u in updates]


@pytest.mark.parametrize(
    ("case", "data", "cve", "plain"),
    [
        ("case-1-all-label-only", reports((318, []), (319, []), (320, [])), [], [318, 319, 320]),
        (
            "case-2-mixed-buckets",
            reports(
                (410, []),
                (
                    411,
                    [
                        "Short public summary for publish — add upgrade target",
                        "CWE — rewrite bare `CWE-22` to long form",
                    ],
                ),
                (412, ["Reporter credited as — anonymise from `Jane Doe (internal scan)` to `anonymous`"]),
                (413, []),
            ),
            [411, 412],
            [410, 413],
        ),
        (
            "case-3-all-cve-affecting",
            reports(
                (
                    450,
                    [
                        "Title — strip `[ Security Report ]` prefix",
                        "Affected versions — wrap value in backticks",
                    ],
                ),
                (
                    451,
                    [
                        "Short public summary for publish — write summary",
                        "Severity — set `Unknown` to `Medium`",
                    ],
                ),
                (
                    452,
                    [
                        "Remediation developer — set to `Jarek Potiuk`",
                        "PR with the fix — populate with apache/airflow#68102",
                    ],
                ),
            ),
            [450, 451, 452],
            [],
        ),
    ],
)
def test_bulk_orchestration_cases(capsys, tmp_path, case, data, cve, plain):
    out = ok(capsys, tmp_path, "bucket", {"reports": data})
    assert (out["cve_affecting"], out["non_cve_affecting"], out["walk_order"]) == (cve, plain, cve)


def test_parse_bulk_reply_forms(capsys, tmp_path):
    proposal = {"212": [1, 2, 3], "215": [1, 2]}
    out = ok(capsys, tmp_path, "parse-bulk-reply", {"reply": "212:1,3; 215:skip", "proposal": proposal})
    assert (out["action"], out["apply"], out["skip"]) == ("apply", {"212": [1, 3]}, [215])
    out = ok(
        capsys,
        tmp_path,
        "parse-bulk-reply",
        {"reply": "all; 215:edit 2: use the 3.2.2 milestone", "proposal": proposal},
    )
    assert out["apply"] == {"212": [1, 2, 3], "215": [1, 2]}
    assert out["edits"] == [{"tracker": 215, "item": 2, "value": "use the 3.2.2 milestone"}]
    for reply in ("212:4", "999:all", "212:all; 212:1", "looks fine I guess", "force-sync #212"):
        assert (
            ok(
                capsys,
                tmp_path,
                "parse-bulk-reply",
                {"reply": reply, "proposal": proposal, "preflight_skipped": [211]},
            )["action"]
            == "ambiguous"
        )
    assert (
        ok(capsys, tmp_path, "parse-bulk-reply", {"reply": "cancel", "proposal": proposal})["action"]
        == "cancel"
    )


# --- Step 3: confirm ---------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "items", "reply", "expected"),
    [
        ("case-1-apply-all", [1, 2, 3, 4, 5, 6], "all", ("apply", [1, 2, 3, 4, 5, 6], [])),
        ("case-2-selective", [1, 2, 3, 4, 5, 6], "1,2,5", ("apply", [1, 2, 5], [3, 4, 6])),
        ("case-3-cancel", [1, 2, 3], "cancel", ("cancel", [], [])),
    ],
)
def test_step_3_confirm_cases(capsys, tmp_path, case, items, reply, expected):
    out = ok(capsys, tmp_path, "parse-reply", {"reply": reply, "items": items})
    assert (out["action"], out["items_applied"], out["items_skipped"]) == expected


# --- Step 6: recap -----------------------------------------------------------


def test_case_1_full_sync_with_cve(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "render-recap",
        {"tracker": TRACKER, "issue": 272, "applied": ["label `needs triage` removed", "scope label `airflow` added"],
         "rollup_comment": "#issuecomment-2441839", "milestone": {"title": "3.0.3", "number": 17},
         "cve_id": "CVE-2025-44812", "record_url_template": RECORD,
         "drafts": [{"id": "r123", "thread_url": "https://mail.google.com/mail/u/0/#inbox/AA003xyz"}],
         "next_step": "design the fix using the security-issue-fix skill."},
    )  # fmt: skip
    text = out["text"]
    issue = f"https://github.com/{TRACKER}/issues/272"
    assert f"[{TRACKER}#272]({issue})" in text
    assert f"({issue}#issuecomment-2441839)" in text
    assert f"({issue}#cve-json--paste-ready-for-cve-2025-44812)" in text
    assert f"(https://github.com/{TRACKER}/milestone/17)" in text
    assert "waiting in Gmail on [the thread]" in text
    assert "**Next:** design the fix" in text
    assert out["bare_refs"] == []


def test_case_2_no_cve_yet(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "render-recap",
        {"tracker": TRACKER, "issue": 301, "applied": ["label `needs triage` removed"], "rollup_comment": "2449102",
         "next_step": "continue the CVE-worthiness discussion and tag a second team member."},
    )  # fmt: skip
    text = out["text"]
    assert "#issuecomment-2449102" in text
    assert "none allocated yet" in text
    assert "Milestone: none set." in text
    assert "waiting in Gmail" not in text
    assert out["bare_refs"] == []


# --- Guardrails --------------------------------------------------------------


def test_case_1_cvss_not_propagated(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "check",
        {"surfaces": [
            {"kind": "observed", "text": "Reporter: Severity CVSS 9.1 (Critical)."},
            {"kind": "body_patch", "text": 'Update "Severity" body field to: "CVSS 9.1 (Critical) — as reported by researcher"'},
            {"kind": "status_comment", "text": "Sync 2025-11-03 — severity confirmed at CVSS 9.1 (Critical) per reporter's assessment."},
        ]},
    )  # fmt: skip
    assert out["clean"] is False
    assert [v["guardrail"] for v in out["violations"]] == [
        "Never propagate a reporter-supplied CVSS score",
        "Never propagate a reporter-supplied CVSS score",
    ]
    assert out["violations"][1]["evidence"].startswith("Sync 2025-11-03")


def test_case_2_severity_label_not_copied(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "check",
        {"surfaces": [
            {"kind": "observed", "text": "Reporter indicated a severity assessment (informational)."},
            {"kind": "status_comment", "text": "Sync 2025-11-05 — assessment complete. Issue is valid and "
             "[CVE-2025-44812](https://cveprocess.apache.org/cve5/CVE-2025-44812) has been allocated."},
            {"kind": "email", "text": "Thank you for the report. The team allocated CVE-2025-44812.\n"
             "An advisory will follow once the fix ships."},
        ], "own_names": ["Airflow"]},
    )  # fmt: skip
    assert out == {"ok": True, "clean": True, "violations": []}


def test_case_3_other_asf_project_not_named(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "check",
        {"organization": "ASF", "surfaces": [
            {"kind": "status_comment", "text": "Sync 2025-11-04 — SSRF confirmed. Note: reporter has previously reported "
             "CVE-2024-55633 against Apache Superset exploiting an identical connection test vector. "
             "Our issue shares the same root cause."},
            {"kind": "rollup", "text": "Similar SSRF was reported to Apache Superset as CVE-2024-55633 and is now public; "
             "we should coordinate the fix timeline accordingly."},
        ]},
    )  # fmt: skip
    assert [v["guardrail"] for v in out["violations"]] == [
        "Never name or describe other ASF projects' vulnerabilities",
        "Linking CVEs",
        "Never name or describe other ASF projects' vulnerabilities",
        "Linking CVEs",
    ]


def test_a_non_asf_project_does_not_flag_asf_names(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "check",
        {"organization": "independent", "surfaces": [
            {"kind": "status_comment", "text": "Sync 2025-11-04 — SSRF confirmed. Note: reporter has previously "
             "reported a similar issue against Apache Superset."},
        ]},
    )  # fmt: skip
    assert out["clean"] is True


def test_the_cve_tool_url_in_an_email_is_the_violation(capsys, tmp_path):
    out = ok(
        capsys,
        tmp_path,
        "check",
        {"surfaces": [{"kind": "email", "text": "See https://cveprocess.apache.org/cve5/CVE-2025-1."}]},
    )
    assert [v["guardrail"] for v in out["violations"]] == ["Linking CVEs"]


def test_a_configured_cve_tool_url_without_a_scheme_is_still_the_violation(capsys, tmp_path):
    out = ok(
        capsys,
        tmp_path,
        "check",
        {"cve_tool_url": "cve.example.org",
         "surfaces": [{"kind": "email", "text": "See https://cve.example.org/cve5/CVE-2025-1."}]},
    )  # fmt: skip
    assert [v["guardrail"] for v in out["violations"]] == ["Linking CVEs"]


def test_a_configured_cve_tool_url_with_a_port_matches_a_plain_url(capsys, tmp_path):
    out = ok(
        capsys,
        tmp_path,
        "check",
        {"cve_tool_url": "https://cve.example.org:8443",
         "surfaces": [{"kind": "email", "text": "See https://cve.example.org/cve5/CVE-2025-1."}]},
    )  # fmt: skip
    assert [v["guardrail"] for v in out["violations"]] == ["Linking CVEs"]


def test_the_public_cve_record_link_is_allowed_when_cve_org_is_the_tool(capsys, tmp_path):
    out = ok(
        capsys,
        tmp_path,
        "check",
        {"organization": "independent", "cve_tool_url": "https://www.cve.org",
         "surfaces": [{"kind": "email", "text": "See https://www.cve.org/CVERecord?id=CVE-2025-1."}]},
    )  # fmt: skip
    assert out["clean"] is True


def test_an_unset_organization_still_flags_asf_names(capsys, tmp_path):
    out = ok(
        capsys,
        tmp_path,
        "check",
        {"surfaces": [{"kind": "status_comment", "text": "Tomcat had the same issue."}]},
    )
    assert [v["guardrail"] for v in out["violations"]] == [
        "Never name or describe other ASF projects' vulnerabilities"
    ]
