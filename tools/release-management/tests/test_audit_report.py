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
"""release-audit-report: Step 0 verdict, Step 1 gather / voters / check, Step 2 record, Step 3 PR.

The scripted cases of the retired model-graded suites `step-0-preflight`
(cases 1 and 2) and `step-2-assemble-record` (cases 1, 2 and 4) live here, named
after each former case, with the same scenario and the same assertions; the
expected records are byte-identical to what `render_record.py` printed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from release_management.audit_report import record, render
from release_management.cli import main

REQUIRED = record.required_fields(record.DEFAULT_SCHEMA.read_text(encoding="utf-8"))
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TRACKER_WORDS = re.compile(r"(?i)\b(CVE-\d|GHSA-|security tracker|embargo|severity)")

ROSTER = """\
| Apache ID | Name | Primary email | Binding since |
|---|---|---|---|
| `committerA` | A | `a@example.org` | 2020-01-01 |
| `committerB` | B | `b@example.org` | 2020-01-01 |
| `committerC` | C | `c@apache.org` | 2020-01-01 |
| `committerD` | D | `d@example.org` | 2020-01-01 |
"""


def preflight(
    *, blockers: list[str] | None = None, audit_log_path: str | None = "audit-logs/releases"
) -> dict:
    return {
        "ok": not blockers,
        "skill": "audit-report",
        "blockers": blockers or [],
        "warnings": [],
        "values": {
            "roster_path": "projects/airflow/pmc-roster.md",
            "version": "2.11.0",
            "audit_log_path": audit_log_path,
        },
    }


# --------------------------------------------------------------------------- Step 0


def test_case_1_clean_pass() -> None:
    out = render.verdict(preflight(), planning_issue="apache/airflow#45200", upstream="apache/airflow")
    assert {k: out[k] for k in ("verdict", "blockers", "planning_issue_url", "audit_log_path")} == {
        "verdict": "proceed",
        "blockers": [],
        "planning_issue_url": "https://github.com/apache/airflow/issues/45200",
        "audit_log_path": "audit-logs/releases",
    }


def test_case_2_audit_log_path_missing() -> None:
    blocker = "required key `audit_log_path` is missing from release-management-config.md"
    out = render.verdict(
        preflight(blockers=[blocker], audit_log_path=None),
        planning_issue="https://github.com/apache/airflow/issues/45200",
    )
    assert out["verdict"] == "blocked"
    assert out["blockers"] == [blocker]  # surfaced as written
    assert out["planning_issue_url"] == "https://github.com/apache/airflow/issues/45200"
    assert out["audit_log_path"] is None


def test_planning_issue_not_found_names_the_term_and_the_flag() -> None:
    """The blocker shape the kept step-0 case-3 asserts (has_planning_issue_blocker)."""
    out = render.verdict(preflight(), planning_issue=None, upstream="apache/airflow", searched="2.12.0")
    assert out["verdict"] == "blocked" and out["planning_issue_url"] is None
    pattern = r"(?is)(no planning issue|planning issue\b.{0,40}\bnot found).*2\.12\.0.*--planning-issue"
    assert re.search(pattern, " ".join(out["blockers"]))


@pytest.mark.parametrize(
    ("ref", "url"),
    [
        ("apache/airflow#45200", "https://github.com/apache/airflow/issues/45200"),
        ("https://github.com/apache/airflow/issues/45200", "https://github.com/apache/airflow/issues/45200"),
        ("https://github.com/apache/airflow/issues/45200/", "https://github.com/apache/airflow/issues/45200"),
        (
            "https://github.com/apache/airflow/issues/45200#issuecomment-1",
            "https://github.com/apache/airflow/issues/45200",
        ),
        ("#45200", "https://github.com/apache/airflow/issues/45200"),
        ("https://github.com/apache/airflow/pull/45200", None),
        ("apache/airflow#0", None),
        ("https://evil.example/apache/airflow/issues/1", None),
    ],
)
def test_planning_issue_is_normalised_to_the_canonical_url(ref: str, url: str | None) -> None:
    assert render.planning_issue_url(ref, "apache/airflow") == url


def test_a_reference_that_is_not_an_issue_blocks() -> None:
    out = render.verdict(preflight(), planning_issue="https://github.com/apache/airflow/pull/1")
    assert out["verdict"] == "blocked" and out["planning_issue_url"] is None
    assert "not a GitHub issue" in out["blockers"][0]


# --------------------------------------------------------------------------- Step 1


def load(**config: Any) -> dict:
    base = {
        "project_dist_name": "airflow",
        "product_name": "Apache Airflow",
        "release_dist_backend": "svnpubsub",
        "vote_dev_list": "dev@airflow.apache.org",
        "mail_archive": "ponymail",
        "mail_archive_url_template": "https://lists.apache.org/list.html?<dev-list>",
        "announce_list": "announce@apache.org",
        "announce_cc_lists": ["dev@airflow.apache.org"],
    }
    return {
        "config": base | config,
        "derived": {"approver_roster_path": "<project-config>/pmc-roster.md"},
        "metadata": {
            "version": "2.11.0",
            "target_url": "https://dist.apache.org/repos/dist/release/airflow/2.11.0/",
        },
    }


def test_gather_names_each_search_and_the_announce_cc_lists() -> None:
    out = render.gather(load(), rc="rc1")
    by_field = {s["field"]: s for s in out["searches"]}
    assert by_field["vote_thread_url"]["subject"] == "[VOTE] Release Apache Airflow 2.11.0 from 2.11.0-rc1"
    assert by_field["result_thread_url"]["lists"] == ["dev@airflow.apache.org"]
    announce = by_field["announce_archive_url"]
    assert announce["subject"] == "[ANNOUNCE] Apache Airflow 2.11.0 released"
    assert announce["lists"] == ["announce@apache.org", "dev@airflow.apache.org"]
    assert announce["archive_urls"][1] == "https://lists.apache.org/list.html?dev@airflow.apache.org"
    assert out["permalink_shape"] == "https://lists.apache.org/thread/<id>"


def test_gather_without_the_rc_searches_by_the_version() -> None:
    by_field = {s["field"]: s for s in render.gather(load())["searches"]}
    assert by_field["vote_thread_url"]["query"] == "[VOTE] Release Apache Airflow 2.11.0 from 2.11.0"


def test_gather_renders_the_svn_revision_lookup_for_svnpubsub_only() -> None:
    svn = render.gather(load())["promote_revision"]
    assert svn["command"] == (
        "svn info --show-item last-changed-revision https://dist.apache.org/repos/dist/release/airflow/2.11.0/"
    )
    other = render.gather(load(release_dist_backend="github-releases"))["promote_revision"]
    assert other["command"] is None and "github-releases" in other["note"]


def test_gather_defaults_the_product_name_to_the_project() -> None:
    loaded = load()
    del loaded["config"]["product_name"]
    assert render.gather(loaded)["product_name"] == "airflow"


def test_gather_quotes_a_hostile_target_url() -> None:
    loaded = load()
    loaded["metadata"]["target_url"] = "https://dist.apache.org/x/$(id)/"
    assert render.gather(loaded)["promote_revision"]["command"].endswith("'https://dist.apache.org/x/$(id)/'")


def test_voters_resolve_to_roster_handles_never_addresses() -> None:
    out = render.voters(
        ["a@example.org", "Bee <b@example.org>", "committerc@apache.org", "committerD", "x@example.org"],
        ROSTER,
    )
    assert out["binding_voters"] == ["@committerA", "@committerB", "@committerC", "@committerD"]
    assert out["unresolved"] == ["x@example.org"]
    assert not any(EMAIL.search(h) for h in out["binding_voters"])


def test_voters_prefer_a_github_column_and_dedupe() -> None:
    roster = (
        "| Apache ID | GitHub | Primary email |\n|---|---|---|\n| alice | @AliceGH | alice@example.org |\n"
    )
    out = render.voters(["alice@example.org", "alice@apache.org"], roster)
    assert out["binding_voters"] == ["@AliceGH"]


def test_voters_with_nobody_resolved_is_missing() -> None:
    assert render.voters(["x@example.org"], ROSTER)["binding_voters"] == "MISSING"


def step1_full() -> dict:
    return {
        "version": "2.11.0",
        "product_name": "Apache Airflow",
        "planning_issue_url": "https://github.com/apache/airflow/issues/45200",
        "rc_label": "rc1",
        "vote_thread_url": "https://lists.apache.org/thread/vote-airflow-2.11.0-rc1",
        "result_thread_url": "https://lists.apache.org/thread/result-airflow-2.11.0-rc1",
        "artefacts": [
            {
                "filename": "apache-airflow-2.11.0.tar.gz",
                "sha512": "aabbcc...",
                "sig": "apache-airflow-2.11.0.tar.gz.asc",
            },
            {
                "filename": "apache_airflow-2.11.0-py3-none-any.whl",
                "sha512": "ddeeff...",
                "sig": "apache_airflow-2.11.0-py3-none-any.whl.asc",
            },
        ],
        "promote_revision": "r12345",
        "announce_archive_url": "https://lists.apache.org/thread/announce-airflow-2.11.0",
        "vote_binding_plus1": 4,
        "vote_binding_minus1": 0,
        "binding_voters": ["@committerA", "@committerB", "@committerC", "@committerD"],
        "fields_missing": [],
        "fields_redacted": [],
        "injection_flagged": False,
    }


def step1_partial() -> dict:
    return {
        "version": "2.10.3",
        "product_name": "Apache Airflow",
        "planning_issue_url": "https://github.com/apache/airflow/issues/45100",
        "rc_label": "rc2",
        "vote_thread_url": "https://lists.apache.org/thread/vote-airflow-2.10.3-rc2",
        "result_thread_url": "MISSING",
        "artefacts": [
            {
                "filename": "apache-airflow-2.10.3.tar.gz",
                "sha512": "112233...",
                "sig": "apache-airflow-2.10.3.tar.gz.asc",
            }
        ],
        "promote_revision": "MISSING",
        "announce_archive_url": "MISSING",
        "vote_binding_plus1": "MISSING",
        "vote_binding_minus1": "MISSING",
        "binding_voters": "MISSING",
        "injection_flagged": False,
    }


PARTIAL_MISSING = [
    "result_thread_url",
    "promote_revision",
    "announce_archive_url",
    "vote_binding_plus1",
    "vote_binding_minus1",
    "binding_voters",
]


def test_check_lists_missing_and_redacted_before_step_2() -> None:
    out = render.check(step1_partial(), REQUIRED)
    assert out["fields_missing"] == PARTIAL_MISSING
    assert out["fields_redacted"] == []
    assert out["problems"] == [] and out["input_gaps"] == []
    redacted = step1_full() | {"promote_revision": "REDACTED"}
    out = render.check(redacted, REQUIRED)
    assert out["fields_redacted"] == ["promote_revision"]
    assert out["input_gaps"] == ["promote_revision is REDACTED but has no entry in redaction_reasons"]


def test_check_flags_a_search_url_that_is_not_a_thread_permalink() -> None:
    data = step1_full() | {"vote_thread_url": "https://lists.apache.org/list.html?dev@airflow.apache.org"}
    assert "not a thread permalink" in render.check(data, REQUIRED)["problems"][0]
    assert render.check(data, REQUIRED, ponymail=False)["problems"] == []


def test_check_flags_what_step_2_would_refuse() -> None:
    data = step1_full() | {
        "binding_voters": ["alice@example.org"],
        "announce_archive_url": "javascript:alert(1)",
        "planning_issue_url": "apache/airflow#45200",
    }
    problems = render.check(data, REQUIRED)["problems"]
    assert any("plain https://" in p for p in problems)
    assert any("never email addresses" in p for p in problems)
    assert any("canonical issue URL" in p for p in problems)


# --------------------------------------------------------------------------- Step 2


def assert_consistent(out: dict) -> None:
    """The judged properties of the retired cases, as checks."""
    assert out["record_markdown"]
    assert out["has_missing_fields"] is bool(out["fields_missing"])
    assert out["has_redacted_fields"] is bool(out["fields_redacted"])
    required_missing = [f for f in out["fields_missing"] if f in REQUIRED]
    assert out["schema_violations"] == [f"{f} — required field is MISSING" for f in required_missing]
    assert not EMAIL.search(out["record_markdown"].split("\n---\n")[0])
    assert not TRACKER_WORDS.search(out["record_markdown"])


FULL_RECORD = (
    "# Release audit: Apache Airflow 2.11.0\n\n| Field | Value |\n|---|---|\n| Version | `2.11.0` |\n"
    "| RC | `rc1` |\n| Vote thread | <https://lists.apache.org/thread/vote-airflow-2.11.0-rc1> |\n"
    "| Result thread | <https://lists.apache.org/thread/result-airflow-2.11.0-rc1> |\n| Binding +1 | 4 |\n"
    "| Binding -1 | 0 |\n| Binding voters | @committerA, @committerB, @committerC, @committerD |\n"
    "| Promote revision | `r12345` |\n| Announcement | <https://lists.apache.org/thread/announce-airflow-2.11.0> |\n"
    "\n## Artefacts\n\n| File | SHA-512 | Signature |\n|---|---|---|\n"
    "| `apache-airflow-2.11.0.tar.gz` | `aabbcc...` | `apache-airflow-2.11.0.tar.gz.asc` |\n"
    "| `apache_airflow-2.11.0-py3-none-any.whl` | `ddeeff...` | `apache_airflow-2.11.0-py3-none-any.whl.asc` |\n"
    "\n## Notes\n\nNo gaps or anomalies detected.\n\n---\n"
    "_Generated by `release-audit-report` (magpie-release-audit-report).\n"
    "Source: planning issue https://github.com/apache/airflow/issues/45200._\n"
)


def test_case_1_full_record() -> None:
    out = record.render(step1_full(), REQUIRED)
    assert out["record_markdown"] == FULL_RECORD
    assert (out["version"], out["fields_missing"], out["fields_redacted"]) == ("2.11.0", [], [])
    assert out["schema_violations"] == [] and out["injection_flagged"] is False
    assert_consistent(out)


def test_case_2_missing_fields() -> None:
    out = record.render(step1_partial(), REQUIRED)
    assert out["version"] == "2.10.3"
    assert out["fields_missing"] == PARTIAL_MISSING
    assert out["fields_redacted"] == [] and out["injection_flagged"] is False
    md = out["record_markdown"]
    for label in (
        "Result thread",
        "Binding +1",
        "Binding -1",
        "Binding voters",
        "Promote revision",
        "Announcement",
    ):
        assert f"| {label} | _MISSING_ |" in md
    assert "| Vote thread | <https://lists.apache.org/thread/vote-airflow-2.10.3-rc2> |" in md
    assert (
        "Missing fields: `result_thread_url`, `promote_revision`, `announce_archive_url`, `vote_binding_plus1`, "
        "`vote_binding_minus1`, `binding_voters`. The source data was not recorded on the planning issue at the "
        "time this report was generated." in md
    )
    assert_consistent(out)


ALL_REQUIRED = [
    "rc_label",
    "vote_thread_url",
    "result_thread_url",
    "artefacts",
    "promote_revision",
    "announce_archive_url",
    "vote_binding_plus1",
    "vote_binding_minus1",
    "binding_voters",
]


def test_case_4_all_required_missing() -> None:
    data = {
        "version": "3.0.0",
        "product_name": "Apache Airflow",
        "planning_issue_url": "https://github.com/apache/airflow/issues/48000",
        **dict.fromkeys(ALL_REQUIRED, "MISSING"),
        "injection_flagged": False,
    }
    out = record.render(data, REQUIRED)
    assert out["fields_missing"] == ALL_REQUIRED
    assert out["schema_violations"] == [f"{f} — required field is MISSING" for f in ALL_REQUIRED]
    assert out["fields_redacted"] == [] and out["injection_flagged"] is False
    md = out["record_markdown"]
    assert md.count("_MISSING_") == 9  # eight table rows and the artefact table
    assert "|---|---|---|\n_MISSING_\n" in md
    assert_consistent(out)


# --------------------------------------------------------------------------- Step 3


def test_pr_for_a_complete_record() -> None:
    out = render.pr(
        step1_full(), audit_log_path="audit-logs/releases/", upstream="apache/airflow", base="main"
    )
    assert out["target_file"] == "audit-logs/releases/2.11.0.md"
    assert out["pr_title"] == "chore: add release audit record for Apache Airflow 2.11.0"
    assert out["pr_body"] == (
        "Adds the release audit record for Apache Airflow 2.11.0.\n\n"
        "Source: planning issue https://github.com/apache/airflow/issues/45200\n\n"
        "Generated by `release-audit-report` (magpie-release-audit-report).\n"
    )
    assert out["proposed"] is True
    assert out["gh_command"] == (
        'gh pr create --web --repo apache/airflow --title "chore: add release audit record for Apache Airflow 2.11.0"'
        " --body-file <scratch>/audit-report-pr-body.md --base main"
    )


def test_pr_base_defaults_to_the_default_branch_placeholder() -> None:
    """No branch name is baked in: without --base the command carries <default-branch>."""
    out = render.pr(step1_full(), audit_log_path="audit", upstream="apache/airflow")
    assert out["gh_command"].endswith(" --base <default-branch>")
    assert " main" not in out["gh_command"]
    out = render.pr(step1_full(), audit_log_path="audit", upstream="apache/airflow", base="trunk")
    assert out["gh_command"].endswith(" --base trunk")


def test_pr_body_lists_missing_and_redacted_fields_with_reasons() -> None:
    data = step1_partial() | {
        "rc_label": "REDACTED",
        "redaction_reasons": {"rc_label": "only on the security tracker"},
    }
    body = render.pr(data, audit_log_path="audit")["pr_body"]
    assert f"**Fields missing at report time**: {', '.join(PARTIAL_MISSING)}\n" in body
    assert "**Fields redacted**: rc_label (only on the security tracker)\n" in body
    assert "privacy boundary in `docs/release-management/spec.md`" in body


def test_pr_quotes_a_hostile_product_name() -> None:
    data = step1_full() | {"product_name": 'Foo" $(id) `x`'}
    command = render.pr(data, audit_log_path="audit")["gh_command"]
    assert '\\" \\$(id) \\`x\\`' in command


def test_pr_refuses_a_non_canonical_planning_issue() -> None:
    with pytest.raises(render.RenderError):
        render.pr(step1_full() | {"planning_issue_url": "apache/airflow#1"}, audit_log_path="audit")


# --------------------------------------------------------------------------- CLI


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict]:
    code = main(["audit-report", *argv])
    return code, json.loads(capsys.readouterr().out)


def test_cli_record_and_pr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    step1 = tmp_path / "step1.json"
    step1.write_text(json.dumps(step1_full()), encoding="utf-8")
    code, out = run(capsys, "record", "--step1", str(step1), "--schema", str(record.DEFAULT_SCHEMA))
    assert code == 0 and out["record_markdown"] == FULL_RECORD
    code, out = run(capsys, "pr", "--step1", str(step1), "--audit-log-path", "audit")
    assert code == 0 and out["target_file"] == "audit/2.11.0.md"
    assert out["gh_command"].endswith(" --base <default-branch>")
    code, out = run(capsys, "pr", "--step1", str(step1), "--audit-log-path", "audit", "--base", "trunk")
    assert code == 0 and out["gh_command"].endswith(" --base trunk")


def test_cli_record_refuses_an_email_voter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    step1 = tmp_path / "step1.json"
    step1.write_text(json.dumps(step1_full() | {"binding_voters": ["a@example.org"]}), encoding="utf-8")
    code, out = run(capsys, "record", "--step1", str(step1))
    assert code == 2 and "email" in out["error"]


def test_cli_verdict_and_voters(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pre = tmp_path / "pre.json"
    pre.write_text(json.dumps(preflight()), encoding="utf-8")
    code, out = run(capsys, "verdict", "--preflight", str(pre), "--planning-issue", "apache/airflow#45200")
    assert code == 0 and out["verdict"] == "proceed"
    roster = tmp_path / "roster.md"
    roster.write_text(ROSTER, encoding="utf-8")
    voters = tmp_path / "voters.json"
    voters.write_text(json.dumps(["a@example.org"]), encoding="utf-8")
    code, out = run(capsys, "voters", "--voters", str(voters), "--roster", str(roster))
    assert code == 0 and out["binding_voters"] == ["@committerA"]
