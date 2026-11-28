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

"""A linked worktree inherits its main checkout's records and writes only its own."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest

from setup_preflight import isolated, layers, sections, upgrade, welcome
from setup_preflight.core import inherited_path_findings

from .conftest import write_lock

LOCK = "method: local\n"


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """An adopted linked worktree and its main checkout, each with a personal layer."""
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    write_lock(wt, LOCK)
    for root in (main, wt):
        (root / ".apache-magpie-local").mkdir()
    return main, wt


def test_an_inherited_path_swapped_for_a_symlink_is_reported(tmp_path: Path, isolated_home: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    assert inherited_path_findings(wt) == []
    assert inherited_path_findings(main) == []  # a main checkout inherits nothing
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (main / ".apache-magpie-local").rmdir()
    (main / ".apache-magpie-local").symlink_to(elsewhere)
    (main / ".claude").symlink_to(elsewhere)
    found = inherited_path_findings(wt)
    assert {f.code for f in found} == {"inherited-path-symlink"}
    assert {f.facts["path"] for f in found} == {
        str(main / ".apache-magpie-local"),
        str(main / ".claude" / "settings.json"),
        str(main / ".claude" / "settings.local.json"),
    }
    assert "inherited-path-symlink" in sections.available()


def test_installing_in_a_worktree_ends_an_isolated_setup_opt_out_it_inherits(
    tmp_path: Path, isolated_home: Path
) -> None:
    """The `isolated_setup` block is inherited whole, so the worktree's own record replaces the opt-out."""
    main, wt = _linked_worktree(tmp_path)
    (main / ".apache-magpie-local" / "reconciled.json").write_text(
        json.dumps({"isolated_setup": {"enabled": False}})
    )
    assert isolated.installed(wt, home=isolated_home, managed_dirs=()) is False
    # A reminder starts from the inherited block, opt-out included.
    isolated.record(wt, "reminder", today=date(2026, 11, 26))
    assert isolated.installed(wt, home=isolated_home, managed_dirs=()) is False
    # The install or update skill running here ends the opt-out, here only.
    isolated.record(wt, "update", today=date(2026, 11, 26))
    assert isolated.installed(wt, home=isolated_home, managed_dirs=()) is True
    assert isolated.installed(main, home=isolated_home, managed_dirs=()) is False


def test_clearing_a_welcome_answer_twice_reports_nothing_the_second_time(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    (main / ".apache-magpie-local" / "reconciled.json").write_text(
        json.dumps({"welcome": {"magpie-security": {"choice": "never"}}})
    )
    assert welcome.enable(wt, "magpie-security") is True
    assert welcome.enable(wt, "magpie-security") is False


def test_stamp_writers_leave_no_file_that_reads_as_configuration(tmp_path: Path, isolated_home: Path) -> None:
    """A fresh worktree's bookkeeping never redirects `personal_dir` away from the main checkout."""
    main, wt = _linked_worktree(tmp_path)
    (wt / ".apache-magpie-local").rmdir()
    (main / ".apache-magpie-local" / "project.md").write_text("x\n")
    isolated.record(wt, "reminder", today=date(2026, 11, 26))
    welcome.record(wt, "magpie-security", "never")
    names = sorted(p.name for p in (wt / ".apache-magpie-local").iterdir())
    assert names == ["reconciled.json"]
    assert not (main / ".apache-magpie-local" / "reconciled.json").exists()
    assert layers.personal_dir(wt) == main / ".apache-magpie-local"
    assert layers.describe(wt)["stamp_dir"] == str(wt / ".apache-magpie-local")


def test_runtime_state_in_a_worktree_never_redirects_setup_config(tmp_path: Path) -> None:
    """`run/` (gateway sockets, write locks) is bookkeeping: configuration still goes to the main checkout."""
    main, wt = _linked_worktree(tmp_path)
    (main / ".apache-magpie-local" / "project.md").write_text("x\n")
    (wt / ".apache-magpie-local" / "run").mkdir()
    assert layers.personal_dir(wt) == main / ".apache-magpie-local"


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, not root")
def test_an_unreadable_worktree_layer_still_counts_as_its_configuration(tmp_path: Path) -> None:
    _main, wt = _linked_worktree(tmp_path)
    own = wt / ".apache-magpie-local"
    own.chmod(0)
    try:
        assert layers.personal_dir(wt) == own
    finally:
        own.chmod(0o755)


def test_a_worktree_record_does_not_hide_the_main_checkouts_other_records(
    tmp_path: Path, isolated_home: Path
) -> None:
    """The pre-flight's stamp readers inherit what the worktree's stamp lacks, and nothing is copied."""
    main, wt = _linked_worktree(tmp_path)
    (main / ".apache-magpie-local" / "reconciled.json").write_text(
        json.dumps({"verified_at": "2026-11-01", "isolated_setup": {"enabled": False}})
    )
    welcome.record(wt, "security", "dismiss")
    own = json.loads((wt / ".apache-magpie-local" / "reconciled.json").read_text())
    assert set(own) == {"welcome"}
    for reader in (isolated._load_stamp, upgrade._load_stamp):
        merged = reader(wt)
        assert merged["verified_at"] == "2026-11-01"
        assert merged["isolated_setup"] == {"enabled": False}
        assert "welcome" in merged


def test_a_worktree_welcome_answer_never_hides_the_main_checkouts_others(
    tmp_path: Path, isolated_home: Path
) -> None:
    """Entries of a block are inherited one by one, before and after the worktree records its own."""
    main, wt = _linked_worktree(tmp_path)
    shared = main / ".apache-magpie-local" / "reconciled.json"
    shared.write_text(json.dumps({"welcome": {"general": {"choice": "never"}}}))
    welcome.record(wt, "security", "dismiss")
    own = json.loads((wt / ".apache-magpie-local" / "reconciled.json").read_text())
    assert set(own["welcome"]) == {"security"}  # the main checkout's answer is not copied
    shared.write_text(json.dumps({"welcome": {"general": {"choice": "seen", "shown": 1}}}))
    assert welcome._state(wt, "general") == {"choice": "seen", "shown": 1}
    security = welcome._state(wt, "security")
    assert security is not None and security["choice"] == "dismiss"

    assert welcome.enable(wt, "general") is True
    assert welcome.reason_to_show(welcome._state(wt, "general"), "x") == "first-run"
    assert json.loads(shared.read_text())["welcome"]["general"]["choice"] == "seen"  # main untouched
