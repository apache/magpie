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
"""`security-management issue-fix` end to end through the CLI.

The cases of the retired model-graded `security-issue-fix` suites
`step-0-fix-flow`, `step-5a-branch-name`, `step-5c-title-check`,
`step-5e-backport`, `step-5f-newsfragment`, `step-6-confirm` and
`step-11-recap` live here, named after each former case. The deterministic
parts of `step-7-adversarial-review`, `step-8-svn-share-patch` and
`step-9-svn-publication-gate` are pinned too; those suites stay model evals
for what needs judgement (findings as data, injection flagging).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

TRACKER = "airflow-s/airflow-s"


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["issue-fix", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out)


def ok(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> dict[str, Any]:
    code, out = run(capsys, tmp_path, command, data)
    assert code == 0, out
    return out


# --- Source control: the flow ------------------------------------------------


@pytest.mark.parametrize(
    ("case", "data", "expected"),
    [
        (
            "case-1-distributed-project",
            {"exit": 0, "result": {"flow": "pull-request"}},
            ("pull-request", False, True),
        ),
        (
            "case-2-subversion-project",
            {"exit": 0, "result": {"flow": "patch-then-commit"}},
            ("patch-then-commit", True, False),
        ),
        (
            "case-3-manifest-contradicts-working-copy",
            {"exit": 2, "error": "the manifest declares 'asf-svn' (svn) but the working copy is git"},
            ("stop", False, False),
        ),
    ],
)
def test_step_0_fix_flow_cases(capsys, tmp_path, case, data, expected):
    out = ok(capsys, tmp_path, "flow", data)
    assert (out["flow"], out["follow_subversion_flow"], out["open_pr"]) == expected


# --- 5a / 5c / 5f: the forbidden-term check ----------------------------------


@pytest.mark.parametrize(
    ("case", "branch", "valid", "term"),
    [
        ("case-1-good-slug", "fix-xcom-deserialize-type-check", True, None),
        ("case-2-cve-id-in-name", "cve-2025-44812-xcom-fix", False, "CVE id"),
        ("case-3-security-fix-in-name", "security-fix-pickle-deserialization", False, "security fix"),
    ],
)
def test_step_5a_branch_name_cases(capsys, tmp_path, case, branch, valid, term):
    out = ok(capsys, tmp_path, "scrub", {"branch": branch})
    assert out["branch"]["valid"] is valid
    if term:
        assert term in out["branch"]["terms"]


def test_a_standalone_security_word_in_a_branch(capsys, tmp_path):
    out = ok(capsys, tmp_path, "scrub", {"branch": "harden-security-of-xcom"})
    assert out["branch"]["terms"] == ["security"]


@pytest.mark.parametrize(
    ("case", "branch", "title", "valid", "found"),
    [
        (
            "case-1-neutral-title",
            "fix-extra-links-xcom-deserialization-owner-check",
            "Improve xcom value handling in extra links API",
            (True, True),
            [],
        ),
        (
            "case-2-cve-in-title",
            "cve-2025-44812-xcom-pickle-fix",
            "Fix CVE-2025-44812: prevent pickle deserialization in XCom",
            (False, False),
            ["CVE-2025-44812", "cve"],
        ),
        (
            "case-3-security-fix-in-title",
            "fix-connection-test-ssrf",
            "Security fix: prevent SSRF in connection test endpoint",
            (False, False),
            ["SSRF", "Security fix", "ssrf"],
        ),
    ],
)
def test_step_5c_title_check_cases(capsys, tmp_path, case, branch, title, valid, found):
    out = ok(capsys, tmp_path, "scrub", {"branch": branch, "title": title})
    assert (out["branch"]["valid"], out["title"]["valid"]) == valid
    assert set(found) <= set(out["forbidden_terms_found"]) | {f.lower() for f in out["forbidden_terms_found"]}
    assert out["clean"] is all(valid)


def test_tracker_identifiers_and_neutral_wording_pass(capsys, tmp_path):
    out = ok(
        capsys, tmp_path, "scrub",
        {"body": f"Restrict the connection test to the configured hosts.\n\nTracking: https://github.com/{TRACKER}/issues/312, #312"},
    )  # fmt: skip
    assert out["clean"] is True


def test_reporter_names_and_private_text_are_caught(capsys, tmp_path):
    private = "the scheduler deserializes the crafted payload before any permission check is applied"
    out = ok(
        capsys, tmp_path, "scrub",
        {"commit_message": f"Thanks Alice Nguyen: {private}", "reporter_names": ["Alice Nguyen"], "private_texts": [private]},
    )  # fmt: skip
    assert out["commit_message"]["valid"] is False
    assert "Alice Nguyen" in out["commit_message"]["terms"]


@pytest.mark.parametrize(
    ("case", "text", "violation"),
    [
        ("case-1-default-no-fragment", "Login redirects now only accept configured hosts.", False),
        (
            "case-2-forbidden-security-framing",
            "Fixed security vulnerability in login redirect that allowed open redirect attacks.",
            True,
        ),
    ],
)
def test_step_5f_newsfragment_cases(capsys, tmp_path, case, text, violation):
    out = ok(capsys, tmp_path, "scrub", {"newsfragment": text})
    assert (out["include_newsfragment"], out["security_framing_violation"]) == (False, violation)


# --- 5e: backport ------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "data", "needed", "labels"),
    [
        (
            "case-1-patch-release-needs-backport",
            {"milestone": "Airflow 3.2.2"},
            True,
            ["backport-to-v3-2-test"],
        ),
        ("case-2-main-no-backport", {"milestone": "Airflow 3.3.0"}, False, []),
        (
            "case-3-multiple-backports",
            {"milestone": "Airflow 3.2.2", "extra_lines": ["3.1"]},
            True,
            ["backport-to-v3-2-test", "backport-to-v3-1-test"],
        ),
    ],
)
def test_step_5e_backport_cases(capsys, tmp_path, case, data, needed, labels):
    out = ok(capsys, tmp_path, "backport", {"main_version": "3.3.0", **data})
    assert (out["backport_needed"], out["backport_labels"]) == (needed, labels)


def test_backport_needs_versions(capsys, tmp_path):
    assert run(capsys, tmp_path, "backport", {"milestone": "Providers 2026-04-21"})[0] == 2


# --- Step 6: confirm ---------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "reply", "expected"),
    [
        ("case-1-apply-all", "all", ("apply", [1, 2, 3, 4, 5, 6, 7], [])),
        (
            "case-2-free-form-edit",
            "The branch name is fine but can you also add tests/utils/test_helpers.py to the file list?",
            ("edit", [], []),
        ),
        ("case-3-cancel", "cancel", ("cancel", [], [])),
    ],
)
def test_step_6_confirm_cases(capsys, tmp_path, case, reply, expected):
    out = ok(capsys, tmp_path, "parse-reply", {"reply": reply})
    assert (out["action"], out["items_applied"], out["items_skipped"]) == expected
    if out["action"] == "edit":
        assert "test_helpers.py" in out["edit"]


# --- Step 7: when the adversarial reviewers run ------------------------------

REVIEW = {
    "config_found": True,
    "reviewers": ["codex"],
    "plugin_installed": True,
    "title": "Deny unlisted classes in the widget deserializer by default",
    "body_file": "/tmp/pr-body-613.md",
    "project_root": "/repo",
    "repo_dir": "/work/upstream",
    "base": "origin/main",
}


@pytest.mark.parametrize(
    ("case", "data", "run_", "notice"),
    [
        ("case-1-security-runs-under-mode-off", {**REVIEW, "mode": "off"}, True, None),
        ("case-2-no-config", {**REVIEW, "config_found": False}, False, "silent"),
        ("case-3-plugin-missing", {**REVIEW, "plugin_installed": False}, False, "one-line"),
    ],
)
def test_step_7_review_plan_cases(capsys, tmp_path, case, data, run_, notice):
    out = ok(capsys, tmp_path, "review-plan", data)
    assert (out["run"], out["skip_notice"]) == (run_, notice)
    if run_:
        assert out["title_passed"] == REVIEW["title"] and out["body_file_passed"] == REVIEW["body_file"]
        assert out["command"].startswith(
            "uvx --from ~/.claude/magpie/adversarial-review adversarial-review run "
        )


# --- Steps 8 and 9 (Subversion) ----------------------------------------------


@pytest.mark.parametrize(
    ("platform", "first", "via"),
    [
        ("local-files", "tracker-attach", "local-tracker"),
        ("jira", "tracker-attach", "jira-tracker"),
        ("github", "tracker-comment", "issue-comment"),
    ],
)
def test_step_8_share_stays_private(capsys, tmp_path, platform, first, via):
    out = ok(capsys, tmp_path, "svn-share", {"platform": platform})
    assert out["proposals"] == [first, "security-list-draft", "rollup-entry"]
    assert (out["attach_via"], out["public_surface_used"], out["commit_now"], out["next"]) == (
        via,
        False,
        False,
        "stop-await-review",
    )


READY = {
    "ready": True,
    "would_commit": ["src/widget.c"],
    "commands": [["magpie-vcs", "-C", "/wc", "commit", "--scrub", "--message-file", "/s/msg.txt"]],
}


@pytest.mark.parametrize(
    ("case", "data", "action", "shown"),
    [
        ("case-1-not-cleared", {"cleared": False}, "stop", False),
        ("case-2-cleared-and-ready", {"cleared": True, "proposal": READY}, "await-confirmation", True),
        (
            "case-3-scrub-hit-in-message",
            {"cleared": True, "proposal": {"ready": False, "blocked_by": ["scrub hits"]}},
            "revise",
            False,
        ),
        ("case-4-clearance-only-in-mail", {}, "ask", False),
        (
            "case-5-unrelated-change-would-ride-along",
            {"cleared": True, "proposal": {"ready": False, "unexpected_paths": ["docs/manual/index.xml"]}},
            "revise",
            False,
        ),
    ],
)
def test_step_9_publication_gate_cases(capsys, tmp_path, case, data, action, shown):
    out = ok(capsys, tmp_path, "svn-gate", data)
    assert (out["action"], out["show_commit_commands"], out["run_without_confirmation"]) == (
        action,
        shown,
        False,
    )
    if shown:
        assert out["publishing_commands_have_scrub"] is True
        assert out["commands"][0].startswith(
            "uv run --project <framework>/tools/vcs magpie-vcs -C /wc commit --scrub"
        )


def test_a_commit_without_scrub_is_never_shown(capsys, tmp_path):
    bad = {"ready": True, "commands": [["magpie-vcs", "-C", "/wc", "commit", "--message-file", "/s/m"]]}
    assert run(capsys, tmp_path, "svn-gate", {"cleared": True, "proposal": bad})[0] == 2


# --- Step 11: recap ----------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "labels"),
    [("case-1-pr-open-with-backport", ["backport-to-v3-2-test"]), ("case-2-pr-merged-no-backport", [])],
)
def test_step_11_recap_cases(capsys, tmp_path, case, labels):
    out = ok(
        capsys, tmp_path, "render-recap",
        {"tracker": TRACKER, "issue": 312, "pr_url": "https://github.com/apache/airflow/pull/52199",
         "branch": "fix-xcom-deserialize-type-check", "files": ["airflow/models/xcom.py", "tests/models/test_xcom.py"],
         "tests": [{"command": "pytest tests/models/test_xcom.py", "result": "PASSED (3 tests)"}],
         "tracker_comment_url": f"https://github.com/{TRACKER}/issues/312#issuecomment-9055", "backport_labels": labels},
    )  # fmt: skip
    text = out["text"]
    assert "https://github.com/apache/airflow/pull/52199" in text
    assert "`fix-xcom-deserialize-type-check`" in text and "`airflow/models/xcom.py`" in text
    assert "PASSED (3 tests)" in text and "#issuecomment-9055" in text
    assert ("backport-to-v3-2-test" in text) if labels else ("none needed" in text)
    assert "**Next:** wait for review" in text
    assert out["bare_refs"] == []
