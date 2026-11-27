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

"""User-enabled families a project has not adopted: what is asked, applied, and hinted."""

from __future__ import annotations

import io
import json
import os
from datetime import date
from pathlib import Path

import pytest

from setup_preflight import isolated, layers, local_families, sections, welcome
from setup_preflight.core import family_not_adopted_findings

from .conftest import personal, write_lock, write_stamp

FLOOR_LOCK = """
    method: marketplace
    url: https://github.com/apache/magpie
    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard
      - magpie-vetted-ops
      - magpie-security
      - magpie-security-tools
"""
PR_SKILL = "pr-triage"  # pr-management
SECURITY_SKILL = "issue-sync"  # security, on the floor


def user_settings(home: Path, enabled: dict[str, object]) -> None:
    path = home / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"enabledPlugins": enabled}), encoding="utf-8")


def local_settings(root: Path, enabled: dict[str, object]) -> None:
    path = root / ".claude" / "settings.local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"enabledPlugins": enabled}), encoding="utf-8")


def stamp(root: Path) -> dict:
    return json.loads((personal(root) / "reconciled.json").read_text(encoding="utf-8"))


@pytest.fixture
def adopted(project: Path, isolated_home: Path) -> Path:
    write_lock(project, FLOOR_LOCK)
    user_settings(
        isolated_home,
        {
            "magpie-pr-management@apache-magpie": True,
            "magpie-release-management@apache-magpie": True,
            "magpie-contributor-growth@apache-magpie": True,
            "magpie-security@apache-magpie": True,
            "magpie-agent-guard@apache-magpie": True,
            "magpie-adversarial-review@apache-magpie": True,
            "magpie-repo-health@apache-magpie": False,
            "magpie-issue@some-other-marketplace": True,
        },
    )
    return project


# --- the candidate list -----------------------------------------------------------


def test_candidates_are_user_enabled_families_minus_the_floor(adopted: Path) -> None:
    answer = local_families.candidates(adopted)
    assert answer["applicable"] is True
    # On the floor (security), disabled (repo-health), another marketplace
    # (issue) and substrate plugins (agent-guard, adversarial-review) are out.
    assert answer["ask"] == [
        "magpie-contributor-growth",
        "magpie-pr-management",
        "magpie-release-management",
    ]
    assert answer["apply"] == []
    assert answer["settings_entries"]["magpie-pr-management"] == "magpie-pr-management@apache-magpie"


def test_substrate_plugins_are_never_family_plugins() -> None:
    plugins = local_families.family_plugins()
    assert "magpie-pr-management" in plugins
    for substrate in ("magpie-agent-guard", "magpie-vetted-ops", "magpie-security-tools", "magpie-setup"):
        assert substrate not in plugins


def test_not_applicable_without_an_adopted_lock(project: Path, isolated_home: Path) -> None:
    user_settings(isolated_home, {"magpie-pr-management@apache-magpie": True})
    assert local_families.candidates(project) == {"applicable": False, "reason": "not-adopted"}
    write_lock(project, "method: local\nplugins:\n  - magpie-setup\n")
    assert local_families.candidates(project)["applicable"] is False


def test_unreadable_user_settings_are_unknown_not_empty(adopted: Path, isolated_home: Path) -> None:
    path = isolated_home / ".claude" / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert local_families.candidates(adopted) == {
        "applicable": False,
        "reason": "user-settings-unreadable",
        "path": str(path),
    }


def test_a_missing_or_dangling_user_settings_file_is_unknown(adopted: Path, isolated_home: Path) -> None:
    """A sandbox can make the file look missing rather than denied."""
    path = isolated_home / ".claude" / "settings.json"
    path.unlink()
    assert local_families.candidates(adopted)["reason"] == "user-settings-unreadable"
    path.symlink_to(isolated_home / "denied" / "settings.json")
    assert local_families.candidates(adopted)["reason"] == "user-settings-unreadable"
    assert family_not_adopted_findings(adopted, PR_SKILL, "claude") == []


