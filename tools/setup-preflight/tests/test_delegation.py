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

"""Delegation to project skills: what the resolver accepts, refuses, and prefers."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from setup_preflight import delegation, sections
from setup_preflight.cli import main as preflight_main
from setup_preflight.delegation import Step, declared, findings, render, resolve

from .conftest import personal

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]


def project_skill(root: Path, name: str, where: str = ".claude/skills") -> Path:
    skill = root / where / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {name}\ndescription: the project's own\n---\n\n## Do it\n", encoding="utf-8"
    )
    return skill


def override(layer: Path, skill: str, frontmatter: str, body: str = "### Override 1 — x\n") -> Path:
    layer.mkdir(parents=True, exist_ok=True)
    path = layer / f"{skill}.md"
    path.write_text("---\n" + textwrap.dedent(frontmatter).strip("\n") + "\n---\n\n" + body, encoding="utf-8")
    return path


def committed(root: Path) -> Path:
    return root / ".apache-magpie-overrides"


# --- no override ------------------------------------------------------------------


def test_no_override_file_means_the_framework_default(project: Path) -> None:
    assert resolve(project, "security-issue-triage").status == "default"
    assert findings(project, "issue-triage") == []


def test_an_override_without_a_delegate_key_is_not_a_delegation(project: Path) -> None:
    (committed(project)).mkdir()
    (committed(project) / "security-issue-triage.md").write_text("### Override 1 — tone\n", encoding="utf-8")
    assert resolve(project, "security-issue-triage").status == "default"


# --- the four modes ---------------------------------------------------------------


def test_replace_resolves_to_the_project_skill(project: Path) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project), "security-issue-triage", "delegate:\n  skill: triage-reports\n  mode: replace"
    )
    r = resolve(project, "security-issue-triage")
    assert r.status == "delegated"
    assert (r.delegate, r.mode, r.layer) == ("triage-reports", "replace", "committed")
    assert r.path == ".claude/skills/triage-reports/SKILL.md"


@pytest.mark.parametrize("mode", ["before", "after"])
def test_before_and_after_need_no_steps(project: Path, mode: str) -> None:
    project_skill(project, "notify-team", ".agents/skills")
    override(committed(project), "security-issue-fix", f"delegate: {{ skill: notify-team, mode: {mode} }}")
    r = resolve(project, "security-issue-fix")
    assert (r.status, r.mode, r.path) == ("delegated", mode, ".agents/skills/notify-team/SKILL.md")


def test_merge_keeps_the_confirmed_step_order(project: Path) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project),
        "security-issue-triage",
        """
        delegate:
          skill: triage-reports
          mode: merge
          steps:
            - magpie: Step 1 — Gather   # the tracker state
            - project: Reproduce locally
            - magpie: "Step 2 — Classify"
            - skip: Step 3 — Label
          why: our reproduction lab
        """,
    )
    r = resolve(project, "security-issue-triage")
    assert r.status == "delegated", r.reason
    assert [s.to_dict() for s in r.steps] == [
        {"kind": "magpie", "ref": "Step 1 — Gather"},
        {"kind": "project", "ref": "Reproduce locally"},
        {"kind": "magpie", "ref": "Step 2 — Classify"},
        {"kind": "skip", "ref": "Step 3 — Label"},
    ]
    assert r.why == "our reproduction lab"


# --- precedence -------------------------------------------------------------------


def test_the_personal_layer_wins_over_the_committed_one(project: Path) -> None:
    project_skill(project, "triage-reports")
    project_skill(project, "my-triage")
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    override(personal(project), "security-issue-triage", "delegate: { skill: my-triage, mode: after }")
    r = resolve(project, "security-issue-triage")
    assert (r.delegate, r.mode, r.layer) == ("my-triage", "after", "personal")


def test_a_personal_off_opts_out_of_a_committed_delegation(project: Path) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    override(personal(project), "security-issue-triage", "delegate: off")
    assert resolve(project, "security-issue-triage").status == "opted-out"


def test_a_personal_override_without_delegate_falls_through_to_committed(project: Path) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    personal(project).mkdir(parents=True)
    (personal(project) / "security-issue-triage.md").write_text("### Override 1 — tone\n", encoding="utf-8")
    assert resolve(project, "security-issue-triage").layer == "committed"


# --- refusals ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("block", "reason"),
    [
        ("delegate:\n  skill: triage-reports\n  mode replace", "malformed"),
        ("delegate: yes-please", "malformed"),
        ("delegate:\n  skill: triage-reports\n  mode: rewrite", "mode"),
        ("delegate:\n  skill: triage-reports\n  mode: replace\n  baseline: off", "unknown key"),
        ("delegate:\n  skill: triage-reports\n  mode: replace\n  mode: merge", "duplicate"),
        ("delegate:\n  skill: triage-reports\n  mode: merge", "needs the confirmed"),
        ("delegate:\n  skill: triage-reports\n  mode: replace\n  steps:\n    - project: x", "merge only"),
        ("delegate:\n  skill: triage-reports\n  mode: merge\n  steps:\n    - project: x", "interleaves"),
        ("delegate:\n  skill: magpie-security-issue-triage\n  mode: replace", "Magpie skill"),
        ("delegate:\n  skill: issue-triage\n  mode: replace", "Magpie skill"),
        ("delegate:\n  skill: absent-skill\n  mode: replace", "not found"),
        (
            "delegate:\n  skill: triage-reports\n  path: ../elsewhere/SKILL.md\n  mode: replace",
            "without `..`",
        ),
        ("delegate:\n  skill: triage-reports\n  mode: '{ nested }'\n", "mode"),
        ("delegate:\n  skill: triage-reports\n  mode: replace\n  why: [a, b]", "malformed"),
    ],
)
def test_a_malformed_or_invalid_block_is_refused_whole(project: Path, block: str, reason: str) -> None:
    project_skill(project, "triage-reports")
    override(committed(project), "security-issue-triage", block)
    r = resolve(project, "security-issue-triage")
    assert r.status == "refused"
    assert reason in (r.reason or "")
    assert r.delegate is None and r.steps == ()


@pytest.mark.parametrize(
    "removed",
    [
        "Step 0 — Pre-flight",
        "Golden rule 2",
        "Step 3 — Confirm with the user",
        "Step 6 — Scrub the PR body",
        "Privacy-LLM gate",
    ],
)
def test_a_merge_that_would_skip_a_baseline_step_is_refused(project: Path, removed: str) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project),
        "security-issue-triage",
        f"""
        delegate:
          skill: triage-reports
          mode: merge
          steps:
            - magpie: Step 1 — Gather
            - project: Reproduce locally
            - skip: {removed}
        """,
    )
    r = resolve(project, "security-issue-triage")
    assert r.status == "refused"
    assert "baseline step" in (r.reason or "")


def test_a_malformed_personal_block_is_refused_not_skipped(project: Path) -> None:
    """Falling through to the committed delegate would apply something the
    person deliberately changed; refusing runs the framework default."""
    project_skill(project, "triage-reports")
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    override(personal(project), "security-issue-triage", "delegate:\n  skill triage-reports")
    r = resolve(project, "security-issue-triage")
    assert (r.status, r.layer) == ("refused", "personal")


def test_setup_family_skills_cannot_be_delegated(project: Path) -> None:
    project_skill(project, "our-setup")
    override(committed(project), "setup-override-upstream", "delegate: { skill: our-setup, mode: replace }")
    r = resolve(project, "setup-override-upstream")
    assert r.status == "refused" and "setup-family" in (r.reason or "")


def test_a_project_skill_linking_outside_the_repository_is_not_the_projects(
    project: Path, tmp_path_factory
) -> None:
    outside = tmp_path_factory.mktemp("elsewhere") / "triage-reports"
    outside.mkdir()
    (outside / "SKILL.md").write_text("---\nname: triage-reports\n---\n", encoding="utf-8")
    (project / ".claude" / "skills").mkdir(parents=True)
    (project / ".claude" / "skills" / "triage-reports").symlink_to(outside)
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    r = resolve(project, "security-issue-triage")
    assert r.status == "refused" and "outside the repository" in (r.reason or "")


# --- the pre-flight findings ------------------------------------------------------


def test_the_delegated_skill_gets_a_delegated_finding(project: Path) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    # The pre-flight passes the frontmatter name, `issue-triage`, for this skill.
    found = findings(project, "issue-triage")
    assert [(f.code, f.section) for f in found] == [("delegated", "step-13")]
    assert found[0].facts["delegate"] == "triage-reports"


def test_other_skills_learn_the_delegates_they_may_hand_off_to(project: Path) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    found = findings(project, "issue-sync")
    assert [f.code for f in found] == ["handoff-delegates"]
    delegates = found[0].facts["delegates"]
    assert isinstance(delegates, dict)
    assert delegates["security-issue-triage"]["delegate"] == "triage-reports"


def test_a_refused_delegate_is_reported_to_its_own_skill_only(project: Path) -> None:
    override(committed(project), "security-issue-triage", "delegate: { skill: absent, mode: replace }")
    assert [f.code for f in findings(project, "issue-triage")] == ["delegate-refused"]
    assert findings(project, "issue-sync") == []


def test_the_preflight_verdict_carries_the_delegation_rules(project: Path, capsys) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    assert preflight_main(["--skill", "issue-triage", "--project-root", str(project), "--no-cache"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "action"
    assert "delegated" in [f["code"] for f in payload["findings"]]
    assert "step-13" in payload["rules"]


def test_declared_lists_only_skills_with_a_delegate_key(project: Path) -> None:
    project_skill(project, "triage-reports")
    override(
        committed(project), "security-issue-triage", "delegate: { skill: triage-reports, mode: replace }"
    )
    (committed(project) / "project.md").write_text("# config\n", encoding="utf-8")
    assert [r.skill for r in declared(project)] == ["security-issue-triage"]


def test_the_delegation_section_ships() -> None:
    assert delegation.SECTION in sections.available()
    assert sections.load(delegation.SECTION).startswith("## step-13")


# --- rendering and the name table -------------------------------------------------


def test_a_rendered_block_resolves_to_what_was_confirmed(project: Path) -> None:
    project_skill(project, "triage-reports")
    steps = [Step("magpie", "Step 1 — Gather"), Step("project", "Reproduce: locally"), Step("skip", "Step 3")]
    block = render("triage-reports", "merge", ".claude/skills/triage-reports/SKILL.md", steps, "lab #1")
    committed(project).mkdir()
    (committed(project) / "security-issue-triage.md").write_text(block + "\n# Overrides\n", encoding="utf-8")
    r = resolve(project, "security-issue-triage")
    assert r.status == "delegated", r.reason
    assert list(r.steps) == steps and r.why == "lab #1"


def test_render_refuses_what_resolve_would_refuse(project: Path, capsys) -> None:
    code = delegation.main(
        [
            "render",
            "--skill",
            "security-issue-triage",
            "--delegate",
            "absent",
            "--mode",
            "replace",
            "--project-root",
            str(project),
        ]
    )
    assert code == 1
    assert "not found" in capsys.readouterr().err


def test_the_name_table_matches_the_framework_tree() -> None:
    if not (FRAMEWORK_ROOT / "skills").is_dir():
        pytest.skip("not running inside the framework checkout")
    shipped = delegation.NAMES_PATH.read_text(encoding="utf-8")
    assert shipped == delegation.names_source(FRAMEWORK_ROOT), (
        "skill_names.py is stale: run `python3 -m setup_preflight.delegation write-names`"
    )


def test_frontmatter_names_map_to_override_names() -> None:
    assert delegation.override_name("pr-triage") == "pr-management-triage"
    assert delegation.override_name("issue-triage") == "security-issue-triage"
    assert delegation.override_name("security-issue-triage") == "security-issue-triage"
