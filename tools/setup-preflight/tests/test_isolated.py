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

"""When the pre-flight proposes `setup-isolated-setup-update`, as tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from setup_preflight import isolated
from setup_preflight.core import isolated_setup_findings

from .conftest import personal, write_stamp

TODAY = date(2026, 9, 26)
REPO_ROOT = Path(__file__).resolve().parents[3]


def framework_tree(root: Path, script: str = "echo one\n") -> None:
    """A checkout that carries the isolated-setup source, as the framework does."""
    tools = root / "tools" / "agent-isolation"
    tools.mkdir(parents=True)
    (tools / "agent-iso.sh").write_text(script, encoding="utf-8")


def enable_sandbox(root: Path) -> None:
    (root / ".claude").mkdir(exist_ok=True)
    (root / ".claude" / "settings.json").write_text(json.dumps({"sandbox": {"enabled": True}}))


def codes(findings: list) -> list[str]:
    return [f.code for f in findings]


def test_a_machine_that_does_not_use_the_isolated_setup_is_never_told(project: Path) -> None:
    framework_tree(project)
    assert isolated_setup_findings(project, today=TODAY) == []


def test_a_sandboxed_project_never_recorded_is_asked_to_run_the_update(project: Path) -> None:
    framework_tree(project)
    enable_sandbox(project)
    [finding] = isolated_setup_findings(project, today=TODAY)
    assert finding.code == "isolated-setup-changed"
    assert finding.facts["recorded"] is None


def test_an_upgrade_that_changes_setup_files_proposes_the_update(project: Path) -> None:
    framework_tree(project)
    before = isolated.current(project)
    write_stamp(project, {"isolated_setup": {"fingerprint": before, "updated_at": "2026-09-25"}})
    (project / "tools" / "agent-isolation" / "agent-iso.sh").write_text("echo two\n")
    [finding] = isolated_setup_findings(project, today=TODAY)
    assert finding.code == "isolated-setup-changed"
    assert finding.facts == {"recorded": before, "current": isolated.current(project)}


def test_a_documentation_only_change_does_not_move_the_fingerprint(project: Path) -> None:
    framework_tree(project)
    before = isolated.current(project)
    (project / "tools" / "agent-isolation" / "README.md").write_text("reworded\n")
    assert isolated.current(project) == before


def test_a_change_already_shown_is_not_repeated(project: Path) -> None:
    framework_tree(project)
    write_stamp(project, {"isolated_setup": {"fingerprint": "sha256:old", "updated_at": "2026-09-25"}})
    isolated.record(project, "reminder", today=TODAY)
    assert isolated_setup_findings(project, today=TODAY) == []


def test_the_reminder_is_weekly_by_default(project: Path) -> None:
    framework_tree(project)
    current = isolated.current(project)
    write_stamp(project, {"isolated_setup": {"fingerprint": current, "updated_at": "2026-09-20"}})
    assert isolated_setup_findings(project, today=TODAY) == []
    write_stamp(project, {"isolated_setup": {"fingerprint": current, "updated_at": "2026-09-19"}})
    [finding] = isolated_setup_findings(project, today=TODAY)
    assert finding.code == "isolated-setup-update-due"
    assert finding.facts == {"days_since": 7, "interval_days": 7}


def test_a_reminder_already_shown_rearms_the_timer(project: Path) -> None:
    framework_tree(project)
    current = isolated.current(project)
    write_stamp(
        project,
        {"isolated_setup": {"fingerprint": current, "updated_at": "2026-08-01", "reminded_at": "2026-09-24"}},
    )
    assert isolated_setup_findings(project, today=TODAY) == []


def test_the_interval_is_configurable_personal_config_first(project: Path) -> None:
    framework_tree(project)
    current = isolated.current(project)
    write_stamp(project, {"isolated_setup": {"fingerprint": current, "updated_at": "2026-09-16"}})
    (project / ".apache-magpie-overrides").mkdir()
    (project / ".apache-magpie-overrides" / "project.md").write_text(
        "setup:\n  isolated_setup_update_interval_days: 30\n"
    )
    assert isolated_setup_findings(project, today=TODAY) == []
    (personal(project) / "project.md").write_text("setup:\n  isolated_setup_update_interval_days: 3\n")
    assert codes(isolated_setup_findings(project, today=TODAY)) == ["isolated-setup-update-due"]


def test_zero_disables_the_timer_but_not_the_change_report(project: Path) -> None:
    framework_tree(project)
    write_stamp(project, {"isolated_setup": {"fingerprint": isolated.current(project)}})
    assert isolated_setup_findings(project, interval_days=0, today=TODAY) == []
    write_stamp(project, {"isolated_setup": {"fingerprint": "sha256:old"}})
    assert codes(isolated_setup_findings(project, interval_days=0, today=TODAY)) == ["isolated-setup-changed"]


def test_an_explicit_opt_out_silences_everything(project: Path) -> None:
    framework_tree(project)
    enable_sandbox(project)
    write_stamp(project, {"isolated_setup": {"enabled": False}})
    assert isolated_setup_findings(project, today=TODAY) == []


def test_recording_an_update_clears_both_reasons(project: Path) -> None:
    framework_tree(project)
    enable_sandbox(project)
    block = isolated.record(project, "update", today=TODAY)
    assert block["fingerprint"] == isolated.current(project)
    assert isolated_setup_findings(project, today=TODAY) == []


def test_recording_keeps_the_rest_of_the_stamp(project: Path) -> None:
    write_stamp(project, {"verified_at": "2026-09-01", "acknowledged": {"sweep": "0.2.0"}})
    isolated.record(project, "reminder", today=TODAY)
    stamp = json.loads((personal(project) / "reconciled.json").read_text())
    assert stamp["verified_at"] == "2026-09-01"
    assert stamp["acknowledged"] == {"sweep": "0.2.0"}
    assert stamp["isolated_setup"]["reminded_at"] == "2026-09-26"


def test_recording_in_an_unadopted_repo_writes_the_git_dir_home(project: Path) -> None:
    """Never the working tree: the stamp lands inside `.git/`."""
    isolated.record(project, "reminder", today=TODAY)
    assert (project / ".git" / "apache-magpie" / "reconciled.json").is_file()
    assert not (project / ".apache-magpie-local").exists()


def test_recording_in_an_adopted_repo_writes_the_in_tree_local_dir(project: Path) -> None:
    (project / ".apache-magpie.lock").write_text("method: local\nsource: skills/\n")
    isolated.record(project, "reminder", today=TODAY)
    assert (project / ".apache-magpie-local" / "reconciled.json").is_file()
    assert not (project / ".git" / "apache-magpie").exists()


def test_recording_carries_a_legacy_stamp_over_to_the_git_dir_home(project: Path) -> None:
    legacy = project / ".apache-magpie-local"
    legacy.mkdir()
    (legacy / "reconciled.json").write_text(json.dumps({"verified_at": "2026-09-01"}))
    isolated.record(project, "reminder", today=TODAY)
    stamp = json.loads((project / ".git" / "apache-magpie" / "reconciled.json").read_text())
    assert stamp["verified_at"] == "2026-09-01"
    # Read and carried over, never deleted: moving it is the user's call.
    assert (legacy / "reconciled.json").is_file()


def test_recording_without_version_control_writes_the_in_tree_dir(tmp_path: Path) -> None:
    isolated.record(tmp_path, "reminder", today=TODAY)
    assert (tmp_path / ".apache-magpie-local" / isolated.STAMP_NAME).is_file()


def test_recording_in_an_svn_working_copy_writes_the_svn_dir(tmp_path: Path) -> None:
    (tmp_path / ".svn").mkdir()
    (tmp_path / ".svn" / "wc.db").write_bytes(b"")
    isolated.record(tmp_path, "reminder", today=TODAY)
    assert (tmp_path / ".svn" / "apache-magpie" / isolated.STAMP_NAME).is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == [".svn"]


def test_the_interval_is_read_from_a_legacy_local_dir(project: Path) -> None:
    legacy = project / ".apache-magpie-local"
    legacy.mkdir()
    (legacy / "project.md").write_text("setup:\n  isolated_setup_update_interval_days: 3\n")
    assert isolated.interval_days(project) == 3
    assert not (project / ".git" / "apache-magpie").exists()


def test_a_snapshot_install_reads_the_fingerprint_from_the_snapshot(project: Path) -> None:
    framework_tree(project / ".apache-magpie")
    assert isolated.current(project) == isolated.compute(project / ".apache-magpie")


def test_without_framework_source_the_shipped_constant_is_used(project: Path) -> None:
    assert isolated.current(project) == isolated.shipped()


@pytest.mark.skipif(not (REPO_ROOT / "tools" / "agent-isolation").is_dir(), reason="needs the framework tree")
def test_the_shipped_constant_matches_the_framework_tree() -> None:
    """The prek hook keeps this in sync; a failure means it was bypassed."""
    assert isolated.shipped() == isolated.compute(REPO_ROOT)


def test_nothing_configured_is_not_configured(project: Path) -> None:
    assert isolated.configured(project) is False


@pytest.mark.parametrize("name", ["settings.json", "settings.local.json"])
def test_a_sandbox_in_the_user_settings_is_configured(project: Path, isolated_home: Path, name: str) -> None:
    """The whole-user install scope leaves no trace in the project."""
    (isolated_home / ".claude").mkdir()
    (isolated_home / ".claude" / name).write_text('{"sandbox": {"enabled": true}}')
    assert isolated.configured(project) is True


def test_a_sandbox_in_the_project_settings_is_configured(project: Path) -> None:
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.local.json").write_text('{"sandbox": {"enabled": true}}')
    assert isolated.configured(project) is True


def test_unreadable_user_settings_are_not_configured(project: Path, isolated_home: Path) -> None:
    (isolated_home / ".claude").mkdir()
    (isolated_home / ".claude" / "settings.json").write_text("{not json")
    assert isolated.configured(project) is False


def test_the_configured_action_prints_json(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert isolated.main(["configured", "--project-root", str(project)]) == 0
    assert json.loads(capsys.readouterr().out) == {"configured": False}


def adopt(root: Path, project_md: str = "") -> None:
    (root / ".apache-magpie.lock").write_text("method: marketplace\nurl: apache/magpie\n")
    (root / ".apache-magpie-overrides").mkdir(exist_ok=True)
    (root / ".apache-magpie-overrides" / "project.md").write_text(project_md)


def test_session_start_warns_while_unconfigured(project: Path) -> None:
    adopt(project)
    out = json.loads(isolated.session_start(project, "plugin 1.0 is active"))
    assert out["systemMessage"] == isolated.UNCONFIGURED_WARNING
    context = out["hookSpecificOutput"]["additionalContext"]
    assert context.startswith("plugin 1.0 is active\n\n")
    assert isolated.UNCONFIGURED_CONTEXT in context


def test_session_start_warns_from_a_subdirectory(project: Path) -> None:
    adopt(project)
    (project / "src").mkdir()
    assert "systemMessage" in json.loads(isolated.session_start(project / "src"))


def test_the_warning_says_what_matters() -> None:
    """Optional for a trial, recommended for longer use, the consequences, and the untrusted-content warning."""
    text = isolated.UNCONFIGURED_WARNING
    for phrase in (
        "do not need it to try Magpie out",
        "/magpie-setup:isolated-setup-install",
        "prompt injection",
        "credentials",
        "do not use Magpie on untrusted content",
    ):
        assert phrase in text


def test_no_warning_in_a_repository_that_has_not_adopted(project: Path) -> None:
    assert isolated.session_start(project, "plugin 1.0 is active") == "plugin 1.0 is active"


def test_no_warning_when_the_project_opted_out(project: Path) -> None:
    adopt(project, "isolated_setup_update_interval_days: 7\nisolation_warning: off\n")
    assert isolated.session_start(project) == ""


def test_a_personal_layer_cannot_opt_out_for_the_project(project: Path) -> None:
    adopt(project)
    local = personal(project)
    local.mkdir(parents=True, exist_ok=True)
    (local / "project.md").write_text("isolation_warning: off\n")
    assert "systemMessage" in json.loads(isolated.session_start(project))


def test_session_start_passes_the_notice_through_once_configured(project: Path) -> None:
    adopt(project)
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text('{"sandbox": {"enabled": true}}')
    assert isolated.session_start(project, "plugin 1.0 is active") == "plugin 1.0 is active"
    assert isolated.session_start(project) == ""
