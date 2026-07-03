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
"""Behavioural fixtures for symlink-lint's two rules.

Rule 1 (cycles): parity with the earlier bash draft — cyclic -> flagged,
dangling -> skipped, canonical+relay -> allowed, plus pruned / symlink-to-
file / whitespace-name edges.

Rule 2 (relay correctness): canonical links point into ../../skills/;
relays point at ../../.agents/skills/magpie-<skill>.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

import symlink_lint


def _symlink(root: Path, path: str, target: str) -> None:
    """Create a symlink at ``root/<path>`` pointing at ``target``, making
    any missing parent directories first."""
    link = root / path
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, link)


def offending_paths(violations: Iterable[tuple[Any, ...]], root: Path) -> set[str]:
    """Root-relative paths of the flagged links — works for either rule's
    return shape (the link is always the first tuple element)."""
    return {str(link.relative_to(root)) for link, *_ in violations}


def _wire_skill(root: Path, relay_target: str) -> None:
    """Build skills/x + a canonical .agents link + a .claude relay pointing
    at ``relay_target``."""
    (root / "skills" / "x").mkdir(parents=True)
    (root / "skills" / "x" / "SKILL.md").write_text("x\n")
    _symlink(root, ".agents/skills/magpie-x", "../../skills/x")
    _symlink(root, ".claude/skills/magpie-x", relay_target)


# ---- Rule 1: cycles -------------------------------------------------------


def test_self_referential_cycle_detected(tmp_path: Path) -> None:
    _symlink(tmp_path, "skills/foo/loop", target=".")  # loop -> its own dir
    assert offending_paths(symlink_lint.find_cyclic_symlinks(tmp_path), tmp_path) == {"skills/foo/loop"}


def test_indirect_cycle_through_relay_detected(tmp_path: Path) -> None:
    (tmp_path / "skills" / "ctc").mkdir(parents=True)
    _symlink(tmp_path, ".agents/skills/magpie-ctc", "../../skills/ctc")
    # stray in-source relay -> canonical -> back into skills/ctc: a cycle
    _symlink(tmp_path, "skills/ctc/magpie-ctc", "../../.agents/skills/magpie-ctc")
    assert offending_paths(symlink_lint.find_cyclic_symlinks(tmp_path), tmp_path) == {"skills/ctc/magpie-ctc"}


def test_dangling_link_skipped(tmp_path: Path) -> None:
    _symlink(tmp_path, "x/dangling", "../../no-such-dir/skills/thing")
    assert symlink_lint.find_cyclic_symlinks(tmp_path) == []


def test_symlink_to_regular_file_not_flagged(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "real.txt").write_text("x\n")
    _symlink(tmp_path, "a/link.txt", target="real.txt")
    assert symlink_lint.find_cyclic_symlinks(tmp_path) == []


def test_pruned_directory_ignored(tmp_path: Path) -> None:
    _symlink(tmp_path, ".git/loop", target=".")
    assert symlink_lint.find_cyclic_symlinks(tmp_path) == []


def test_source_snapshot_dir_pruned(tmp_path: Path) -> None:
    # The gitignored fetch of a trusted external skill source is a build
    # artefact like the framework snapshot — never scanned. A stray link
    # inside it must not be flagged.
    _symlink(tmp_path, ".apache-magpie-sources/acme/loop", target=".")
    assert symlink_lint.find_cyclic_symlinks(tmp_path) == []
    assert symlink_lint.find_misdirected_relays(tmp_path) == []


def test_symlink_name_with_spaces_detected(tmp_path: Path) -> None:
    _symlink(tmp_path, "weird dir/loop with space", target=".")
    assert offending_paths(symlink_lint.find_cyclic_symlinks(tmp_path), tmp_path) == {
        "weird dir/loop with space"
    }


# ---- Rule 2: relay correctness -------------------------------------------


def test_correct_canonical_and_relay_not_flagged(tmp_path: Path) -> None:
    _wire_skill(tmp_path, relay_target="../../.agents/skills/magpie-x")
    assert symlink_lint.find_cyclic_symlinks(tmp_path) == []
    assert symlink_lint.find_misdirected_relays(tmp_path) == []


def test_relay_pointing_at_source_flagged(tmp_path: Path) -> None:
    # The workflow-security-audit divergence: a .claude relay pointing
    # straight into source instead of through the canonical .agents entry.
    _wire_skill(tmp_path, relay_target="../../skills/x")
    assert offending_paths(symlink_lint.find_misdirected_relays(tmp_path), tmp_path) == {
        ".claude/skills/magpie-x"
    }
    # It is acyclic, so rule 1 does NOT catch it — rule 2 must.
    assert symlink_lint.find_cyclic_symlinks(tmp_path) == []


def test_canonical_pointing_outside_source_flagged(tmp_path: Path) -> None:
    (tmp_path / "skills" / "x").mkdir(parents=True)
    # Canonical should point at ../../skills/x, not at another skill.
    _symlink(tmp_path, ".agents/skills/magpie-x", "../../skills/wrong")
    assert offending_paths(symlink_lint.find_misdirected_relays(tmp_path), tmp_path) == {
        ".agents/skills/magpie-x"
    }


def test_non_magpie_symlink_ignored_by_relay_rule(tmp_path: Path) -> None:
    (tmp_path / "other").mkdir()
    _symlink(tmp_path, ".claude/skills/not-magpie", "../../other")
    assert symlink_lint.find_misdirected_relays(tmp_path) == []


# ---- main() ---------------------------------------------------------------


def test_main_returns_zero_when_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_skill(tmp_path, relay_target="../../.agents/skills/magpie-x")
    monkeypatch.setattr(symlink_lint, "repo_root", lambda: tmp_path)
    assert symlink_lint.main() == 0


def test_main_returns_one_on_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _symlink(tmp_path, "skills/foo/loop", target=".")
    monkeypatch.setattr(symlink_lint, "repo_root", lambda: tmp_path)
    assert symlink_lint.main() == 1


def test_main_returns_one_on_misdirected_relay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_skill(tmp_path, relay_target="../../skills/x")
    monkeypatch.setattr(symlink_lint, "repo_root", lambda: tmp_path)
    assert symlink_lint.main() == 1
