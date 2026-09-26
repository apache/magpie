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

from .conftest import write_stamp

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
    (project / ".apache-magpie-local" / "project.md").write_text(
        "setup:\n  isolated_setup_update_interval_days: 3\n"
    )
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
    stamp = json.loads((project / ".apache-magpie-local" / "reconciled.json").read_text())
    assert stamp["verified_at"] == "2026-09-01"
    assert stamp["acknowledged"] == {"sweep": "0.2.0"}
    assert stamp["isolated_setup"]["reminded_at"] == "2026-09-26"


def test_a_snapshot_install_reads_the_fingerprint_from_the_snapshot(project: Path) -> None:
    framework_tree(project / ".apache-magpie")
    assert isolated.current(project) == isolated.compute(project / ".apache-magpie")


def test_without_framework_source_the_shipped_constant_is_used(project: Path) -> None:
    assert isolated.current(project) == isolated.shipped()


@pytest.mark.skipif(not (REPO_ROOT / "tools" / "agent-isolation").is_dir(), reason="needs the framework tree")
def test_the_shipped_constant_matches_the_framework_tree() -> None:
    """The prek hook keeps this in sync; a failure means it was bypassed."""
    assert isolated.shipped() == isolated.compute(REPO_ROOT)
