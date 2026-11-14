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

import pytest

from setup_preflight import sections, upgrade
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
