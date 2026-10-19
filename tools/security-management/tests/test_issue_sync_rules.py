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
"""`security-management issue-sync` drafting, advisory and push rules.

The cases of the retired model-graded `security-issue-sync` suites
`step-security-cc`, `step-draft-backend`, `step-ghsa-access-tier` and
`step-5b-push-decision` live here, named after each former case, with the
same scenario and expected output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["issue-sync", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out)


def ok(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> dict[str, Any]:
    code, out = run(capsys, tmp_path, command, data)
    assert code == 0, out
    return out


# --- Security CC -------------------------------------------------------------

FOUNDATION = "security_inbox.foundation_security_address"


def flat(security_list=None, foundation=None, existing=(), previous=None, *, omit_list=False):
    data: dict[str, Any] = {
        FOUNDATION: foundation,
        "existing_cc": list(existing),
        "previous_cc_fallback": previous,
    }
    if not omit_list:
        data["security_list"] = security_list
    return data


def layered(project, organization, defaults):
    return {
        "project": project,
        "organization": organization,
        "framework_defaults": defaults,
        "existing_cc": [],
    }


P, F, A = "security@project.example", "security@foundation.example", "security@apache.org"
CASES = [
    ("case-1-configured", flat(P, F), (P, None, False, False, [P], P)),
    ("case-2-blank", flat("   ", F), (F, F, True, False, [F], None)),
    ("case-3-missing-asf", flat(foundation=A, omit_list=True), (A, A, True, False, [A], None)),
    ("case-4-template-todo", flat("TODO: e.g. security@foo.apache.org", A), (A, A, True, False, [A], None)),
    ("case-5-no-address", flat(None, None), (None, None, True, True, [], None)),
    ("case-6-non-asf-override", flat("", "security@acme.example"),
     ("security@acme.example", "security@acme.example", True, False, ["security@acme.example"], None)),
    ("case-7-trim-and-dedupe", flat("  " + P + "  ", F, ["team@project.example", P]),
     (P, None, False, False, ["team@project.example", P], P)),
    ("case-8-clear-old-fallback", flat(P, F, previous=F), (P, None, False, False, [P], P)),
    (
        "case-9-project-fallback-override",
        layered({"security_list": "", "security_inbox": {"foundation_security_address": P}},
                {"security_inbox": {"foundation_security_address": "security@org.example"}},
                {"security_inbox": {"foundation_security_address": None}}),
        (P, P, True, False, [P], None),
    ),
    (
        "case-10-organization-fallback",
        layered({"security_list": "   "}, {"security_inbox": {"foundation_security_address": "security@org.example"}},
                {"security_inbox": {"foundation_security_address": "security@default.example"}}),
        ("security@org.example", "security@org.example", True, False, ["security@org.example"], None),
    ),
    (
        "case-11-explicit-null-override",
        layered({"security_list": None, "security_inbox": {"foundation_security_address": None}},
                {"security_inbox": {"foundation_security_address": "security@org.example"}}, {}),
        (None, None, True, True, [], None),
    ),
    (
        "case-12-project-list-override",
        layered({"security_list": P}, {"security_list": "security@org.example",
                 "security_inbox": {"foundation_security_address": "security@org-admin.example"}}, {}),
        (P, None, False, False, [P], P),
    ),
    (
        "case-13-framework-fallback",
        layered({"security_list": ""}, {}, {"security_inbox": {"foundation_security_address": "security@default.example"}}),
        ("security@default.example", "security@default.example", True, False, ["security@default.example"], None),
    ),
]  # fmt: skip


@pytest.mark.parametrize(("case", "data", "expected"), CASES, ids=[c[0] for c in CASES])
def test_security_cc_cases(capsys, tmp_path, case, data, expected):
    out = ok(capsys, tmp_path, "security-cc", data)
    keys = ("security_cc", "cc_fallback", "warning", "draft_blocked", "cc", "search_list")
    assert tuple(out[k] for k in keys) == expected


# --- Draft backend -----------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "data", "expected"),
    [
        ("case-1-project-maildir", {"project_backend": "maildir"}, ("maildir", "project.md")),
        (
            "case-2-person-overrides-to-gmail",
            {"project_backend": "maildir", "user_backend": "gmail"},
            ("oauth_curl", "user.md"),
        ),
        ("case-3-person-overrides-to-maildir", {"user_backend": "maildir"}, ("maildir", "user.md")),
        ("case-4-nothing-set", {}, ("oauth_curl", "default")),
        (
            "case-5-project-gmail-no-credential",
            {"project_backend": "gmail", "oauth_credentials": False, "body_has_links": False},
            ("claude_ai_mcp", "project.md"),
        ),
    ],
)
def test_draft_backend_cases(capsys, tmp_path, case, data, expected):
    out = ok(capsys, tmp_path, "draft-backend", data)
    assert (out["backend"], out["decided_by"]) == expected


def test_no_credential_and_links_is_refused(capsys, tmp_path):
    code, out = run(capsys, tmp_path, "draft-backend", {"oauth_credentials": False, "body_has_links": True})
    assert code == 2
    assert "refresh the OAuth credentials" in out["refused"]


# --- GHSA access tier --------------------------------------------------------


def route(capsys, tmp_path, **data):
    return ok(capsys, tmp_path, "ghsa-route", data)


def test_case_1_collaborator_field_edit_direct(capsys, tmp_path):
    out = route(capsys, tmp_path, change="field_edit", in_list=True)
    assert (out["access_tier"], out["action"], out["channel"]) == (
        "collaborator",
        "direct-write",
        "advisory-api",
    )
    assert out["requires_confirmation"] is True and out["relay_parts"] == []


def test_case_2_collaborator_403_admin_handoff(capsys, tmp_path):
    out = route(
        capsys,
        tmp_path,
        change="collaborators",
        in_list=True,
        got_403=True,
        security_thread_id="19a2f7c4e81b03d5",
    )
    assert (out["access_tier"], out["action"], out["channel"]) == (
        "collaborator",
        "relay-draft",
        "email-draft",
    )
    assert (out["mail_tool"], out["recipient"], out["reply_on_security_thread"]) == (
        "gmail-plaintext-mcp",
        "<foundation-security-list>",
        True,
    )
    assert (
        out["retry_after_403"] is False
        and out["posts_tracker_comment"] is False
        and out["auto_send"] is False
    )
    assert out["rollup_handoff_marker"] is True
    assert out["relay_parts"] == ["already-done", "admin-only-change-and-why", "ask"]


def test_case_3_admin_collaborator_mgmt_direct(capsys, tmp_path):
    out = route(capsys, tmp_path, change="collaborators", in_list=True, security_manager=True)
    assert (out["access_tier"], out["action"], out["rollup_handoff_marker"]) == (
        "admin",
        "direct-write",
        False,
    )


def test_case_4_reporter_reply_collaborator_browser(capsys, tmp_path):
    url = "https://github.com/<upstream>/security/advisories/GHSA-q8mz-5tdc-w2jh"
    out = route(capsys, tmp_path, change="reporter_reply", in_list=True, html_url=url)
    assert (out["action"], out["channel"], out["requires_confirmation"]) == (
        "browser-paste",
        "advisory-web-ui",
        None,
    )
    assert out["claims_reply_posted"] is False and out["open_url"] == url


def test_case_5_reporter_reply_not_collaborator_relay(capsys, tmp_path):
    out = route(capsys, tmp_path, change="reporter_reply", in_list=False, advisory_get_status=404)
    assert (out["access_tier"], out["action"], out["channel"]) == (
        "not-collaborator",
        "relay-draft",
        "email-draft",
    )
    assert (out["mail_tool"], out["recipient"], out["requires_confirmation"]) == (None, None, True)


# --- Step 5b: the push decision ----------------------------------------------

NAMES = {"project_names": ["Apache Airflow"], "short_names": ["Airflow"]}
GOOD = dict.fromkeys(
    (
        "trigger_conditions",
        "incomplete_fix_clause",
        "anonymise_private_finder",
        "conservative_affected_range",
    ),
    True,
)


def record(
    title="Stored XSS in the task instance notes view",
    state="REVIEW",
    cwe="CWE-79: Improper Neutralization",
    summary=None,
):
    return {
        "containers": {
            "cna": {
                "title": title,
                "descriptions": [
                    {
                        "value": summary
                        or "A user could store JavaScript. Users are recommended to upgrade to apache-airflow 2.10.5, which fixes the issue."
                    }
                ],
                "problemTypes": [{"descriptions": [{"cweId": cwe.split(":")[0], "description": cwe}]}],
            }
        },
        "CNA_private": {"state": state},
    }


def decide(capsys, tmp_path, **data):
    base = {"regenerated": True, "cve_id": "CVE-2026-41107", **NAMES, "judged": GOOD, "record": record()}
    return ok(capsys, tmp_path, "push-decision", {**base, **data})


def test_case_1_skip_5a_skipped_invalid(capsys, tmp_path):
    out = decide(capsys, tmp_path, regenerated=False, cve_id=None)
    assert (out["action"], out["gate_failed"], out["handoff_variant"], out["state_advance"]) == (
        "skip",
        None,
        None,
        None,
    )


def test_case_2_expired_session_fix_released(capsys, tmp_path):
    out = decide(capsys, tmp_path, session="expired", record_state="DRAFT", fix_released_transition=True)
    assert (out["action"], out["handoff_variant"], out["recap_blocker"]) == ("hand-off", "manual-paste", True)
    assert "vulnogram-api-setup" in out["reason"]


def test_case_3_title_gate_ghsa_prefix(capsys, tmp_path):
    out = decide(
        capsys,
        tmp_path,
        record=record(title="[GHSA-7f3q-9xw2-hm4c] Path traversal in the DAG file processor", state="DRAFT"),
    )
    assert (out["action"], out["gate_failed"], out["state_advance"]) == ("block", "title_strip_cascade", None)


def test_case_4_private_scanner_credit(capsys, tmp_path):
    out = decide(
        capsys, tmp_path, judged={**GOOD, "anonymise_private_finder": False}, record=record(state="DRAFT")
    )
    assert (out["action"], out["gate_failed"]) == ("block", "anonymise_private_finder")


def test_case_5_clean_push_fix_released(capsys, tmp_path):
    base = {"session": "valid", "record_state": "DRAFT", "fix_released_transition": True}
    assert decide(capsys, tmp_path, **base)["next"].endswith(
        "--json-file '<scratch>/cve-CVE-2026-41107.json'"
    )
    pending = decide(capsys, tmp_path, **base, push_exit=0)
    assert "vulnogram-api-record-fetch --cve-id CVE-2026-41107" in pending["next"]
    out = decide(capsys, tmp_path, **base, push_exit=0, fetched_state="REVIEW")
    assert (out["action"], out["handoff_variant"], out["state_advance"], out["recap_blocker"]) == (
        "push",
        "oauth-pushed",
        "allocated->review-ready",
        False,
    )


def test_case_6_public_record_advisory_closeout(capsys, tmp_path):
    out = decide(
        capsys, tmp_path, session="valid", record_state="PUBLIC", record=record(state="PUBLIC"), push_exit=0
    )
    assert (out["action"], out["state_advance"], out["recap_blocker"]) == ("push", None, False)


def test_case_7_not_configured_fix_released(capsys, tmp_path):
    out = decide(
        capsys, tmp_path, session="not-configured", record_state="DRAFT", fix_released_transition=True
    )
    assert (out["action"], out["handoff_variant"], out["recap_blocker"]) == ("hand-off", "manual-paste", True)


def test_case_8_not_configured_no_transition(capsys, tmp_path):
    out = decide(capsys, tmp_path, session="not-configured", record_state="REVIEW")
    assert (out["action"], out["handoff_variant"], out["recap_blocker"]) == (
        "hand-off",
        "manual-paste",
        False,
    )


@pytest.mark.parametrize(
    ("data", "gate"),
    [
        (
            {"record": record(summary="Users should upgrade to the version that contains the fix.")},
            "upgrade_target_version",
        ),
        ({"record": record(cwe="CWE-79")}, "cwe_long_form"),
        ({"judged": {**GOOD, "conservative_affected_range": False}}, "conservative_affected_range"),
    ],
)
def test_the_other_gates_block(capsys, tmp_path, data, gate):
    out = decide(capsys, tmp_path, **data)
    assert (out["action"], out["gate_failed"]) == ("block", gate)


def test_an_unjudged_gate_is_asked_for_and_a_failed_push_hands_off(capsys, tmp_path):
    out = decide(capsys, tmp_path, judged={"trigger_conditions": True})
    assert (out["action"], out["next"]) == ("pending", "incomplete_fix_clause")
    failed = decide(capsys, tmp_path, session="valid", record_state="REVIEW", push_exit=1)
    assert (failed["action"], failed["handoff_variant"], failed["recap_blocker"]) == (
        "hand-off",
        "manual-paste",
        True,
    )
    stuck = decide(
        capsys, tmp_path, session="valid", record_state="DRAFT", push_exit=0, fetched_state="DRAFT"
    )
    assert (stuck["action"], stuck["state_advance"], stuck["recap_blocker"]) == ("push", None, True)


def test_a_malformed_cve_id_never_reaches_a_command(capsys, tmp_path):
    code, out = run(
        capsys, tmp_path, "push-decision", {"regenerated": True, "cve_id": "CVE-2026-1; rm -rf ~", **NAMES}
    )
    assert code == 2
    assert "CVE-YYYY-NNNNN" in out["refused"]
