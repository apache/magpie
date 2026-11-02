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

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main
from security_management.issue_sync.ghsa_fields import RESOLUTION_MARKER, severity, version_range

GHSA = "GHSA-q8mz-5tdc-w2jh"


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    code = main(["issue-sync", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out or "{}")


def advisory(**over: Any) -> dict[str, Any]:
    base = {
        "ghsa_id": GHSA,
        "html_url": f"https://github.com/<upstream>/security/advisories/{GHSA}",
        "cve_id": None,
        "severity": "high",
        "cwe_ids": [],
        "summary": "XSS in notes",
        "description": "Reporter's original report.",
        "vulnerabilities": [
            {
                "package": {"ecosystem": "pip", "name": "apache-airflow"},
                "vulnerable_version_range": "<= 3.0.0",
                "patched_versions": None,
                "vulnerable_functions": ["notes_view"],
            }
        ],
        "credits_detailed": [{"user": {"login": "finder"}, "type": "reporter", "state": "accepted"}],
    }
    base.update(over)
    return base


TRACKER = {
    "cve_id": "CVE-2026-12345",
    "severity": "Moderate",
    "cwe": "CWE-79: Improper Neutralization of Input During Web Page Generation",
    "affected_versions": ">= 2.0.0, < 3.0.2",
    "package": {"ecosystem": "pip", "name": "apache-airflow"},
    "pr_author_login": "fixer",
    "pr_approver_logins": ["reviewer", "fixer", "dependabot[bot]"],
    "pr_with_fix": "https://github.com/<upstream>/pull/1",
    "public_advisory_url": "_No response_",
}


def plan(capsys, tmp_path, adv=None, tracker=None, **extra):
    code, out = run(
        capsys,
        tmp_path,
        "ghsa-fields",
        {"advisory": adv or advisory(), "tracker": tracker or TRACKER, **extra},
    )
    assert code == 0, out
    return out


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (">= 2.0.0, < 3.0.2", {"range": ">= 2.0.0, < 3.0.2", "patched": "3.0.2"}),
        ("`< 1.4.1`", {"range": "< 1.4.1", "patched": "1.4.1"}),
        ("<= 1.4.0", {"range": "<= 1.4.0", "patched": None}),
        (">= 2.0.0, < NEXT VERSION", {"range": ">= 2.0.0", "patched": None}),
        ("_No response_", None),
        ("all of them", None),
    ],
)
def test_version_range(raw, expected):
    assert version_range(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Moderate", "medium"),
        ("High (CVSS 4.0 7.1)", "high"),
        ("low", "low"),
        ("_No response_", None),
        ("", None),
    ],
)
def test_severity(raw, expected):
    assert severity(raw) == expected


def test_full_plan_from_an_unreconciled_advisory(capsys, tmp_path):
    out = plan(capsys, tmp_path)
    patch = out["patch"]
    assert patch["cve_id"] == "CVE-2026-12345"
    assert patch["severity"] == "medium"
    assert patch["cwe_ids"] == ["CWE-79"]
    [vuln] = patch["vulnerabilities"]
    assert vuln["vulnerable_version_range"] == ">= 2.0.0, < 3.0.2"
    assert vuln["patched_versions"] == "3.0.2"
    assert vuln["vulnerable_functions"] == ["notes_view"]
    assert patch["credits"] == [
        {"login": "finder", "type": "reporter"},
        {"login": "fixer", "type": "remediation_developer"},
        {"login": "reviewer", "type": "remediation_reviewer"},
    ]
    assert out["bots_not_credited"] == ["dependabot[bot]"]
    assert out["requires_confirmation"] is True
    assert GHSA in out["command"] and "--input" in out["command"]


def test_never_writes_state_or_collaborators(capsys, tmp_path):
    out = plan(capsys, tmp_path)
    assert not {"state", "collaborating_users", "collaborating_teams"} & set(out["patch"])


def test_a_different_cve_on_the_advisory_is_a_conflict(capsys, tmp_path):
    out = plan(capsys, tmp_path, adv=advisory(cve_id="CVE-2025-99999"))
    assert "cve_id" not in out["patch"]
    assert out["conflicts"] == [
        {"field": "cve_id", "advisory": "CVE-2025-99999", "tracker": "CVE-2026-12345"}
    ]


