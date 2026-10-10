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
"""pre-first-pr-check: the scripted categories over a real local branch, and the report.

Mirrors the retired model-graded cases: `step-2-check-categories` cases 1, 2,
4 and 5, and every `step-3-compose-report` case. Step-2 cases 3 (B1,
imperative mood) and 6 (E, prompt injection) are agent judgement and stay.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pr_management.pre_first_pr import checks, report

HEADER = "<!-- SPDX-License-Identifier: Apache-2.0\n     https://www.apache.org/licenses/LICENSE-2.0 -->\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.org")
    _git(r, "config", "user.name", "T")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text(HEADER + "\n# Base\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "Base")
    _git(r, "update-ref", "refs/remotes/origin/main", "HEAD")
    return r


def commit(repo: Path, files: dict[str, str | bytes], message: str) -> None:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def run(repo: Path) -> dict:
    return checks.run(repo, base=None, default_branch="main", path_glob=None)


def test_nothing_ahead_of_base(repo: Path) -> None:
    assert run(repo)["nothing_to_check"]


def test_case_1_all_pass(repo: Path) -> None:
    commit(
        repo,
        {"docs/setup/quick-start.md": HEADER + "\n# Quick-start\n"},
        "Add quick-start guide to setup docs\n\nGenerated-by: Claude Code (Sonnet 4.6)",
    )
    cats = run(repo)["categories"]
    assert {k: v["status"] for k, v in cats.items()} == {
        "spdx_headers": "pass",
        "commit_shape": "pass",
        "placeholder_convention": "pass",
        "contributing_conventions": "pass",
    }


def test_case_2_missing_spdx(repo: Path) -> None:
    commit(
        repo,
        {"tools/my-helper/helper.py": '"""Helper."""\n\n\ndef f():\n    return 1\n'},
        "Add helper utility for hashing\n\nGenerated-by: Claude Code (Sonnet 4.6)",
    )
    spdx = run(repo)["categories"]["spdx_headers"]
    assert spdx["status"] == "fail" and spdx["locations"] == ["tools/my-helper/helper.py"]


def test_case_4_agent_co_authored(repo: Path) -> None:
    commit(
        repo,
        {"README.md": HEADER + "\n# Base\n\n- more\n"},
        "Expand setup prerequisites list\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
    )
    shape = run(repo)["categories"]["commit_shape"]
    assert shape["status"] == "fail" and shape["violations"][0]["rule"] == "B2"


def test_a_human_co_author_is_fine(repo: Path) -> None:
    commit(
        repo,
        {"README.md": HEADER + "\n# Base\n\n- x\n"},
        "Add a line\n\nCo-Authored-By: Jane Doe <jane@example.org>",
    )
    assert run(repo)["categories"]["commit_shape"]["status"] == "pass"


def test_co_authored_by_convention_allows_the_agent_trailer(repo: Path) -> None:
    (repo / ".apache-magpie-overrides").mkdir()
    (repo / ".apache-magpie-overrides" / "commit-attribution.toml").write_text(
        'convention = "co-authored-by"\n'
    )
    commit(
        repo,
        {"README.md": HEADER + "\n# Base\n\n- y\n"},
        "Add a line\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
    )
    assert run(repo)["categories"]["commit_shape"]["status"] == "pass"


def test_case_5_unsubstituted_placeholder(repo: Path) -> None:
    commit(
        repo,
        {"skills/my-new-skill/SKILL.md": HEADER + "\nManages releases for <upstream>.\n"},
        "Add my-new-skill for release management\n\nGenerated-by: Claude Code (Sonnet 4.6)",
    )
    c = run(repo)["categories"]["placeholder_convention"]
    assert c["status"] == "fail" and c["occurrences"][0]["token"] == "<upstream>"


def test_template_files_are_exempt_from_placeholders(repo: Path) -> None:
    commit(
        repo, {"projects/_template/project.md": HEADER + "\n<upstream>\n"}, "Add template\n\nGenerated-by: x"
    )
    assert run(repo)["categories"]["placeholder_convention"]["status"] == "pass"


def test_binaries_env_files_and_tokens_fail_d(repo: Path) -> None:
    commit(
        repo,
        {
            ".env.production": "TOKEN=1\n",
            "blob.bin": b"\x00\x01\x02",
            "conf.md": HEADER + "\nghp_" + "a" * 36 + "\n",
        },
        "Add config\n\nGenerated-by: x",
    )
    d = run(repo)["categories"]["contributing_conventions"]
    assert d["status"] == "fail"
    assert {p["summary"] for p in d["problems"]} >= {
        "committed environment file",
        "committed binary file",
        "token-like string in added lines",
    }


def test_b1_and_b3_are_handed_to_the_agent(repo: Path) -> None:
    commit(repo, {"README.md": HEADER + "\n# Base\n\n- z\n"}, "Added the thing")
    j = run(repo)["categories"]["commit_shape"]["judgement"]
    assert j["B1"][0]["subject"] == "Added the thing"
    assert j["B3"]["convention"] == "generated-by" and len(j["B3"]["commits_without_trailer"]) == 1


SUMMARY = {"base": "origin/main", "commits": 1, "files": 1, "added": 1, "modified": 0, "deleted": 0}
PASS = {"status": "pass", "details": "", "locations": []}


def test_report_case_1_all_pass() -> None:
    cats = {k: dict(PASS) for k, _ in report.SECTIONS}
    text = report.render(SUMMARY, cats)
    assert report.readiness(cats) == {
        "signal": "ready",
        "blocking": 0,
        "advisory": 0,
        "sentence": "Ready to open — no blocking or advisory items.",
    }
    for _, title in report.SECTIONS:
        assert f"### {title}" in text
    assert "**Base:** origin/main" in text and "*Pre-first-PR checklist generated by" in text


def test_report_case_2_blocking_items_counts_a_category_that_did_not_run() -> None:
    cats = {k: dict(PASS) for k, _ in report.SECTIONS if k != "spdx_headers"}
    cats["commit_shape"] = {"status": "fail", "details": "past tense", "locations": ["bcd2345"]}
    r = report.readiness(cats)
    assert (r["signal"], r["blocking"], r["advisory"]) == ("blocking", 2, 0)
    assert "this check did not run" in report.render(SUMMARY, cats)


def test_report_case_3_advisory_only() -> None:
    cats = {k: dict(PASS) for k, _ in report.SECTIONS}
    cats["contributing_conventions"] = {"status": "advisory", "details": "Reminder.", "locations": []}
    r = report.readiness(cats)
    assert (r["signal"], r["blocking"], r["advisory"]) == ("advisory-only", 0, 1)


def test_merge_folds_the_agents_judgement() -> None:
    cats = {k: dict(PASS) for k, _ in report.SECTIONS if k != "injection_guard"}
    merged = report.merge(
        cats,
        {
            "B1": [{"location": "abc1234", "summary": "past tense"}],
            "E": {"status": "fail", "details": "directive in a comment", "location": "x.md"},
        },
    )
    assert merged["commit_shape"]["status"] == "fail" and merged["injection_guard"]["status"] == "fail"
    assert report.readiness(merged)["blocking"] == 2
