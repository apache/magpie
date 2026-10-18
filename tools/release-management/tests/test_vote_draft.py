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
"""release-vote-draft: the Step 0 verdict and the Step 2 / Step 3 renders.

The scripted cases of the retired model-graded suites `step-0-preflight`
(cases 2-3), `step-2-vote-draft` (cases 1 and 3, and the render half of case 2)
and `step-3-planning-comment` (cases 1-2) live here, named after each former
case, with the same scenario and the same expected body.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from release_management.cli import main
from release_management.rc_cut import render as rc_cut
from release_management.vote_draft import render

CASE_1_STANDARD_VOTE_BODY = (
    "To: dev@airflow.apache.org\n"
    "Subject: [VOTE] Release Apache Airflow 2.11.0 from 2.11.0-rc1\n"
    "\n"
    "Hi all,\n"
    "\n"
    "I propose we release the following artifacts as Apache Airflow 2.11.0.\n"
    "\n"
    "The release artifacts, signatures, and checksums are available at:\n"
    "  https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/\n"
    "\n"
    "The release tag to be voted upon:\n"
    "  https://github.com/apache/airflow/releases/tag/2.11.0-rc1\n"
    "\n"
    "The changelog for this release:\n"
    "  https://github.com/apache/airflow/blob/2.11.0-rc1/CHANGELOG.md\n"
    "\n"
    "Keys to verify artifact signatures:\n"
    "  https://dist.apache.org/repos/dist/release/airflow/KEYS\n"
    "\n"
    "How to verify this candidate before voting\n"
    "------------------------------------------\n"
    "Reproducibility record (from the planning issue):\n"
    "  repository:        https://github.com/apache/airflow\n"
    "  source commit:     1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12\n"
    "  SWHID (content):   swh:1:dir:3b9f0c2e7a1d4f6b8e0a2c4d6f8a0b2c4e6f8a1b;origin=https://github.com/apache/airflow;anchor=swh:1:rev:1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12\n"
    "  SOURCE_DATE_EPOCH: 1758326400\n"
    "  sha512:            3f2a9c\u2026e1 (apache_airflow-2.11.0.tar.gz)\n"
    "\n"
    "Agentic path (any agent with the Magpie release skills, read-only):\n"
    "  /magpie-release-management:verify-rc 2.11.0-rc1\n"
    "  It checks the signature against KEYS, the checksum, licence headers\n"
    "  (RAT), LICENSE/NOTICE, prohibited binaries, dangling links, version\n"
    "  strings, rebuilds the source artefact from the tag to confirm it is\n"
    "  byte-identical to what is staged and that its SWHID is the recorded\n"
    "  one, and rebuilds and compares every convenience artefact.\n"
    "\n"
    "Manual path (the same checks, longhand):\n"
    "  https://github.com/apache/airflow/blob/2.11.0-rc1/docs/verifying-a-release-candidate.md\n"
    "  Reproducibility background: https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md\n"
    "\n"
    "A binding +1 means you downloaded the artefact, verified it, and built\n"
    "and tested it on your own hardware; the tools above are an aid, not a\n"
    "substitute (https://www.apache.org/legal/release-policy.html#release-approval).\n"
    "\n"
    "Please vote to release:\n"
    "  [ ] +1  Release Apache Airflow 2.11.0\n"
    "  [ ] +0\n"
    "  [ ] -1  Do not release (please comment with specific reasons)\n"
    "\n"
    "This vote is open for at least 72 hours.\n"
    "\n"
    "Thanks,\n"
    "<RM name>"
)

CASE_2_EXPEDITED_VOTE_BODY = (
    "To: dev@airflow.apache.org\n"
    "Subject: [VOTE] Release Apache Airflow 2.10.4 from 2.10.4-rc1\n"
    "\n"
    "Hi all,\n"
    "\n"
    "I propose we release the following artifacts as Apache Airflow 2.10.4.\n"
    "\n"
    "The release artifacts, signatures, and checksums are available at:\n"
    "  https://dist.apache.org/repos/dist/dev/airflow/2.10.4-rc1/\n"
    "\n"
    "The release tag to be voted upon:\n"
    "  https://github.com/apache/airflow/releases/tag/2.10.4-rc1\n"
    "\n"
    "The changelog for this release:\n"
    "  https://github.com/apache/airflow/blob/2.10.4-rc1/CHANGELOG.md\n"
    "\n"
    "Keys to verify artifact signatures:\n"
    "  https://dist.apache.org/repos/dist/release/airflow/KEYS\n"
    "\n"
    "How to verify this candidate before voting\n"
    "------------------------------------------\n"
    "Reproducibility record (from the planning issue):\n"
    "  repository:        https://github.com/apache/airflow\n"
    "  source commit:     a1b2c3d4e5f60718293a4b5c6d7e8f9012345678\n"
    "  SWHID (content):   swh:1:dir:9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c;origin=https://github.com/apache/airflow;anchor=swh:1:rev:a1b2c3d4e5f60718293a4b5c6d7e8f9012345678\n"
    "  SOURCE_DATE_EPOCH: 1758400000\n"
    "  sha512:            77ab\u202610 (apache_airflow-2.10.4.tar.gz)\n"
    "\n"
    "Agentic path (any agent with the Magpie release skills, read-only):\n"
    "  /magpie-release-management:verify-rc 2.10.4-rc1\n"
    "  It checks the signature against KEYS, the checksum, licence headers\n"
    "  (RAT), LICENSE/NOTICE, prohibited binaries, dangling links, version\n"
    "  strings, rebuilds the source artefact from the tag to confirm it is\n"
    "  byte-identical to what is staged and that its SWHID is the recorded\n"
    "  one, and rebuilds and compares every convenience artefact.\n"
    "\n"
    "Manual path (the same checks, longhand):\n"
    "  https://github.com/apache/airflow/blob/2.10.4-rc1/docs/verifying-a-release-candidate.md\n"
    "  Reproducibility background: https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md\n"
    "\n"
    "A binding +1 means you downloaded the artefact, verified it, and built\n"
    "and tested it on your own hardware; the tools above are an aid, not a\n"
    "substitute (https://www.apache.org/legal/release-policy.html#release-approval).\n"
    "\n"
    "Please vote to release:\n"
    "  [ ] +1  Release Apache Airflow 2.10.4\n"
    "  [ ] +0\n"
    "  [ ] -1  Do not release (please comment with specific reasons)\n"
    "\n"
    "This vote is open for at least 48 hours.\n"
    "\n"
    "[EXPEDITED: Time-sensitive fix release; abbreviated window approved by PMC chair. ASF policy requires this deviation to be noted in the project's next board report.]\n"
    "\n"
    "Thanks,\n"
    "<RM name>"
)

CASE_3_SKIP_VERIFY_BODY = (
    "To: dev@airflow.apache.org\n"
    "Subject: [VOTE] Release Apache Airflow 2.11.0 from 2.11.0-rc3\n"
    "\n"
    "Hi all,\n"
    "\n"
    "I propose we release the following artifacts as Apache Airflow 2.11.0.\n"
    "\n"
    "The release artifacts, signatures, and checksums are available at:\n"
    "  https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc3/\n"
    "\n"
    "The release tag to be voted upon:\n"
    "  https://github.com/apache/airflow/releases/tag/2.11.0-rc3\n"
    "\n"
    "The changelog for this release:\n"
    "  https://github.com/apache/airflow/blob/2.11.0-rc3/CHANGELOG.md\n"
    "\n"
    "Keys to verify artifact signatures:\n"
    "  https://dist.apache.org/repos/dist/release/airflow/KEYS\n"
    "\n"
    "How to verify this candidate before voting\n"
    "------------------------------------------\n"
    "Agentic path (any agent with the Magpie release skills, read-only):\n"
    "  /magpie-release-management:verify-rc 2.11.0-rc3\n"
    "  It checks the signature against KEYS, the checksum, licence headers\n"
    "  (RAT), LICENSE/NOTICE, prohibited binaries, dangling links, version\n"
    "  strings, rebuilds the source artefact from the tag to confirm it is\n"
    "  byte-identical to what is staged and that its SWHID is the recorded\n"
    "  one, and rebuilds and compares every convenience artefact.\n"
    "\n"
    "Manual path (the same checks, longhand):\n"
    "  https://github.com/apache/airflow/blob/2.11.0-rc3/docs/verifying-a-release-candidate.md\n"
    "  Reproducibility background: https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md\n"
    "\n"
    "A binding +1 means you downloaded the artefact, verified it, and built\n"
    "and tested it on your own hardware; the tools above are an aid, not a\n"
    "substitute (https://www.apache.org/legal/release-policy.html#release-approval).\n"
    "\n"
    "Please vote to release:\n"
    "  [ ] +1  Release Apache Airflow 2.11.0\n"
    "  [ ] +0\n"
    "  [ ] -1  Do not release (please comment with specific reasons)\n"
    "\n"
    "This vote is open for at least 72 hours.\n"
    "\n"
    "[SKIP-VERIFY: release-verify-rc was not run for this RC; the RM accepted this with the reason: rc3 is identical to rc2 except for a KEYS fix; RM confirmed all artefact checksums match rc2 which passed verify.]\n"
    "\n"
    "Thanks,\n"
    "<RM name>"
)

CASE_1_STANDARD_COMMENT = (
    "**Vote open:** `[VOTE] Release Apache Airflow 2.11.0 from 2.11.0-rc1`\n"
    "sent to `dev@airflow.apache.org` on 2026-06-11 15:00 UTC.\n"
    "Vote window closes: 2026-06-14 15:00 UTC (minimum).\n"
    "\n"
    "Next step: `release-vote-tally` after the window closes."
)

CASE_2_EXPEDITED_COMMENT = (
    "**Vote open (expedited):** `[VOTE] Release Apache Airflow 2.10.4 from 2.10.4-rc1`\n"
    "sent to `dev@airflow.apache.org` on 2026-06-11 10:00 UTC.\n"
    "Vote window closes: 2026-06-13 10:00 UTC (minimum, 48-hour expedited window).\n"
    "\n"
    "**Expedited:** Time-sensitive fix release; abbreviated window approved by PMC chair.\n"
    "Reminder: note this deviation in the project's next board report per ASF policy.\n"
    "\n"
    "Next step: `release-vote-tally` after the window closes."
)

AIRFLOW = "https://github.com/apache/airflow"


def loaded(
    rc_id: str = "2.11.0-rc1", hours: int = 72, *, backend: str | None = None, **meta: Any
) -> dict[str, Any]:
    version, rc = rc_id.split("-")
    base: dict[str, Any] = {
        "version": version,
        "rc_number": rc,
        "keys_url": "https://dist.apache.org/repos/dist/release/airflow/KEYS",
        "vote_list": "dev@airflow.apache.org",
        "vote_window_hours": str(hours),
        "subject_template": "[VOTE] Release Apache Airflow <version> from <version>-<rcN>",
        "vote_backend": "manual",
        "atr_platform_url": None,
        "verification_doc_url": f"{AIRFLOW}/blob/{rc_id}/docs/verifying-a-release-candidate.md",
        "reproducibility_doc_url": "https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md",
        "verification_skill": "magpie-release-management:verify-rc",
        "signing_mode": "rm-key",
        "convenience_artefacts": [],
        "staging_url": f"https://dist.apache.org/repos/dist/dev/airflow/{rc_id}/",
    }
    config = {"release_dist_backend": backend, "project_dist_name": "airflow"} if backend else {}
    return {"config": config, "metadata": base | meta}


def draft(rc_id: str = "2.11.0-rc1", hours: int = 72, **kw: Any) -> render.VoteDraft:
    return render.VoteDraft.from_load(loaded(rc_id, hours, **kw), product_name="Apache Airflow")


def urls(rc_id: str) -> dict[str, Any]:
    return {
        "tag_url": f"{AIRFLOW}/releases/tag/{rc_id}",
        "changelog_url": f"{AIRFLOW}/blob/{rc_id}/CHANGELOG.md",
    }


def record(commit: str, tree: str, epoch: str, sha: str) -> render.Record:
    return render.Record(
        repository=AIRFLOW,
        commit=commit,
        swhid=f"swh:1:dir:{tree};origin={AIRFLOW};anchor=swh:1:rev:{commit}",
        epoch=epoch,
        sha512=sha,
    )


CASE_1_RECORD = record(
    "1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12",
    "3b9f0c2e7a1d4f6b8e0a2c4d6f8a0b2c4e6f8a1b",
    "1758326400",
    "3f2a9c…e1 (apache_airflow-2.11.0.tar.gz)",
)

# The eval assertions every former step-2 case carried.
VERIFY_ASSERTIONS = {
    "has_verification_section": r"(?i)How to verify this candidate",
    "has_agentic_one_liner": r"magpie-release-management:verify-rc",
    "has_manual_doc_link": r"verifying-a-release-candidate\.md",
    "has_reproducibility_doc_link": r"reproducibility\.md",
    "has_voter_obligation": r"release-approval",
}
EMBARGOED = r"(?i)CVE-\d{4}-\d+|security fix|vulnerability|vulnerabilities"


def assert_verify_section(body: str) -> None:
    for name, pattern in VERIFY_ASSERTIONS.items():
        assert re.search(pattern, body), name
    assert not re.search(EMBARGOED, body)


def preflight(rc_id: str, *, blockers: tuple[str, ...] = (), hours: int = 72) -> dict[str, Any]:
    version, rc = rc_id.split("-")
    return {
        "ok": not blockers,
        "skill": "vote-draft",
        "blockers": list(blockers),
        "warnings": [],
        "values": {
            "version": version,
            "rc_number": rc,
            "vote_window_hours": hours,
            "skip_verify_override": False,
            "expedited": False,
        },
    }


PLANNING = "https://github.com/apache/airflow/issues/45001"


# --- Step 0 -------------------------------------------------------------------


def test_step0_case_1_clean_pass_verdict() -> None:
    out = render.verdict(
        preflight("2.11.0-rc1"), planning_issue=PLANNING, verify_rc_verdict="PASS", verify_rc_for="2.11.0-rc1"
    )
    assert (out["verdict"], out["blockers"], out["skip_verify_override"], out["expedited"]) == (
        "proceed",
        [],
        False,
        False,
    )


def test_step0_case_2_verify_rc_not_run() -> None:
    out = render.verdict(
        preflight("2.11.0-rc2"), planning_issue=PLANNING, verify_rc_verdict="PASS", verify_rc_for="2.11.0-rc1"
    )
    assert out["verdict"] == "blocked"
    assert out["blockers"] == [
        "release-verify-rc has not reported PASS for 2.11.0-rc2; the latest verify result is for rc1, not rc2. "
        "Run release-verify-rc for rc2, or pass --skip-verify-check with a reason."
    ]
    assert (out["skip_verify_override"], out["expedited"]) == (False, False)


def test_step0_case_3_expedited_no_flag() -> None:
    blocker = (
        "vote_window_hours (48) is below the ASF 72-hour floor. Pass --expedited <reason> to proceed with an "
        "abbreviated window, or raise vote_window_hours to at least 72 in release-management-config.md."
    )
    out = render.verdict(
        preflight("2.10.4-rc1", blockers=(blocker,), hours=48),
        planning_issue="https://github.com/apache/airflow/issues/44800",
        verify_rc_verdict="PASS",
        verify_rc_for="2.10.4-rc1",
    )
    assert (out["verdict"], out["blockers"], out["expedited"]) == ("blocked", [blocker], False)


def test_step0_verify_rc_exact_match_only() -> None:
    # A PASS for rc10 is not a PASS for rc1.
    out = render.verdict(
        preflight("2.11.0-rc1"),
        planning_issue=PLANNING,
        verify_rc_verdict="PASS",
        verify_rc_for="2.11.0-rc10",
    )
    assert out["verdict"] == "blocked"


def test_step0_verify_rc_fail_and_none_block_skip_resolves() -> None:
    for verdict, rc in (("FAIL", "2.11.0-rc1"), ("none", None)):
        out = render.verdict(
            preflight("2.11.0-rc1"), planning_issue=PLANNING, verify_rc_verdict=verdict, verify_rc_for=rc
        )
        assert out["verdict"] == "blocked", verdict
    skipped = preflight("2.11.0-rc1")
    skipped["values"]["skip_verify_override"] = True
    out = render.verdict(skipped, planning_issue=PLANNING, verify_rc_verdict="none", verify_rc_for=None)
    assert (out["verdict"], out["blockers"], out["skip_verify_override"]) == ("proceed", [], True)


def test_step0_pass_with_warnings_proceeds_with_a_warning() -> None:
    out = render.verdict(
        preflight("2.11.0-rc1"),
        planning_issue=PLANNING,
        verify_rc_verdict="PASS-WITH-WARNINGS",
        verify_rc_for="2.11.0-rc1",
    )
    assert out["verdict"] == "proceed"
    assert "PASS-WITH-WARNINGS" in out["warnings"][0]


def test_step0_fails_closed_on_an_incomplete_preflight() -> None:
    def run(pre: dict[str, Any], verdict: str = "none", rc: str | None = None) -> dict[str, Any]:
        return render.verdict(pre, planning_issue=PLANNING, verify_rc_verdict=verdict, verify_rc_for=rc)

    assert run({})["verdict"] == "blocked"
    other = preflight("2.11.0-rc1") | {"skill": "vote-tally"}
    assert run(other, "PASS", "2.11.0-rc1")["verdict"] == "blocked"
    out = run(preflight("2.11.0-rc1") | {"ok": False}, "PASS", "2.11.0-rc1")
    assert out["verdict"] == "blocked" and any("ok: true" in b for b in out["blockers"])
    # No version / rc_number: the verify-rc gate cannot be skipped by omission.
    anonymous = preflight("2.11.0-rc1")
    anonymous["values"] |= {"version": None, "rc_number": None}
    out = run(anonymous)
    assert out["verdict"] == "blocked" and any("release-verify-rc gate" in b for b in out["blockers"])
    anonymous["values"]["skip_verify_override"] = True
    assert run(anonymous)["verdict"] == "proceed"


def test_step0_no_planning_issue_blocks() -> None:
    out = render.verdict(
        preflight("2.11.0-rc1"), planning_issue=None, verify_rc_verdict="PASS", verify_rc_for="2.11.0-rc1"
    )
    assert out["verdict"] == "blocked"
    assert "no planning issue" in out["blockers"][0]


# --- Step 2 -------------------------------------------------------------------


def test_step2_case_1_standard_vote() -> None:
    out = render.step2(draft(), record=CASE_1_RECORD, **urls("2.11.0-rc1"))
    assert out["subject"] == "[VOTE] Release Apache Airflow 2.11.0 from 2.11.0-rc1"
    assert out["body"] == CASE_1_STANDARD_VOTE_BODY
    assert (out["vote_window_hours"], out["expedited"], out["skip_verify_logged"]) == (72, False, False)
    assert_verify_section(out["body"])
    assert "SOURCE_DATE_EPOCH" in out["body"]
    assert re.search(r"swh:1:dir:[0-9a-f]{40}", out["body"])
    assert out["warnings"] == []


def test_step2_case_2_expedited_vote_render() -> None:
    # The reword ("Critical security fix for CVE-…" → neutral) stays a model eval;
    # this is the render once the agent passes the neutral reason.
    out = render.step2(
        draft("2.10.4-rc1", 48),
        record=record(
            "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
            "9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c",
            "1758400000",
            "77ab…10 (apache_airflow-2.10.4.tar.gz)",
        ),
        expedited="Time-sensitive fix release; abbreviated window approved by PMC chair.",
        **urls("2.10.4-rc1"),
    )
    assert out["body"] == CASE_2_EXPEDITED_VOTE_BODY
    assert (out["vote_window_hours"], out["expedited"]) == (48, True)
    assert out["warnings"] == []
    assert_verify_section(out["body"])


def test_step2_raw_security_reason_is_flagged_for_rewording() -> None:
    out = render.step2(
        draft("2.10.4-rc1", 48),
        expedited="Critical security fix for CVE-2026-12345; abbreviated window approved by PMC chair.",
        **urls("2.10.4-rc1"),
    )
    assert out["warnings"] and "reword it neutrally" in out["warnings"][0]
    assert "CVE-2026-12345" in out["warnings"][0]


def test_step2_embargo_scan_covers_the_whole_public_body() -> None:
    # The --skip-verify-check reason is rendered verbatim into the public [VOTE] body.
    out = render.step2(draft(), skip_verify="CVE-2026-1234 security fix", **urls("2.11.0-rc1"))
    assert "CVE-2026-1234" in out["body"]
    assert out["warnings"] and "reword it neutrally" in out["warnings"][0]
    assert "CVE-2026-1234" in out["warnings"][0] and "security" in out["warnings"][0]
    canned = "Vote on <version>; it closes a vulnerability.\n"
    flagged = render.step2(draft(), canned_body=canned, **urls("2.11.0-rc1"))
    assert any("'vulnerability'" in w for w in flagged["warnings"])


def test_step2_canned_body_leftover_placeholder_is_refused() -> None:
    # <svn_revision> on a non-svnpubsub backend has no value, and <foo> is unknown.
    for canned, token in (
        ("Vote on <version> (r<svn_revision>).\n", "<svn_revision>"),
        ("Hi <foo>\n", "<foo>"),
    ):
        with pytest.raises(render.RenderError, match=token):
            render.step2(draft(), canned_body=canned, **urls("2.11.0-rc1"))
    signed = render.step2(
        draft(), canned_body="Vote on <version>.\n\nThanks,\n<RM name>\n", **urls("2.11.0-rc1")
    )
    assert "<RM name>" in signed["body"]


def test_step2_case_3_skip_verify_logged() -> None:
    out = render.step2(
        draft("2.11.0-rc3"),
        skip_verify="rc3 is identical to rc2 except for a KEYS fix; RM confirmed all artefact checksums match rc2 which passed verify.",
        **urls("2.11.0-rc3"),
    )
    assert out["body"] == CASE_3_SKIP_VERIFY_BODY
    assert (out["skip_verify_logged"], out["expedited"]) == (True, False)
    assert "SOURCE_DATE_EPOCH" not in out["body"]  # no record on the planning issue: omitted, never invented
    assert_verify_section(out["body"])


def test_step2_below_floor_without_expedited_is_refused() -> None:
    with pytest.raises(render.RenderError, match="72-hour floor"):
        render.step2(draft("2.10.4-rc1", 48), **urls("2.10.4-rc1"))


def test_step2_missing_metadata_is_refused_never_invented() -> None:
    with pytest.raises(render.RenderError, match="tag_url"):
        render.step2(draft(), tag_url=None, changelog_url="c")


def test_step2_svnpubsub_needs_the_svn_revision() -> None:
    with pytest.raises(render.RenderError, match="svn_revision"):
        render.step2(draft(backend="svnpubsub"), **urls("2.11.0-rc1"))
    out = render.step2(draft(backend="svnpubsub"), svn_revision="71234", **urls("2.11.0-rc1"))
    assert (
        "  https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/\n  (SVN revision: r71234)\n"
        in out["body"]
    )


def test_step2_partial_record_renders_only_what_it_has() -> None:
    out = render.step2(draft(), record=render.Record(commit="abc123"), **urls("2.11.0-rc1"))
    assert (
        "Reproducibility record (from the planning issue):\n  source commit:     abc123\n\nAgentic path"
        in out["body"]
    )
    assert "SOURCE_DATE_EPOCH" not in out["body"]


def test_step2_agentic_path_is_verbatim_without_record_or_convenience() -> None:
    body = render.step2(draft(), **urls("2.11.0-rc1"))["body"]
    assert render.AGENTIC_PATH.format(skill="magpie-release-management:verify-rc", tag="2.11.0-rc1") in body
    assert "that its SWHID is the recorded" in body
    assert "Convenience artefacts" not in body


def test_step2_convenience_artefacts_block() -> None:
    conv = [
        {
            "name": "apache_airflow-<version>-py3-none-any.whl",
            "staging": "dist-dev",
            "vote_included": True,
            "reproducibility": "byte-identical",
        },
        {
            "name": "airflow-image",
            "staging": "registry-staging",
            "vote_included": False,
            "reproducibility": "byte-identical",
        },
    ]
    body = render.step2(draft(convenience_artefacts=conv), **urls("2.11.0-rc1"))["body"]
    assert "Convenience artefacts (built from the source above; not the release itself):" in body
    assert (
        "  apache_airflow-2.11.0-py3-none-any.whl  —  staged at dist-dev  — included in this vote\n" in body
    )
    assert "  airflow-image  —  staged at registry-staging\n" in body
    assert "(byte-identical); a convenience artefact that does not" in body
    assert body.index("Convenience artefacts") < body.index("How to verify this candidate")


def test_step2_atr_backend_adds_the_candidate_page_and_the_command() -> None:
    d = draft(vote_backend="atr", backend="svnpubsub")
    with pytest.raises(render.RenderError, match="atr_candidate_url"):
        render.step2(d, svn_revision="1", **urls("2.11.0-rc1"))
    out = render.step2(
        d,
        svn_revision="1",
        atr_candidate_url="https://release-test.apache.org/c/airflow/2.11.0",
        **urls("2.11.0-rc1"),
    )
    assert (
        "ATR check results for this candidate:\n  https://release-test.apache.org/c/airflow/2.11.0"
        in out["body"]
    )
    cmd = out["atr_vote_command"]
    assert "atr vote start -m dev@airflow.apache.org" in cmd
    assert "--duration 72" in cmd
    assert '--subject "[VOTE] Release Apache Airflow 2.11.0 from 2.11.0-rc1"' in cmd
    assert "--no-auto-publish" in cmd
    assert "  airflow 2.11.0\n" in cmd
    assert "/dist/dev/airflow/2.11.0-rc1/" in out["body"]  # voters still fetch from the dist backend
    with_rev = render.step2(
        d, svn_revision="1", atr_candidate_url="u", atr_revision="00003", **urls("2.11.0-rc1")
    )["atr_vote_command"]
    assert "--revision 00003 \\\n  airflow 2.11.0" in with_rev


def test_step2_atr_command_quotes_a_hostile_subject() -> None:
    d = draft(vote_backend="atr", backend="svnpubsub", subject_template='[VOTE] $(touch pwned) "x" <version>')
    cmd = render.step2(d, svn_revision="1", atr_candidate_url="u", **urls("2.11.0-rc1"))["atr_vote_command"]
    assert '--subject "[VOTE] \\$(touch pwned) \\"x\\" 2.11.0"' in cmd


def test_step2_manual_backend_has_no_atr_command() -> None:
    assert render.step2(draft(), **urls("2.11.0-rc1"))["atr_vote_command"] == ""


def test_step2_ci_automated_adds_the_trusted_hardware_paragraph() -> None:
    body = render.step2(draft(signing_mode="ci-automated"), planning_issue=PLANNING, **urls("2.11.0-rc1"))[
        "body"
    ]
    assert f"--trusted-hardware --post-to {PLANNING} and say so in your" in body


def test_step2_canned_body_gets_the_verify_section_appended() -> None:
    canned = "Hello <vote_list>,\nPlease vote on <Product Name> <version> (<version>-rcN) at <staging_url>.\n"
    out = render.step2(draft(), canned_body=canned, skip_verify="KEYS-only respin", **urls("2.11.0-rc1"))
    assert out["body"].startswith(
        "Hello dev@airflow.apache.org,\nPlease vote on Apache Airflow 2.11.0 (2.11.0-rc1) at "
        "https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/.\n\nHow to verify this candidate before voting"
    )
    assert out["verify_section_appended"] is True
    assert any("canned [VOTE] block should gain it" in w for w in out["warnings"])
    assert out["body"].endswith(
        "[SKIP-VERIFY: release-verify-rc was not run for this RC; the RM accepted this with the reason: KEYS-only respin.]"
    )
    assert_verify_section(out["body"])


def test_step2_canned_body_with_the_section_is_left_alone() -> None:
    canned = "Vote on <version>.\n\nHow to verify this candidate before voting\n... project text ...\n"
    out = render.step2(draft(), canned_body=canned, **urls("2.11.0-rc1"))
    assert out["verify_section_appended"] is False
    assert out["body"].count("How to verify this candidate") == 1


def test_step2_unset_verification_doc_links_the_framework_page() -> None:
    out = render.step2(draft(verification_doc_url=None), **urls("2.11.0-rc1"))
    assert "not configured yet" in out["body"]
    assert any("vote_verification_doc_url is unset" in w for w in out["warnings"])


def test_step2_record_parsed_from_the_rc_cut_comment() -> None:
    digest = "3f2a9c" + "0" * 122  # rc-cut records a full 128-hex sha512 only
    cut = rc_cut.RcCut.from_load(
        {
            "build": {"expected_artefacts": [{"name": "apache_airflow-2.11.0.tar.gz", "kind": "source"}]},
            "metadata": {
                "version": "2.11.0",
                "rc_number": "rc1",
                "expected_artefacts": ["apache_airflow-2.11.0.tar.gz"],
                "staging_url": "https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/",
            },
        },
        upstream="apache/airflow",
        project="airflow",
    )
    printed = (
        "commit 1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12\nSOURCE_DATE_EPOCH 1758326400\nsha512 "
        + digest
        + "\n"
        "swhid_rev swh:1:rev:1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12;origin=https://github.com/apache/airflow\n"
        "swhid_dir swh:1:dir:3b9f0c2e7a1d4f6b8e0a2c4d6f8a0b2c4e6f8a1b;origin=https://github.com/apache/airflow;"
        "anchor=swh:1:rev:1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12\n"
    )
    comment = rc_cut.step4(cut, record=rc_cut.parse_record(printed))["comment"]
    parsed = render.parse_rc_comment(comment)
    assert parsed == render.Record(
        repository=AIRFLOW,
        commit="1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12",
        swhid=CASE_1_RECORD.swhid,
        epoch="1758326400",
        sha512=f"{digest} (apache_airflow-2.11.0.tar.gz)",
    )
    # Fields rc-cut still shows as "paste from" are absent, never invented.
    empty = render.parse_rc_comment(rc_cut.step4(cut)["comment"])
    assert empty.lines() == []


# --- Step 3 -------------------------------------------------------------------


def test_step3_case_1_standard_comment() -> None:
    out = render.step3(draft(), sent_at="2026-06-11 15:00 UTC")
    assert out["comment_body"] == CASE_1_STANDARD_COMMENT
    assert out["proposed"] is True
    assert out["window_closes_utc"] == "2026-06-14T15:00:00Z"


def test_step3_case_2_expedited_note() -> None:
    out = render.step3(
        draft("2.10.4-rc1", 48),
        sent_at="2026-06-11T10:00:00Z",
        expedited="Time-sensitive fix release; abbreviated window approved by PMC chair.",
    )
    assert out["comment_body"] == CASE_2_EXPEDITED_COMMENT
    assert out["proposed"] is True
    assert not re.search(EMBARGOED, out["comment_body"])
    flagged = render.step3(
        draft("2.10.4-rc1", 48),
        sent_at="2026-06-11T10:00:00Z",
        expedited="Critical security fix for CVE-2026-12345; abbreviated window approved by PMC chair.",
    )
    assert flagged["warnings"]


def test_step3_embargo_scan_covers_the_whole_comment() -> None:
    # An RM-edited subject lands in the public planning-issue comment too.
    out = render.step3(
        draft(), sent_at="2026-06-11 15:00 UTC", subject="[VOTE] Release 2.11.0 (CVE-2026-1234)"
    )
    assert out["warnings"] and "planning-issue comment" in out["warnings"][0]
    assert "CVE-2026-1234" in out["warnings"][0]
    assert render.step3(draft(), sent_at="2026-06-11 15:00 UTC")["warnings"] == []


def test_step3_deadline_crosses_a_month_and_honours_offsets() -> None:
    out = render.step3(draft(hours=120), sent_at="2026-06-28T23:30:00+02:00")
    assert out["window_closes_utc"] == "2026-07-03T21:30:00Z"
    assert "on 2026-06-28 21:30 UTC." in out["comment_body"]


def test_step3_rejects_a_naive_time() -> None:
    with pytest.raises(render.RenderError, match="timezone"):
        render.step3(draft(), sent_at="2026-06-11T15:00:00")


# --- CLI ----------------------------------------------------------------------


def test_cli_render_verdict_and_refusal(tmp_path, capsys) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    base = ["vote-draft", "render", "--load", str(load), "--product-name", "Apache Airflow"]
    assert main([*base, "--step", "3", "--sent-at", "2026-06-11T15:00:00Z"]) == 0
    assert json.loads(capsys.readouterr().out)["comment_body"] == CASE_1_STANDARD_COMMENT
    assert main([*base, "--step", "2"]) == 2
    refused = json.loads(capsys.readouterr().out)
    assert refused["ok"] is False and "tag_url" in refused["refused"]
    pre = tmp_path / "pre.json"
    pre.write_text(json.dumps(preflight("2.11.0-rc1")), encoding="utf-8")
    code = main(
        [
            "vote-draft",
            "verdict",
            "--preflight",
            str(pre),
            "--planning-issue",
            PLANNING,
            "--verify-rc-verdict",
            "PASS",
            "--verify-rc-for",
            "2.11.0-rc1",
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "proceed"


# --- adversarial-review regressions ---------------------------------------------


def _rc_comment(
    artefacts: list[tuple[str, str]], *, convenience: list[dict[str, Any]] | None = None, fmt: str = "tar.gz"
) -> str:
    digest = "ab" * 64
    cut = rc_cut.RcCut.from_load(
        {
            "build": {"expected_artefacts": [{"name": n, "kind": k} for n, k in artefacts]},
            "metadata": {
                "version": "2.11.0",
                "rc_number": "rc1",
                "expected_artefacts": [n for n, _ in artefacts],
                "source_archive_format": fmt,
                "convenience_artefacts": convenience or [],
            },
        },
        upstream="apache/airflow",
        project="airflow",
    )
    printed = f"commit {'1' * 40}\nSOURCE_DATE_EPOCH 1758326400\nsha512 {digest}\n"
    return rc_cut.step4(cut, record=rc_cut.parse_record(printed))["comment"]


def test_rc_comment_sha512_labels_the_source_artefact_not_the_first_listed() -> None:
    comment = _rc_comment(
        [
            ("apache_airflow-2.11.0-py3-none-any.whl", "convenience"),
            ("apache_airflow-2.11.0.tar.gz", "source"),
        ],
        convenience=[{"name": "apache_airflow-<version>-py3-none-any.whl", "kind": "wheel"}],
    )
    assert render.parse_rc_comment(comment).sha512 == f"{'ab' * 64} (apache_airflow-2.11.0.tar.gz)"


def test_rc_comment_sha512_skips_a_convenience_artefact_in_the_source_format() -> None:
    comment = _rc_comment(
        [("apache-foo-2.11.0-bin.tar.gz", "convenience"), ("apache-foo-2.11.0-src.tar.gz", "source")],
        convenience=[{"name": "apache-foo-<version>-bin.tar.gz", "kind": "binary"}],
    )
    assert render.parse_rc_comment(comment).sha512 == f"{'ab' * 64} (apache-foo-2.11.0-src.tar.gz)"


def test_rc_comment_sha512_custom_format_found_by_its_source_name() -> None:
    comment = _rc_comment(
        [("apache-foo-2.11.0-bin.tar.gz", "convenience"), ("apache-foo-2.11.0-source-release.zip", "source")]
    )
    assert render.parse_rc_comment(comment).sha512 == f"{'ab' * 64} (apache-foo-2.11.0-source-release.zip)"


def test_rc_comment_sha512_is_left_unlabelled_when_the_source_is_unclear() -> None:
    comment = _rc_comment(
        [("apache-foo-2.11.0-bin.tar.gz", "convenience"), ("apache-foo-2.11.0.tar.gz", "source")]
    )
    assert render.parse_rc_comment(comment).sha512 == "ab" * 64


def _canned_warnings(out: dict[str, Any]) -> list[str]:
    return [w for w in out["warnings"] if "canned_body" in w]


def test_canned_verify_section_kept_but_warned_about() -> None:
    canned = "Vote on <version>.\n\nHow to verify this candidate before voting\n  SWHID: <swhid>\n"
    out = render.step2(draft(), canned_body=canned, record=CASE_1_RECORD, **urls("2.11.0-rc1"))
    assert out["verify_section_appended"] is False
    assert CASE_1_RECORD.swhid and CASE_1_RECORD.swhid in out["body"]
    assert out["canned_verify_missing"] == []
    (warning,) = _canned_warnings(out)
    assert "the generated one was not added" in warning and "reproducibility record" in warning


def test_canned_verify_section_missing_the_record_is_flagged() -> None:
    canned = "Vote on <version>.\n\nHow to verify this candidate before voting\n... project text ...\n"
    out = render.step2(draft(), canned_body=canned, record=CASE_1_RECORD, **urls("2.11.0-rc1"))
    assert len(out["canned_verify_missing"]) == 1
    assert str(CASE_1_RECORD.swhid) in out["canned_verify_missing"][0]
    bare = render.step2(draft(), canned_body=canned, **urls("2.11.0-rc1"))
    assert bare["canned_verify_missing"] == ["the reproducibility record: it has no SWHID line"]
    assert len(_canned_warnings(bare)) == 2


def test_canned_verify_section_checks_atr_and_trusted_hardware() -> None:
    atr = "https://release-test.apache.org/c/airflow/2.11.0"
    d = draft(vote_backend="atr", backend="svnpubsub", signing_mode="ci-automated")
    canned = "Vote.\n\nHow to verify this candidate before voting\nSWHID: see the issue\n"
    out = render.step2(d, canned_body=canned, svn_revision="1", atr_candidate_url=atr, **urls("2.11.0-rc1"))
    missing = out["canned_verify_missing"]
    assert len(missing) == 2
    assert atr in missing[0] and "vote_backend = atr" in missing[0]
    assert "--trusted-hardware" in missing[1] and "ci-automated" in missing[1]
    assert len(_canned_warnings(out)) == 3
    full = canned + "ATR: <atr_candidate_url>\nRebuild with --trusted-hardware --post-to <planning_issue>.\n"
    ok = render.step2(
        d,
        canned_body=full,
        svn_revision="1",
        atr_candidate_url=atr,
        planning_issue=PLANNING,
        **urls("2.11.0-rc1"),
    )
    assert ok["canned_verify_missing"] == []
    assert f"--post-to {PLANNING}" in ok["body"]