def test_a_reconciled_advisory_is_unchanged(capsys, tmp_path):
    first = plan(capsys, tmp_path)
    reconciled = advisory(**{k: v for k, v in first["patch"].items() if k != "credits"})
    reconciled["credits_detailed"] = [
        {"user": {"login": c["login"]}, "type": c["type"]} for c in first["patch"]["credits"]
    ]
    out = plan(capsys, tmp_path, adv=reconciled)
    assert out["unchanged"] is True and out["patch"] == {} and out["command"] is None


def test_unscored_tracker_skips_instead_of_clearing(capsys, tmp_path):
    tracker = {"severity": "_No response_", "cwe": "_No response_", "affected_versions": "_No response_"}
    out = plan(capsys, tmp_path, tracker=tracker)
    assert out["patch"] == {}
    assert {s["field"] for s in out["skipped"]} == {
        "cve_id",
        "severity",
        "cwe_ids",
        "vulnerabilities",
        "credits",
    }


def test_ambiguous_package_is_skipped(capsys, tmp_path):
    two = advisory(
        vulnerabilities=[
            {"package": {"ecosystem": "pip", "name": "a"}},
            {"package": {"ecosystem": "pip", "name": "b"}},
        ]
    )
    out = plan(capsys, tmp_path, adv=two, tracker={**TRACKER, "package": {}})
    assert "vulnerabilities" not in out["patch"]
    assert any(s["field"] == "vulnerabilities" for s in out["skipped"])


def test_a_named_package_picks_its_entry_and_keeps_the_others(capsys, tmp_path):
    two = advisory(
        vulnerabilities=[
            {"package": {"ecosystem": "pip", "name": "other-pkg"}, "vulnerable_version_range": "< 9"},
            {"package": {"ecosystem": "pip", "name": "apache-airflow"}},
        ]
    )
    out = plan(capsys, tmp_path, adv=two)
    first, second = out["patch"]["vulnerabilities"]
    assert first["vulnerable_version_range"] == "< 9"
    assert second["patched_versions"] == "3.0.2"


def test_an_empty_advisory_gets_an_entry_for_the_named_package(capsys, tmp_path):
    out = plan(capsys, tmp_path, adv=advisory(vulnerabilities=[]))
    [vuln] = out["patch"]["vulnerabilities"]
    assert vuln["package"] == {"ecosystem": "pip", "name": "apache-airflow"}


def test_an_unknown_ecosystem_is_refused(capsys, tmp_path):
    code, out = run(
        capsys,
        tmp_path,
        "ghsa-fields",
        {"advisory": advisory(), "tracker": {**TRACKER, "package": {"ecosystem": "cobol", "name": "x"}}},
    )
    assert code == 2 and "ecosystem" in out["refused"]


def test_summary_only_with_a_cve_title(capsys, tmp_path):
    assert "summary" not in plan(capsys, tmp_path)["patch"]
    out = plan(
        capsys, tmp_path, tracker={**TRACKER, "cve_title": "Stored XSS in the task instance notes view"}
    )
    assert out["patch"]["summary"] == "Stored XSS in the task instance notes view"


def test_resolution_waits_for_the_public_advisory(capsys, tmp_path):
    out = plan(capsys, tmp_path, resolution=True)
    assert "description" not in out["patch"]
    assert any(s["field"] == "description" for s in out["skipped"])


def test_resolution_appends_below_the_reporters_text_and_is_idempotent(capsys, tmp_path):
    tracker = {**TRACKER, "public_advisory_url": "https://lists.apache.org/thread/abc"}
    out = plan(capsys, tmp_path, tracker=tracker, resolution=True)
    description = out["patch"]["description"]
    assert description.startswith("Reporter's original report.")
    assert RESOLUTION_MARKER in description
    assert "[CVE-2026-12345](https://www.cve.org/CVERecord?id=CVE-2026-12345)" in description
    assert "- Fixed in: apache-airflow 3.0.2" in description
    assert "https://lists.apache.org/thread/abc" in description

    again = plan(capsys, tmp_path, adv=advisory(description=description), tracker=tracker, resolution=True)
    assert "description" not in again["patch"]

    moved = {**tracker, "public_advisory_url": "https://lists.apache.org/thread/def"}
    updated = plan(capsys, tmp_path, adv=advisory(description=description), tracker=moved, resolution=True)
    new = updated["patch"]["description"]
    assert new.count(RESOLUTION_MARKER) == 1 and "thread/def" in new and "thread/abc" not in new
    assert new.startswith("Reporter's original report.")


