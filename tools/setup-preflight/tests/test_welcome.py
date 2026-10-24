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

"""When a first-run welcome guide is shown, which one, and what the answer records."""

from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

import pytest

from setup_preflight import sections, welcome
from setup_preflight.cli import main as preflight
from setup_preflight.core import configured_at_all, skill_findings, welcome_findings

from .conftest import personal, write_stamp

REPO_ROOT = Path(__file__).resolve().parents[3]
SECURITY_SKILL = "issue-sync"
# Every shipped family now has a guide, so the "family without a guide"
# cases use a synthetic one registered for the duration of each test.
OTHER_SKILL = "example-guideless-skill"
OTHER_FAMILY = "example-guideless-family"


@pytest.fixture
def guideless_family(monkeypatch: pytest.MonkeyPatch) -> None:
    from setup_preflight import families

    monkeypatch.setitem(families.SKILL_FAMILIES, OTHER_SKILL, OTHER_FAMILY)


def stamp(root: Path) -> dict:
    return json.loads((personal(root) / "reconciled.json").read_text(encoding="utf-8"))


def codes(root: Path, skill: str = SECURITY_SKILL) -> list[str]:
    return [f.code for f in welcome_findings(root, skill)]


@pytest.fixture
def version(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The framework version the checker sees; tests move it by assignment."""
    current = ["0.9.0"]
    monkeypatch.setattr(welcome, "framework_stamp", lambda root: current[0])
    return current


# --- which skills ---------------------------------------------------------------------


def due(root: Path, skill: str = SECURITY_SKILL) -> list[tuple[str, str]]:
    """`(guide, reason)` for each finding this run reports."""
    return [(str(f.facts["family"]), str(f.facts["reason"])) for f in welcome_findings(root, skill)]


def test_the_first_magpie_skill_gets_the_general_guide(project: Path, version) -> None:
    findings = welcome_findings(project, SECURITY_SKILL)
    assert [(f.scope, f.code, f.section) for f in findings] == [("family", "welcome", "welcome")]
    facts = findings[0].facts
    assert facts["family"] == "general"
    assert facts["reason"] == "first-run"
    assert facts["shown"] == 0
    assert facts["guide"] == welcome.guide("general")


def test_the_family_guide_comes_on_the_next_run_not_the_same_one(project: Path, version) -> None:
    assert due(project) == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project) == [("security", "first-run")]
    welcome.record(project, "security", "seen")
    assert due(project) == [("general", "again")]


def test_the_utilities_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    assert due(project, "list-skills") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "list-skills") == [("utilities", "first-run")]
    welcome.record(project, "utilities", "seen")
    assert due(project, "list-skills") == [("general", "again")]


def test_the_mentoring_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    for skill in (
        "welcome",
        "good-first-issue-sweep",
        "good-first-issue-author",
        "newcomer-issue-explainer",
    ):
        assert welcome.family_of(skill) == "mentoring"

    assert due(project, "welcome") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "welcome") == [("mentoring", "first-run")]
    welcome.record(project, "mentoring", "seen")
    assert due(project, "welcome") == [("general", "again")]


def test_the_pairing_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    assert welcome.family_of("self-review") == "pairing"
    assert welcome.family_of("multi-agent-review") == "pairing"
    assert due(project, "self-review") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "self-review") == [("pairing", "first-run")]
    welcome.record(project, "pairing", "seen")
    assert due(project, "self-review") == [("general", "again")]


def test_the_issue_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    for skill in (
        "backlog-stats",
        "deduplicate",
        "fix-workflow",
        "reassess",
        "reassess-stats",
        "reproducer",
        "stale-sweep",
    ):
        assert welcome.family_of(skill) == "issue"

    # The bare issue-triage name belongs to Security, not Issue.
    assert welcome.family_of("issue-triage") == "security"
    assert welcome.family_of("magpie-issue-triage") == "issue"

    assert due(project, "magpie-issue-triage") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "magpie-issue-triage") == [("issue", "first-run")]
    welcome.record(project, "issue", "seen")
    assert due(project, "magpie-issue-triage") == [("general", "again")]


def test_the_pr_management_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    assert due(project, "pr-triage") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "pr-triage") == [("pr-management", "first-run")]
    welcome.record(project, "pr-management", "seen")
    assert due(project, "pr-triage") == [("general", "again")]


def test_the_contributor_growth_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    for skill in (
        "activity-sweep",
        "calibrate",
        "candidate-screen",
        "committer-onboarding",
        "contributor-to-committer",
        "identity-map",
        "nomination",
        "onboarding-concierge",
        "sentiment",
    ):
        assert welcome.family_of(skill) == "contributor-growth"

    assert due(project, "activity-sweep") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "activity-sweep") == [("contributor-growth", "first-run")]
    welcome.record(project, "contributor-growth", "seen")
    assert due(project, "activity-sweep") == [("general", "again")]


def test_the_repo_health_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    for skill in (
        "audit-finding-fix",
        "ci-runner-audit",
        "dependency-audit",
        "dependency-license-audit",
        "flaky-test-triage",
        "license-compliance-audit",
        "workflow-security-audit",
    ):
        assert welcome.family_of(skill) == "repo-health"

    assert due(project, "ci-runner-audit") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "ci-runner-audit") == [("repo-health", "first-run")]
    welcome.record(project, "repo-health", "seen")
    assert due(project, "ci-runner-audit") == [("general", "again")]


def test_the_setup_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    for skill in (
        "isolated-setup-doctor",
        "isolated-setup-install",
        "isolated-setup-update",
        "isolated-setup-verify",
        "override-upstream",
        "privacy-llm",
        "setup",
        "shared-config-sync",
        "status",
        "upstream-fix",
        "welcome-guide",
    ):
        assert welcome.family_of(skill) == "setup"

    assert due(project, "status") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "status") == [("setup", "first-run")]
    welcome.record(project, "setup", "seen")
    assert due(project, "status") == [("general", "again")]


def test_the_release_management_family_guide_comes_on_the_next_run(project: Path, version) -> None:
    for skill in (
        "announce-draft",
        "archive-sweep",
        "audit-report",
        "keys-sync",
        "prepare",
        "promote",
        "rc-cut",
        "verify-rc",
        "vote-draft",
        "vote-tally",
    ):
        assert welcome.family_of(skill) == "release-management"

    assert due(project, "rc-cut") == [("general", "first-run")]
    welcome.record(project, "general", "seen")
    assert due(project, "rc-cut") == [("release-management", "first-run")]
    welcome.record(project, "release-management", "seen")
    assert due(project, "rc-cut") == [("general", "again")]


def test_at_most_one_guide_per_run(project: Path, version) -> None:
    for _ in range(8):
        found = welcome_findings(project, SECURITY_SKILL)
        assert len(found) <= 1
        if found:
            welcome.record(project, str(found[0].facts["family"]), "seen")
    assert due(project) == []
    assert stamp(project)["welcome"]["general"]["shown"] == 3
    assert stamp(project)["welcome"]["security"]["shown"] == 3


def test_a_family_first_showing_beats_a_general_repeat(project: Path, version) -> None:
    welcome.record(project, "general", "seen")
    welcome.record(project, "general", "seen")
    assert due(project) == [("security", "first-run")]


def test_a_hidden_general_guide_does_not_hold_back_the_family_one(project: Path, version) -> None:
    welcome.record(project, "general", "never")
    assert due(project) == [("security", "first-run")]


@pytest.mark.usefixtures("guideless_family")
def test_a_skill_of_a_family_without_a_guide_gets_only_the_general_one(project: Path, version) -> None:
    assert welcome.family_of(OTHER_SKILL) == OTHER_FAMILY
    assert OTHER_FAMILY not in welcome.family_guides()
    assert due(project, OTHER_SKILL) == [("general", "first-run")]
    welcome.record(project, "general", "never")
    assert due(project, OTHER_SKILL) == []


def test_an_unknown_skill_gets_nothing(project: Path, version) -> None:
    assert codes(project, "magpie-x") == []


def test_mirror_names_resolve_only_with_their_prefix() -> None:
    """`skills/issue-triage` is the issue family's `triage`; the security
    family's frontmatter name is `issue-triage`. The bare name is the
    frontmatter one, and the mirror is reached only as `magpie-<mirror>`."""
    assert welcome.family_of("issue-triage") == "security"
    assert welcome.family_of("magpie-issue-triage") == "issue"
    assert welcome.family_of("magpie-security-issue-triage") == "security"


def test_a_project_without_version_control_still_gets_the_guide(tmp_path: Path, version) -> None:
    """With no VCS the choice is recorded in the in-tree personal layer."""
    assert welcome_findings(tmp_path, SECURITY_SKILL) != []


def run(project: Path, *extra: str) -> None:
    listing = project / "plugins.json"
    listing.write_text("[]")
    preflight(
        ["--skill", SECURITY_SKILL, "--project-root", str(project), "--plugin-list", str(listing), *extra]
    )


def test_the_finding_rides_the_verdict_with_its_rules(project: Path, capsys, version) -> None:
    run(project)
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "action"
    assert payload["findings"][0]["section"] == "welcome"
    assert payload["rules"]["welcome"].startswith("## welcome")


@pytest.mark.parametrize("failure", ["guide", "framework_stamp"])
def test_an_unreadable_optional_guide_keeps_setup_findings(
    project: Path, capsys, monkeypatch, failure: str
) -> None:
    def unreadable(*args):
        raise PermissionError("the optional guide is unreadable")

    monkeypatch.setattr(welcome, failure, unreadable)
    run(project, "--requires", "project.md")
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "action"
    assert [f["code"] for f in payload["findings"]] == ["config-missing"]


def test_no_welcome_leaves_it_out(project: Path, capsys, version) -> None:
    run(project, "--no-welcome")
    assert json.loads(capsys.readouterr().out) == {"verdict": "ok"}


# --- the three answers ----------------------------------------------------------------


@pytest.mark.usefixtures("guideless_family")
def test_seen_shows_again_and_stops_after_three(project: Path, version) -> None:
    reasons = []
    for _ in range(5):
        found = welcome_findings(project, OTHER_SKILL)
        reasons.append(found[0].facts["reason"] if found else None)
        if found:
            welcome.record(project, "general", "seen")
    assert reasons == ["first-run", "again", "again", None, None]
    assert stamp(project)["welcome"]["general"]["shown"] == 3


def test_a_later_answer_replaces_seen_without_counting_twice(project: Path, version) -> None:
    welcome.record(project, "general", "seen")
    entry = welcome.record(project, "general", "dismiss")
    assert entry["choice"] == "dismiss"
    assert entry["shown"] == 1


@pytest.mark.usefixtures("guideless_family")
def test_dismiss_hides_it_until_the_version_changes(project: Path, version) -> None:
    welcome.record(project, "general", "dismiss")
    assert codes(project, OTHER_SKILL) == []
    version[0] = "0.10.0"
    found = welcome_findings(project, OTHER_SKILL)
    assert [f.facts["reason"] for f in found] == ["upgraded"]


@pytest.mark.usefixtures("guideless_family")
def test_never_persists_across_versions(project: Path, version) -> None:
    welcome.record(project, "general", "never")
    version[0] = "1.0.0"
    assert codes(project, OTHER_SKILL) == []


@pytest.mark.usefixtures("guideless_family")
def test_enable_clears_the_choice(project: Path, version) -> None:
    welcome.record(project, "general", "never")
    assert welcome.enable(project, "general") is True
    assert codes(project, OTHER_SKILL) == ["welcome"]
    assert "welcome" not in stamp(project)
    assert welcome.enable(project, "general") is False


def test_an_unknown_choice_is_refused(project: Path, version) -> None:
    with pytest.raises(ValueError):
        welcome.record(project, "general", "later")


# --- what recording writes ------------------------------------------------------------


def test_record_merges_into_the_stamp_without_touching_other_keys(project: Path, version) -> None:
    original: dict[str, object] = {
        "version": "0.8.0",
        "skills": {"issue-sync": "sha256:aaaa"},
        "acknowledged": {"sweep": "0.8.0"},
        "isolated_setup": {"enabled": False},
        "welcome": {"other": {"choice": "never"}},
    }
    write_stamp(project, original)
    entry = welcome.record(project, "security", "dismiss", today=date(2026, 10, 16))
    assert entry == {"choice": "dismiss", "version": "0.9.0", "at": "2026-10-16", "shown": 0}
    after = stamp(project)
    assert after["welcome"] == {"other": {"choice": "never"}, "security": entry}
    assert {k: v for k, v in after.items() if k != "welcome"} == {
        k: v for k, v in original.items() if k != "welcome"
    }


def test_enable_keeps_other_families_and_keys(project: Path, version) -> None:
    write_stamp(project, {"skills": {"a": "b"}, "welcome": {"security": {"choice": "never"}, "x": {}}})
    welcome.enable(project, "security")
    assert stamp(project) == {"skills": {"a": "b"}, "welcome": {"x": {}}}


def test_answering_the_guide_is_not_configuring_the_project(project: Path, version) -> None:
    """The record creates the personal layer; that must not read as a
    configured project and start proposing a reconciliation sweep."""
    welcome.record(project, "security", "seen")
    assert not configured_at_all(project)
    assert skill_findings(project, SECURITY_SKILL, "sha256:abc", []) == []


def test_a_layer_with_real_config_is_still_configured(project: Path, version) -> None:
    welcome.record(project, "security", "seen")
    (personal(project) / "project.md").write_text("# project\n", encoding="utf-8")
    assert configured_at_all(project)


def test_the_record_command_prints_the_entry(project: Path, capsys, version) -> None:
    code = welcome.main(
        ["record", "--family", "security", "--choice", "never", "--project-root", str(project)]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["welcome"]["security"]["choice"] == "never"


def test_recording_without_version_control_writes_the_in_tree_dir(tmp_path: Path, capsys, version) -> None:
    code = welcome.main(
        ["record", "--family", "security", "--choice", "seen", "--project-root", str(tmp_path)]
    )
    assert code == 0
    assert (tmp_path / ".apache-magpie-local").is_dir()


@pytest.mark.parametrize("family", ["../sections/welcome", "_footer", "/tmp/other-guide"])
def test_guide_names_cannot_select_other_markdown_files(family: str, capsys) -> None:
    assert welcome.guide(family) is None
    assert welcome.main(["show", "--family", family]) == 2
    assert capsys.readouterr().out == ""


def test_an_unknown_family_is_refused(capsys) -> None:
    assert welcome.main(["show", "--family", "nope"]) == 2


# --- the version a dismissal is tied to -----------------------------------------------


def manifest(base: Path, name: str, version: str) -> None:
    directory = base / "plugins" / "magpie-setup" / ".claude-plugin"
    directory.mkdir(parents=True)
    (directory / "plugin.json").write_text(json.dumps({"name": name, "version": version}))


@pytest.fixture
def copied_checker(project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The checker as copied into a personal layer: no manifest beside it."""
    here = project / ".git" / "apache-magpie" / "setup_preflight"
    here.mkdir(parents=True)
    (here / "core.py").write_text("# a copy\n")
    monkeypatch.setattr(welcome, "HERE", here)
    return here


def test_the_stamp_is_the_setup_plugin_version_in_a_framework_tree(project: Path, copied_checker) -> None:
    manifest(project, "magpie-setup", "1.2.3")
    assert welcome.framework_stamp(project) == "1.2.3"


def test_a_pinned_snapshot_supplies_the_version(project: Path, copied_checker) -> None:
    manifest(project / ".apache-magpie", "magpie-setup", "1.2.4")
    assert welcome.framework_stamp(project) == "1.2.4"


def test_a_manifest_of_another_plugin_is_not_the_version(project: Path, copied_checker) -> None:
    manifest(project, "magpie-other", "9.9.9")
    assert welcome.framework_stamp(project).startswith("checker:")


def test_running_from_the_plugin_reads_its_own_manifest(project: Path) -> None:
    beside = welcome._plugin_version(welcome.HERE.parents[2] / ".claude-plugin" / "plugin.json")
    if beside is None:
        pytest.skip("not running from a magpie-setup plugin tree")
    assert welcome.framework_stamp(project) == beside


def test_without_a_manifest_the_stamp_is_the_checker_fingerprint(project: Path, copied_checker) -> None:
    before = welcome.framework_stamp(project)
    assert before.startswith("checker:")
    (copied_checker / "core.py").write_text("# an upgraded copy\n")
    assert welcome.framework_stamp(project) != before


# --- showing it -----------------------------------------------------------------------


class Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_colour_needs_a_tty_unless_forced() -> None:
    assert welcome.use_color("auto", Tty(), env={}) is True
    assert welcome.use_color("auto", io.StringIO(), env={}) is False
    assert welcome.use_color("always", io.StringIO(), env={}) is True
    assert welcome.use_color("never", Tty(), env={}) is False


def test_no_color_wins_over_everything() -> None:
    assert welcome.use_color("always", Tty(), env={"NO_COLOR": "1"}) is False
    assert welcome.use_color("auto", Tty(), env={"NO_COLOR": "1"}) is False
    assert welcome.use_color("auto", Tty(), env={"NO_COLOR": ""}) is True


def test_show_color_off_a_tty_prints_no_escapes(capsys, monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert welcome.main(["show", "--family", "security", "--color"]) == 0
    out = capsys.readouterr().out
    assert "\033[" not in out
    assert "Magpie here" in out
    assert "**" not in out
    assert '*"' not in out, "italic markers survive the terminal rendering"
    assert "`" not in out


def test_show_color_always_paints_unless_no_color(capsys, monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    welcome.main(["show", "--family", "security", "--color=always"])
    assert "\033[" in capsys.readouterr().out
    monkeypatch.setenv("NO_COLOR", "1")
    welcome.main(["show", "--family", "security", "--color=always"])
    assert "\033[" not in capsys.readouterr().out


def test_show_without_color_prints_the_markdown(capsys) -> None:
    welcome.main(["show", "--family", "security"])
    assert capsys.readouterr().out == welcome.guide("security")


# --- what ships -----------------------------------------------------------------------


def test_the_rules_section_and_all_guides_ship() -> None:
    assert welcome.SECTION in sections.available()
    assert {
        "general",
        "security",
        "utilities",
        "mentoring",
        "pairing",
        "issue",
        "pr-management",
        "contributor-growth",
        "repo-health",
        "setup",
        "release-management",
    } <= set(welcome.guides())
    assert welcome.family_guides() == [g for g in welcome.guides() if g != "general"]


@pytest.mark.parametrize(
    "name",
    [
        "general",
        "security",
        "utilities",
        "mentoring",
        "pairing",
        "issue",
        "pr-management",
        "contributor-growth",
        "repo-health",
        "setup",
        "release-management",
    ],
)
def test_each_guide_is_short_and_ends_with_the_way_back(name: str) -> None:
    text = welcome.guide(name) or ""
    assert not text.startswith("<!--")
    assert len(text.splitlines()) <= 70
    assert "/magpie-setup:welcome-guide" in text
    assert "/magpie-setup-welcome-guide" in text


def test_the_general_guide_lists_the_family_guides_that_ship() -> None:
    text = welcome.guide("general") or ""
    assert "family guides: generated" not in text
    for name in welcome.family_guides():
        assert f"/magpie-setup:welcome-guide {name}" in text


def test_the_footer_is_shared_and_filled_in_per_guide() -> None:
    assert "_footer" not in welcome.guides()
    assert welcome.guide("_footer") is None
    security = welcome.guide("security") or ""
    general = welcome.guide("general") or ""
    utilities = welcome.guide("utilities") or ""
    mentoring = welcome.guide("mentoring") or ""
    pairing = welcome.guide("pairing") or ""
    issue = welcome.guide("issue") or ""
    pr_management = welcome.guide("pr-management") or ""
    contributor_growth = welcome.guide("contributor-growth") or ""
    repo_health = welcome.guide("repo-health") or ""
    setup = welcome.guide("setup") or ""
    release_management = welcome.guide("release-management") or ""
    for text in (
        security,
        general,
        utilities,
        mentoring,
        pairing,
        issue,
        pr_management,
        contributor_growth,
        repo_health,
        setup,
        release_management,
    ):
        assert "{{" not in text
        assert "welcome footer: generated" not in text
    assert "`/magpie-setup:welcome-guide security`" in security
    assert "--family security --color=always" in security
    assert "`/magpie-setup:welcome-guide [<family>]`" in general
    assert "--family general --color=always" in general
    assert "`/magpie-setup:welcome-guide utilities`" in utilities
    assert "--family utilities --color=always" in utilities
    assert "`/magpie-setup:welcome-guide mentoring`" in mentoring
    assert "--family mentoring --color=always" in mentoring
    assert "`/magpie-setup:welcome-guide pairing`" in pairing
    assert "--family pairing --color=always" in pairing
    assert "`/magpie-setup:welcome-guide issue`" in issue
    assert "--family issue --color=always" in issue
    assert "`/magpie-setup:welcome-guide pr-management`" in pr_management
    assert "--family pr-management --color=always" in pr_management
    assert "`/magpie-setup:welcome-guide contributor-growth`" in contributor_growth
    assert "--family contributor-growth --color=always" in contributor_growth
    assert "`/magpie-setup:welcome-guide repo-health`" in repo_health
    assert "--family repo-health --color=always" in repo_health
    assert "`/magpie-setup:welcome-guide setup`" in setup
    assert "--family setup --color=always" in setup
    assert "`/magpie-setup:welcome-guide release-management`" in release_management
    assert "--family release-management --color=always" in release_management


def test_list_prints_every_guide(capsys) -> None:
    assert welcome.main(["list"]) == 0
    assert capsys.readouterr().out.split() == welcome.guides()


def _plugin_skill(base: Path, name: str, family: str) -> Path:
    skill = base / "plugins" / f"magpie-{family}" / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\nfamily: {family}\n---\n", encoding="utf-8")
    return skill


def test_a_mirror_entry_checked_out_as_a_text_file_still_resolves(tmp_path: Path) -> None:
    """Without symlink support git writes a link as a file holding its target path."""
    _plugin_skill(tmp_path, "list-skills", "utilities")
    mirror = tmp_path / "skills"
    mirror.mkdir()
    (mirror / "list-skills").write_text("../plugins/magpie-utilities/skills/list-skills\n", encoding="utf-8")
    (mirror / "stray").write_text("../plugins/magpie-utilities/skills/missing\n", encoding="utf-8")

    assert welcome.scan_families(tmp_path) == {"list-skills": "utilities", "magpie-list-skills": "utilities"}


@pytest.mark.skipif(not (REPO_ROOT / "plugins").is_dir(), reason="needs the framework tree")
def test_the_shipped_family_map_matches_the_framework_tree() -> None:
    """The prek hook keeps this in sync; a failure means it was bypassed."""
    from setup_preflight.families import SKILL_FAMILIES

    assert welcome.scan_families(REPO_ROOT) == SKILL_FAMILIES