def test_a_malformed_enabled_plugins_block_is_unknown(adopted: Path, isolated_home: Path) -> None:
    (isolated_home / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": []}))
    assert local_families.candidates(adopted)["reason"] == "user-settings-unreadable"


def test_an_unreadable_lock_is_reported_not_taken_for_unadopted(adopted: Path) -> None:
    (adopted / ".apache-magpie.lock").write_text("method: marketplace\nbogus_key: 1\n")
    answer = local_families.candidates(adopted)
    assert answer["reason"] == "lock-unreadable"
    assert answer["path"].endswith(".apache-magpie.lock")


def test_a_hidden_family_the_project_adopted_since_is_restored(adopted: Path) -> None:
    here = str(adopted.resolve())
    write_stamp(adopted, {"local_families": {"magpie-security": {"choice": "disable", "worktrees": [here]}}})
    local_settings(adopted, {"magpie-security@apache-magpie": False})
    answer = local_families.candidates(adopted)
    assert answer["restore"] == ["magpie-security"]
    assert answer["settings_entries"]["magpie-security"] == "magpie-security@apache-magpie"
    local_settings(adopted, {})
    assert local_families.candidates(adopted)["restore"] == []


def test_a_false_magpie_did_not_apply_here_is_never_restored(adopted: Path) -> None:
    """A disable recorded for other worktrees plus the user's own false here: the false is the user's."""
    write_stamp(
        adopted, {"local_families": {"magpie-security": {"choice": "disable", "worktrees": ["/elsewhere"]}}}
    )
    local_settings(adopted, {"magpie-security@apache-magpie": False})
    assert local_families.candidates(adopted)["restore"] == []


def test_a_false_in_committed_settings_is_never_restored(adopted: Path) -> None:
    here = str(adopted.resolve())
    write_stamp(adopted, {"local_families": {"magpie-security": {"choice": "disable", "worktrees": [here]}}})
    (adopted / ".claude").mkdir(exist_ok=True)
    (adopted / ".claude" / "settings.json").write_text(
        json.dumps({"enabledPlugins": {"magpie-security@apache-magpie": False}})
    )
    assert local_families.candidates(adopted)["restore"] == []


def test_a_restore_needs_no_user_enabled_family(adopted: Path) -> None:
    """With no user-scope settings file, the caller passes an empty block and still gets the restore."""
    here = str(adopted.resolve())
    write_stamp(adopted, {"local_families": {"magpie-security": {"choice": "disable", "worktrees": [here]}}})
    local_settings(adopted, {"magpie-security@apache-magpie": False})
    answer = local_families.candidates(adopted, user_settings={})
    assert answer["restore"] == ["magpie-security"]
    assert answer["ask"] == []


def test_a_restored_family_is_not_offered_again_and_a_later_drop_asks_anew(adopted: Path) -> None:
    here = str(adopted.resolve())
    write_stamp(adopted, {"local_families": {"magpie-security": {"choice": "disable", "worktrees": [here]}}})
    local_settings(adopted, {"magpie-security@apache-magpie": False})
    assert local_families.candidates(adopted)["restore"] == ["magpie-security"]
    local_families.record(adopted, "magpie-security", "restored")
    # The user later sets their own false: it is theirs now, never offered for removal.
    assert local_families.candidates(adopted)["restore"] == []
    local_families.record(adopted, "magpie-security", "hinted")
    assert local_families.decisions(adopted)["magpie-security"]["choice"] == "restored"
    # The floor drops the family again: it is asked about, not re-hidden in silence.
    write_lock(adopted, FLOOR_LOCK.replace("      - magpie-security\n", ""))
    local_settings(adopted, {})
    answer = local_families.candidates(adopted)
    assert "magpie-security" in answer["ask"]
    assert "magpie-security" not in answer["apply"]


def _linked_with_hide_in_main(tmp_path: Path, isolated_home: Path) -> tuple[Path, Path]:
    main, wt = _linked_worktree(tmp_path)
    write_lock(main, FLOOR_LOCK)
    user_settings(isolated_home, {"magpie-security@apache-magpie": True})
    return main, wt


def test_a_hide_applied_in_the_main_checkout_is_restored_only_from_there(
    tmp_path: Path, isolated_home: Path
) -> None:
    """The `restored` record must land in the stamp holding the `disable`, which a worktree cannot write."""
    main, wt = _linked_with_hide_in_main(tmp_path, isolated_home)
    (main / ".apache-magpie-local" / "reconciled.json").write_text(
        json.dumps(
            {"local_families": {"magpie-security": {"choice": "disable", "worktrees": [str(main.resolve())]}}}
        )
    )
    local_settings(main, {"magpie-security@apache-magpie": False})
    answer = local_families.candidates(wt)
    assert answer["restore"] == []
    assert answer["restore_in_main"] == ["magpie-security"]
    assert answer["restore_in_main_files"]["magpie-security"] == str(main / ".claude" / "settings.local.json")
    from_main = local_families.candidates(main)
    assert from_main["restore"] == ["magpie-security"]
    assert from_main["restore_in_main"] == []


def test_the_users_false_in_the_main_checkout_is_never_restored_from_a_worktree(
    tmp_path: Path, isolated_home: Path
) -> None:
    main, wt = _linked_with_hide_in_main(tmp_path, isolated_home)
    (wt / ".apache-magpie-local" / "reconciled.json").write_text(
        json.dumps(
            {"local_families": {"magpie-security": {"choice": "disable", "worktrees": [str(wt.resolve())]}}}
        )
    )
    local_settings(main, {"magpie-security@apache-magpie": False})  # the user's, in the main checkout
    assert local_families.candidates(wt)["restore"] == []


def test_a_worktree_record_never_vouches_for_a_hide_in_the_main_checkout(
    tmp_path: Path, isolated_home: Path
) -> None:
    """The worktree's own stamp is sandbox-writable; only the main checkout's may vouch for its settings."""
    main, wt = _linked_with_hide_in_main(tmp_path, isolated_home)
    forged = {
        "local_families": {"magpie-security": {"choice": "disable", "worktrees": [str(main.resolve())]}}
    }
    (wt / ".apache-magpie-local" / "reconciled.json").write_text(json.dumps(forged))
    local_settings(main, {"magpie-security@apache-magpie": False})
    assert local_families.candidates(wt)["restore"] == []


def test_claude_config_dir_is_honoured(tmp_path: Path) -> None:
    assert (
        local_families.user_settings_path({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path / "settings.json"
    )


# --- filtering by recorded decisions ------------------------------------------------


def test_keep_is_never_asked_again(adopted: Path) -> None:
    local_families.record(adopted, "magpie-contributor-growth", "keep")
    assert "magpie-contributor-growth" not in local_families.candidates(adopted)["ask"]


def test_hinted_leaves_the_question_open(adopted: Path) -> None:
    local_families.record(adopted, "magpie-pr-management", "hinted")
    assert "magpie-pr-management" in local_families.candidates(adopted)["ask"]


def test_disable_is_applied_not_asked_in_a_new_worktree(adopted: Path, tmp_path_factory) -> None:
    other = tmp_path_factory.mktemp("other-worktree").resolve()
    write_stamp(
        adopted,
        {"local_families": {"magpie-pr-management": {"choice": "disable", "worktrees": [str(other)]}}},
    )
    answer = local_families.candidates(adopted)
    assert "magpie-pr-management" not in answer["ask"]
    assert answer["apply"] == ["magpie-pr-management"]


def test_disable_already_in_this_worktree_is_done(adopted: Path) -> None:
    local_families.record(adopted, "magpie-pr-management", "disable")
    answer = local_families.candidates(adopted)
    assert "magpie-pr-management" not in answer["ask"]
    assert answer["apply"] == []


def test_a_disable_already_present_in_local_settings_is_not_reapplied(adopted: Path) -> None:
    write_stamp(adopted, {"local_families": {"magpie-pr-management": {"choice": "disable", "worktrees": []}}})
    local_settings(adopted, {"magpie-pr-management@apache-magpie": False})
    assert local_families.candidates(adopted)["apply"] == []


def test_an_entry_the_user_set_without_magpie_is_never_touched(adopted: Path) -> None:
    local_settings(adopted, {"magpie-release-management@apache-magpie": True})
    answer = local_families.candidates(adopted)
    assert "magpie-release-management" not in answer["ask"]
    assert "magpie-release-management" not in answer["apply"]


# --- recording -------------------------------------------------------------------------


def test_record_merges_and_keeps_other_keys(adopted: Path) -> None:
    write_stamp(adopted, {"version": "0.9.0", "welcome": {"general": {"choice": "seen"}}})
    entry = local_families.record(adopted, "magpie-pr-management", "disable", today=date(2026, 11, 25))
    assert entry == {"choice": "disable", "at": "2026-11-25", "worktrees": [str(adopted.resolve())]}
    saved = stamp(adopted)
    assert saved["version"] == "0.9.0"
    assert saved["welcome"] == {"general": {"choice": "seen"}}
    assert saved["local_families"]["magpie-pr-management"]["choice"] == "disable"


def test_record_never_replaces_a_stamp_it_cannot_parse(adopted: Path) -> None:
    path = personal(adopted) / "reconciled.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"verified_at": "2026-11-25", truncated', encoding="utf-8")
    with pytest.raises(ValueError):
        local_families.record(adopted, "magpie-pr-management", "keep")
    assert path.read_text(encoding="utf-8") == '{"verified_at": "2026-11-25", truncated'
    assert (
        local_families.main(
            ["record", "--project-root", str(adopted), "--plugin", "magpie-pr-management", "--choice", "keep"]
        )
        == 2
    )


def test_hinted_never_overwrites_a_decision(adopted: Path) -> None:
    local_families.record(adopted, "magpie-contributor-growth", "keep")
    local_families.record(adopted, "magpie-contributor-growth", "hinted")
    assert stamp(adopted)["local_families"]["magpie-contributor-growth"]["choice"] == "keep"


def test_record_refuses_substrate_plugins_and_unknown_choices(adopted: Path) -> None:
    with pytest.raises(ValueError):
        local_families.record(adopted, "magpie-agent-guard", "disable")
    with pytest.raises(ValueError):
        local_families.record(adopted, "magpie-pr-management", "remove")


# --- the pre-flight hint -------------------------------------------------------------


def test_hint_fires_once_for_a_non_adopted_family(adopted: Path) -> None:
    findings = family_not_adopted_findings(adopted, PR_SKILL, "claude")
    assert [(f.scope, f.code, f.section, f.facts) for f in findings] == [
        ("family", "family-not-adopted", "family-not-adopted", {"plugin": "magpie-pr-management"})
    ]
    local_families.record(adopted, "magpie-pr-management", "hinted")
    assert family_not_adopted_findings(adopted, PR_SKILL, "claude") == []


def test_no_hint_for_a_floor_family_or_an_unadopted_project(project: Path, isolated_home: Path) -> None:
    user_settings(isolated_home, {"magpie-pr-management@apache-magpie": True})
    assert family_not_adopted_findings(project, PR_SKILL, "claude") == []
    write_lock(project, FLOOR_LOCK)
    assert family_not_adopted_findings(project, SECURITY_SKILL, "claude") == []


def test_no_hint_when_the_family_is_not_user_enabled(project: Path, isolated_home: Path) -> None:
    write_lock(project, FLOOR_LOCK)
    user_settings(isolated_home, {})
    assert family_not_adopted_findings(project, PR_SKILL, "claude") == []


def test_the_hint_section_ships() -> None:
    assert "family-not-adopted" in sections.available()


# --- review follow-ups -----------------------------------------------------------------


def test_a_pinned_snapshot_has_no_floor_to_compare(project: Path, isolated_home: Path) -> None:
    user_settings(isolated_home, {"magpie-pr-management@apache-magpie": True})
    write_lock(project, "method: git-tag\nurl: https://github.com/apache/magpie\nref: v0.9.0\n")
    assert local_families.candidates(project) == {"applicable": False, "reason": "not-adopted"}
    assert family_not_adopted_findings(project, PR_SKILL, "claude") == []


def test_settings_that_are_not_utf8_are_unknown_not_a_crash(adopted: Path) -> None:
    path = adopted / ".claude" / "settings.local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"enabledPlugins": {"\xff": true}}')
    assert local_families.candidates(adopted) == {
        "applicable": False,
        "reason": "project-settings-unreadable",
        "path": str(path),
    }
    assert family_not_adopted_findings(adopted, PR_SKILL, "claude") == []


def test_a_fifo_at_a_settings_path_does_not_block(adopted: Path) -> None:
    path = adopted / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    os.mkfifo(path)
    assert local_families.candidates(adopted)["reason"] == "project-settings-unreadable"


def test_without_posix_a_regular_file_check_replaces_the_nonblocking_open(
    adopted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_families, "SUPPORTED", False)
    assert "magpie-pr-management" in local_families.candidates(adopted)["ask"]
    (adopted / ".claude").mkdir(exist_ok=True)
    (adopted / ".claude" / "settings.json").mkdir()
    assert local_families.candidates(adopted)["reason"] == "project-settings-unreadable"


def test_an_empty_or_relative_home_never_reads_the_repository() -> None:
    assert local_families.user_settings_path({"HOME": ""}) is None
    assert local_families.user_settings_path({"HOME": "relative/home"}) is None
    assert local_families.user_settings_path({"HOME": "/home/u", "CLAUDE_CONFIG_DIR": "rel"}) == Path(
        "/home/u/.claude/settings.json"
    )


def test_a_disable_elsewhere_never_overrides_the_users_own_true_here(adopted: Path) -> None:
    write_stamp(adopted, {"local_families": {"magpie-pr-management": {"choice": "disable", "worktrees": []}}})
    local_settings(adopted, {"magpie-pr-management@apache-magpie": True})
    answer = local_families.candidates(adopted)
    assert "magpie-pr-management" not in answer["apply"]
    assert "magpie-pr-management" not in answer["ask"]


def test_the_hint_is_claude_code_only(adopted: Path) -> None:
    for harness in ("codex", "antigravity", None):
        assert family_not_adopted_findings(adopted, PR_SKILL, harness) == []


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """An adopted linked worktree and its main checkout, each with a personal layer."""
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    write_lock(wt, FLOOR_LOCK)
    for root in (main, wt):
        (root / ".apache-magpie-local").mkdir()
    return main, wt


def test_stamp_writers_leave_no_file_that_reads_as_configuration(tmp_path: Path, isolated_home: Path) -> None:
    """A fresh worktree's bookkeeping never redirects `personal_dir` away from the main checkout."""
    main, wt = _linked_worktree(tmp_path)
    (wt / ".apache-magpie-local").rmdir()
    (main / ".apache-magpie-local" / "project.md").write_text("x\n")
    isolated.record(wt, "reminder", today=date(2026, 11, 26))
    welcome.record(wt, "magpie-security", "never")
    local_families.record(wt, "magpie-security", "keep")
    names = sorted(p.name for p in (wt / ".apache-magpie-local").iterdir())
    assert names == ["reconciled.json"]
    assert layers.personal_dir(wt) == main / ".apache-magpie-local"
    assert layers.describe(wt)["stamp_dir"] == str(wt / ".apache-magpie-local")


def test_a_worktree_stamp_does_not_hide_the_projects_decisions(tmp_path: Path, isolated_home: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    user_settings(isolated_home, {"magpie-contributor-growth@apache-magpie": True})
    (main / ".apache-magpie-local" / "reconciled.json").write_text(
        json.dumps({"local_families": {"magpie-contributor-growth": {"choice": "keep"}}})
    )
    (wt / ".apache-magpie-local" / "reconciled.json").write_text(json.dumps({"verified_at": "2026-11-25"}))
    assert local_families.candidates(wt)["ask"] == []


def test_a_worktree_hint_never_hides_a_decision_in_the_main_checkout(
    tmp_path: Path, isolated_home: Path
) -> None:
    main, wt = _linked_worktree(tmp_path)
    user_settings(isolated_home, {"magpie-pr-management@apache-magpie": True})
    local_families.record(wt, "magpie-pr-management", "hinted")
    (main / ".apache-magpie-local" / "reconciled.json").write_text(
        json.dumps({"local_families": {"magpie-pr-management": {"choice": "keep"}}})
    )
    assert local_families.decisions(wt)["magpie-pr-management"]["choice"] == "keep"
    assert local_families.candidates(wt)["ask"] == []


def test_a_worktree_record_does_not_hide_the_main_checkouts_other_records(
    tmp_path: Path, isolated_home: Path
) -> None:
    """The pre-flight's other stamp readers inherit what the worktree's stamp lacks."""
    from setup_preflight import isolated, upgrade

    main, wt = _linked_worktree(tmp_path)
    (main / ".apache-magpie-local" / "reconciled.json").write_text(
        json.dumps({"verified_at": "2026-11-01", "isolated_setup": {"enabled": False}})
    )
    local_families.record(wt, "magpie-pr-management", "hinted")
    own = json.loads((wt / ".apache-magpie-local" / "reconciled.json").read_text())
    assert set(own) == {"local_families"}  # nothing copied from the main checkout
    for reader in (isolated._load_stamp, upgrade._load_stamp):
        merged = reader(wt)
        assert merged["verified_at"] == "2026-11-01"
        assert merged["isolated_setup"] == {"enabled": False}
        assert "local_families" in merged


def test_answers_are_recorded_in_the_personal_dir_only(tmp_path: Path, isolated_home: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    (wt / ".apache-magpie-local" / "reconciled.json").write_text(json.dumps({"verified_at": "2026-11-25"}))
    local_families.record(wt, "magpie-pr-management", "keep")
    own = json.loads((wt / ".apache-magpie-local" / "reconciled.json").read_text())
    assert own["verified_at"] == "2026-11-25"
    assert own["local_families"]["magpie-pr-management"]["choice"] == "keep"
    assert not (main / ".apache-magpie-local" / "reconciled.json").exists()
    assert not list((wt / ".apache-magpie-local").glob("*.tmp"))


def test_a_worktree_without_a_layer_records_in_its_own_never_the_main_checkouts(
    tmp_path: Path, isolated_home: Path
) -> None:
    """A linked worktree's sandbox may only read the main checkout's layer."""
    from setup_preflight import layers

    main, wt = _linked_worktree(tmp_path)
    (wt / ".apache-magpie-local").rmdir()
    (main / ".apache-magpie-local" / "user.md").write_text("main configuration")
    local_families.record(wt, "magpie-pr-management", "keep")
    own = json.loads((wt / ".apache-magpie-local" / "reconciled.json").read_text())
    assert own["local_families"]["magpie-pr-management"]["choice"] == "keep"
    assert not (main / ".apache-magpie-local" / "reconciled.json").exists()
    # The bookkeeping folder it created never redirects configuration writes.
    assert layers.personal_dir(wt) == main / ".apache-magpie-local"


def test_candidates_say_whether_a_hide_reaches_linked_worktrees(
    tmp_path: Path, adopted: Path, isolated_home: Path
) -> None:
    assert local_families.candidates(adopted)["main_checkout"] is True
    _, wt = _linked_worktree(tmp_path / "linked")
    user_settings(isolated_home, {"magpie-pr-management@apache-magpie": True})
    assert local_families.candidates(wt)["main_checkout"] is False


def test_candidates_take_user_settings_the_caller_read(
    adopted: Path, isolated_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (isolated_home / ".claude" / "settings.json").write_text("{denied", encoding="utf-8")
    supplied = tmp_path / "read-by-agent.json"
    supplied.write_text(json.dumps({"enabledPlugins": {"magpie-repo-health@apache-magpie": True}}))
    assert (
        local_families.main(["candidates", "--project-root", str(adopted), "--user-settings", str(supplied)])
        == 0
    )
    answer = json.loads(capsys.readouterr().out)
    assert answer["applicable"] is True
    assert answer["ask"] == ["magpie-repo-health"]


def test_user_settings_can_come_on_stdin(
    adopted: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (isolated_home / ".claude" / "settings.json").write_text("{denied", encoding="utf-8")
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"enabledPlugins": {"magpie-repo-health@apache-magpie": True}}))
    )
    assert local_families.main(["candidates", "--project-root", str(adopted), "--user-settings", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["ask"] == ["magpie-repo-health"]


def test_a_bare_enabled_plugins_block_is_refused_not_read_as_empty(
    adopted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"magpie-repo-health@apache-magpie": True})))
    assert local_families.main(["candidates", "--project-root", str(adopted), "--user-settings", "-"]) == 2


def test_a_fifo_given_as_user_settings_does_not_block(adopted: Path, tmp_path: Path) -> None:
    fifo = tmp_path / "settings-fifo"
    os.mkfifo(fifo)
    assert (
        local_families.main(["candidates", "--project-root", str(adopted), "--user-settings", str(fifo)]) == 2
    )