def test_backfill_splits_plans_from_unchanged(capsys, tmp_path):
    first = plan(capsys, tmp_path)
    reconciled = advisory(
        ghsa_id="GHSA-aaaa-bbbb-cccc", **{k: v for k, v in first["patch"].items() if k != "credits"}
    )
    reconciled["credits_detailed"] = [
        {"user": {"login": c["login"]}, "type": c["type"]} for c in first["patch"]["credits"]
    ]
    code, out = run(
        capsys,
        tmp_path,
        "ghsa-backfill",
        {
            "items": [
                {"advisory": advisory(), "tracker": TRACKER, "tracker_number": 101},
                {"advisory": reconciled, "tracker": TRACKER, "tracker_number": 102},
            ]
        },
    )
    assert code == 0
    assert [p["tracker_number"] for p in out["plans"]] == [101]
    assert out["unchanged"] == ["GHSA-aaaa-bbbb-cccc"]


# --- the reverse direction: proposals for the tracker ------------------------


def test_empty_tracker_fields_are_proposed_from_the_advisory(capsys, tmp_path):
    adv = advisory(cve_id="CVE-2026-55555", cwe_ids=["CWE-22"], severity="critical")
    tracker = {
        "cve_id": "_No response_",
        "cwe": "_No response_",
        "affected_versions": "_No response_",
        "severity": "",
    }
    out = plan(capsys, tmp_path, adv=adv, tracker=tracker)
    proposed = {p["tracker_field"]: p["value"] for p in out["tracker_proposals"]}
    assert proposed == {"cve-id": "CVE-2026-55555", "cwe": "CWE-22", "affected-versions": "<= 3.0.0"}
    assert "severity" not in proposed
    assert any("never proposed" in o for o in out["observed"])


def test_both_sides_set_and_different_is_drift_and_the_tracker_wins(capsys, tmp_path):
    out = plan(capsys, tmp_path, adv=advisory(cwe_ids=["CWE-80"]))
    assert {"field": "cwe_ids", "advisory": ["CWE-80"], "tracker": ["CWE-79"]} in out["drift"]
    assert {
        "field": "vulnerable_version_range",
        "advisory": "<= 3.0.0",
        "tracker": ">= 2.0.0, < 3.0.2",
    } in out["drift"]
    assert out["patch"]["cwe_ids"] == ["CWE-79"]
    assert out["tracker_proposals"] == []


def test_other_advisory_credits_are_observed_not_proposed(capsys, tmp_path):
    adv = advisory(
        credits_detailed=[
            {"user": {"login": "finder"}, "type": "reporter"},
            {"user": {"login": "pal"}, "type": "finder"},
        ]
    )
    out = plan(capsys, tmp_path, adv=adv)
    assert any("`pal` as `finder`" in o for o in out["observed"])


def test_a_single_entry_naming_the_repository_takes_the_trackers_package(capsys, tmp_path):
    adv = advisory(
        vulnerabilities=[
            {
                "package": {"ecosystem": "", "name": "apache/airflow"},
                "patched_versions": "none",
                "vulnerable_version_range": "no fixed release exists as of 2026-10-03",
            }
        ]
    )
    out = plan(capsys, tmp_path, adv=adv)
    [vuln] = out["patch"]["vulnerabilities"]
    assert vuln["package"] == {"ecosystem": "pip", "name": "apache-airflow"}
    assert {
        "field": "package",
        "advisory": {"ecosystem": "", "name": "apache/airflow"},
        "tracker": TRACKER["package"],
    } in out["drift"]


def test_every_fix_pr_author_is_credited_once(capsys, tmp_path):
    tracker = {
        **TRACKER,
        "pr_author_login": "",
        "pr_author_logins": ["fixer", "second", "fixer"],
        "pr_approver_logins": ["second", "reviewer", "reviewer"],
    }
    out = plan(capsys, tmp_path, tracker=tracker)
    assert out["patch"]["credits"][1:] == [
        {"login": "fixer", "type": "remediation_developer"},
        {"login": "second", "type": "remediation_developer"},
        {"login": "reviewer", "type": "remediation_reviewer"},
    ]
