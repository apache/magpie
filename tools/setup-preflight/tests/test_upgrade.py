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

"""The `upgrade-pending` finding: every skill asks until `setup-upgrade` ran."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from setup_preflight import isolated, sections, upgrade
from setup_preflight.cli import main

from .conftest import personal, write_lock, write_stamp


def _marker(home: Path, version: str) -> None:
    path = home / ".claude" / "plugins" / "data" / "magpie-setup-apache-magpie" / "magpie-plugin-version"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(version, encoding="utf-8")


def _codes(project: Path, installed: dict[str, str] | None = None, harness: str | None = None) -> list[str]:
    return [f.code for f in upgrade.findings(project, installed, harness)]


def test_a_version_newer_than_the_stamp_asks(project: Path, isolated_home: Path) -> None:
    write_stamp(project, {"version": "0.8.0"})
    _marker(isolated_home, "0.9.0")
    [finding] = upgrade.findings(project, None, None)
    assert finding.code == "upgrade-pending"
    assert finding.facts == {"from": "0.8.0", "to": "0.9.0", "downgrade": False}
    assert finding.section == "step-15"


def test_the_same_version_says_nothing(project: Path, isolated_home: Path) -> None:
    write_stamp(project, {"version": "0.9.0"})
    _marker(isolated_home, "0.9.0")
    assert _codes(project) == []


def test_a_recorded_upgrade_wins_over_the_config_version(project: Path, isolated_home: Path) -> None:
    write_stamp(project, {"version": "0.8.0", "upgraded": {"version": "0.9.0", "at": "2026-11-09"}})
    _marker(isolated_home, "0.9.0")
    assert _codes(project) == []


def test_a_dev_build_counts_as_a_change(project: Path, isolated_home: Path) -> None:
    write_stamp(project, {"upgraded": {"version": "0.9.0.dev202611010039"}})
    _marker(isolated_home, "0.9.0.dev202611090749")
    assert _codes(project) == ["upgrade-pending"]


def test_a_downgrade_is_reported_as_one(project: Path, isolated_home: Path) -> None:
    write_stamp(project, {"version": "0.9.0"})
    _marker(isolated_home, "0.8.0")
    [finding] = upgrade.findings(project, None, None)
    assert finding.facts["downgrade"] is True


def test_the_plugin_listing_wins_over_the_marker(project: Path, isolated_home: Path) -> None:
    write_stamp(project, {"version": "0.9.0"})
    _marker(isolated_home, "0.8.0")
    assert _codes(project, {"magpie-setup": "0.9.0"}) == []
    assert _codes(project, {"magpie-setup": "0.10.0"}) == ["upgrade-pending"]


def test_antigravity_reads_the_single_magpie_plugin(project: Path) -> None:
    write_stamp(project, {"version": "0.9.0"})
    assert _codes(project, {"magpie": "0.10.0"}, "antigravity") == ["upgrade-pending"]


def test_the_xdg_fallback_marker(project: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = isolated_home / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    (state / "magpie").mkdir(parents=True)
    (state / "magpie" / "magpie-plugin-version").write_text("0.10.0\n")
    write_stamp(project, {"version": "0.9.0"})
    assert _codes(project) == ["upgrade-pending"]


def test_an_unreadable_running_version_says_nothing(project: Path) -> None:
    write_stamp(project, {"version": "0.9.0"})
    assert _codes(project) == []


def test_a_garbage_marker_is_ignored(project: Path, isolated_home: Path) -> None:
    write_stamp(project, {"version": "0.9.0"})
    _marker(isolated_home, "not a version")
    assert _codes(project) == []


def test_a_project_never_set_up_is_not_asked(project: Path, isolated_home: Path) -> None:
    _marker(isolated_home, "0.9.0")
    assert _codes(project) == []


def test_the_committed_stamp_is_the_fallback_baseline(project: Path, isolated_home: Path) -> None:
    write_lock(
        project,
        """
        method: marketplace
        url: apache/magpie
        min_version: 0.8.0
        plugins:
          - magpie-setup
        reconciled:
          version: 0.8.0
          at:      2026-01-01
        """,
    )
    _marker(isolated_home, "0.9.0")
    assert _codes(project) == ["upgrade-pending"]


@pytest.mark.parametrize("method", ["git-tag", "local"])
def test_snapshot_and_framework_checkouts_are_left_alone(
    project: Path, isolated_home: Path, method: str
) -> None:
    write_lock(project, f"method: {method}\nurl: https://github.com/apache/magpie\nref: v0.8.0\n")
    write_stamp(project, {"version": "0.8.0"})
    _marker(isolated_home, "0.9.0")
    assert _codes(project) == []


def test_record_stops_the_question_and_keeps_the_stamp(project: Path, isolated_home: Path) -> None:
    write_stamp(project, {"version": "0.8.0", "verified_at": "2026-11-01"})
    _marker(isolated_home, "0.9.0")
    block = upgrade.record(project, today=date(2026, 11, 9))
    assert block == {"version": "0.9.0", "at": "2026-11-09"}
    stamp = json.loads((personal(project) / "reconciled.json").read_text())
    assert stamp["verified_at"] == "2026-11-01"
    assert _codes(project) == []


def test_record_without_a_readable_version_refuses(project: Path) -> None:
    with pytest.raises(ValueError):
        upgrade.record(project)
    assert upgrade.main(["record", "--project-root", str(project)]) == 2
    assert upgrade.main(["record", "--project-root", str(project), "--version", "0.9.0"]) == 0
    assert upgrade.baseline(project) == "0.9.0"


def test_every_skill_pre_flight_carries_the_finding(
    project: Path, isolated_home: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("CLAUDECODE", "CODEX_HOME", "CODEX_SANDBOX", "CLAUDE_CODE_ENTRYPOINT"):
        monkeypatch.delenv(name, raising=False)
    write_stamp(project, {"version": "0.8.0"})
    _marker(isolated_home, "0.9.0")
    main(["--skill", "pr-triage", "--project-root", str(project), "--no-welcome", "--no-cache"])
    verdict = json.loads(capsys.readouterr().out)
    assert "upgrade-pending" in [f["code"] for f in verdict["findings"]]
    assert "step-15" in verdict["rules"]


def test_the_rules_section_ships() -> None:
    assert "upgrade-pending" in sections.load("step-15")


# --- gather: the facts setup-upgrade decides its catalogue reads from ---------------

TODAY = date(2026, 11, 15)


def _framework_tools(project: Path, body: str = "echo one\n") -> str:
    """A framework tree with secure-setup files, and its fingerprint."""
    tools = project / "tools" / "agent-isolation"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "agent-iso.sh").write_text(body)
    current = isolated.current(project)
    assert current is not None
    return current


def _isolated(project: Path, **block: object) -> dict[str, object]:
    write_stamp(project, {"version": "0.9.0", "isolated_setup": block})
    return upgrade.isolated_summary(project, TODAY)


@pytest.mark.parametrize(
    ("body", "install"),
    [
        (None, "none"),
        ("method: local\n", "local"),
        ("method: git-tag\nurl: https://github.com/apache/magpie\nref: v0.8.0\n", "snapshot"),
        (
            "method: marketplace\nurl: apache/magpie\nmin_version: 0.8.0\nplugins:\n  - magpie-setup\n",
            "marketplace",
        ),
    ],
)
def test_gather_names_the_verify_branch_for_the_install(
    project: Path, body: str | None, install: str
) -> None:
    if body is not None:
        write_lock(project, body)
    assert upgrade.gather(project, None, None, TODAY)["install"] == install


def test_gather_carries_the_project_findings_and_whether_the_listing_was_read(project: Path) -> None:
    write_lock(project, "method: git-tag\nurl: https://github.com/apache/magpie\nref: v0.8.0\n")
    facts: dict[str, Any] = upgrade.gather(project, None, None, TODAY)
    assert [f["code"] for f in facts["project_findings"]] == ["snapshot-never-fetched"]
    assert facts["listing_known"] is False
    assert upgrade.gather(project, {"magpie-setup": "0.9.0"}, None, TODAY)["listing_known"] is True


def test_gather_reports_an_unconfigured_project(project: Path) -> None:
    facts: dict[str, Any] = upgrade.gather(project, None, None, TODAY)
    assert facts["configured"] is False
    assert facts["shadowed"] == []
    assert facts["layers"]["personal_dir_exists"] is False


def test_a_personal_file_shadowing_a_committed_one_is_listed(project: Path) -> None:
    # Adopted, so the personal layer is the in-tree `.apache-magpie-local/`.
    write_lock(project, "method: local\n")
    local = personal(project)
    committed = project / ".apache-magpie-overrides"
    (local / "templates" / "replies").mkdir(parents=True)
    (committed / "templates" / "replies").mkdir(parents=True)
    for name, mine, theirs in [
        ("project.md", "same\n", "same\n"),
        ("user.md", "mine\n", "theirs\n"),
        ("templates/replies/ack.md", "a\n", "b\n"),
    ]:
        (local / name).write_text(mine)
        (committed / name).write_text(theirs)
    (local / "only-mine.md").write_text("gap filled\n")
    assert upgrade.shadowed(project) == [
        {"file": "project.md", "layer": str(local), "identical": True},
        {"file": "templates/replies/ack.md", "layer": str(local), "identical": False},
        {"file": "user.md", "layer": str(local), "identical": False},
    ]


def test_bookkeeping_and_symlinks_are_never_reported_as_shadowing(project: Path) -> None:
    local = personal(project)
    committed = project / ".apache-magpie-overrides"
    (local / "run").mkdir(parents=True)
    committed.mkdir()
    for name in ("reconciled.json", ".preflight-cache.json", "run/gateway.log", "linked.md"):
        (committed / name).parent.mkdir(parents=True, exist_ok=True)
        (committed / name).write_text("x\n")
    (local / "reconciled.json").write_text("{}")
    (local / ".preflight-cache.json").write_text("{}")
    (local / "run" / "gateway.log").write_text("x\n")
    (local / "linked.md").symlink_to(committed / "linked.md")
    assert upgrade.shadowed(project) == []


def test_no_committed_overrides_means_nothing_is_shadowed(project: Path) -> None:
    local = personal(project)
    local.mkdir(parents=True)
    (local / "project.md").write_text("mine\n")
    assert upgrade.shadowed(project) == []


def test_an_isolated_setup_checked_since_the_last_change_needs_no_attention(project: Path) -> None:
    current = _framework_tools(project)
    facts = _isolated(project, fingerprint=current, updated_at="2026-11-14")
    assert facts["state"] == "in-use"
    assert (facts["changed"], facts["due"], facts["attention"]) == (False, False, False)


def test_a_changed_fingerprint_needs_attention(project: Path) -> None:
    _framework_tools(project)
    facts = _isolated(project, fingerprint="sha256:0000000000000000", updated_at="2026-11-14")
    assert (facts["changed"], facts["due"], facts["attention"]) == (True, False, True)


def test_a_shown_reminder_is_not_a_check_that_ran(project: Path) -> None:
    current = _framework_tools(project)
    facts = _isolated(
        project, fingerprint="sha256:0000000000000000", acknowledged=current, updated_at="2026-11-14"
    )
    assert facts["attention"] is True


@pytest.mark.parametrize(("updated_at", "due"), [("2026-11-08", True), ("2026-11-09", False), (None, True)])
def test_an_old_or_missing_check_is_due(project: Path, updated_at: str | None, due: bool) -> None:
    current = _framework_tools(project)
    block: dict[str, object] = {"fingerprint": current}
    if updated_at is not None:
        block["updated_at"] = updated_at
    facts = _isolated(project, **block)
    assert (facts["due"], facts["attention"]) == (due, due)


def test_an_interval_of_zero_turns_the_timer_off(project: Path) -> None:
    current = _framework_tools(project)
    personal(project).mkdir(parents=True, exist_ok=True)
    (personal(project) / "project.md").write_text("isolated_setup_update_interval_days: 0\n")
    facts = _isolated(project, fingerprint=current, updated_at="2020-01-01")
    assert (facts["due"], facts["attention"]) == (False, False)


def test_an_opted_out_setup_never_needs_attention(project: Path) -> None:
    _framework_tools(project)
    facts = _isolated(project, enabled=False)
    assert (facts["state"], facts["attention"]) == ("opted-out", False)


def test_an_unconfirmed_setup_is_unknown_not_absent(project: Path) -> None:
    _framework_tools(project)
    facts = upgrade.isolated_summary(project, TODAY)
    assert facts["state"] == "unknown"
    assert facts["attention"] is False
    assert facts["changed"] is True


def test_an_unstamped_setup_with_sandbox_toggled_off_locally_is_still_in_use(
    project: Path, isolated_home: Path
) -> None:
    _framework_tools(project)
    (isolated_home / ".claude").mkdir()
    (isolated_home / ".claude" / "settings.json").write_text('{"sandbox": {"enabled": true}}')
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.local.json").write_text('{"sandbox": {"enabled": false}}')
    facts = upgrade.isolated_summary(project, TODAY, home=isolated_home)
    assert facts["state"] == "in-use"
    assert facts["attention"] is True


def test_gather_prints_json(project: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    listing = tmp_path / "listing.json"
    listing.write_text("[]")
    assert upgrade.main(["gather", "--project-root", str(project), "--plugin-list", str(listing)]) == 0
    facts = json.loads(capsys.readouterr().out)
    assert set(facts) == {
        "configured",
        "install",
        "isolated",
        "layers",
        "listing_known",
        "project_findings",
        "shadowed",
    }
