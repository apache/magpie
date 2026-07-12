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
import subprocess
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


# ---- rule 3: release-archive symlink safety -------------------------------


def _git_repo(root: Path, gitattributes: str = "") -> None:
    """Init a git repo at ``root``, write ``.gitattributes``, and stage every
    file so `git write-tree` / `git archive` have a tree to work on."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    if gitattributes:
        (root / ".gitattributes").write_text(gitattributes)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)


def test_archive_single_hop_links_clean(tmp_path: Path) -> None:
    # .agents/skills/magpie-x -> ../../skills/x (a real dir): the only view
    # shipped, and it resolves to a real file — extractor-safe.
    (tmp_path / "skills" / "x").mkdir(parents=True)
    (tmp_path / "skills" / "x" / "SKILL.md").write_text("x\n")
    _symlink(tmp_path, ".agents/skills/magpie-x", "../../skills/x")
    _git_repo(tmp_path)
    assert symlink_lint.find_archive_symlink_problems(tmp_path) == []


def test_archive_relay_chain_flagged(tmp_path: Path) -> None:
    # A .claude relay chaining through .agents (target is itself a symlink)
    # ships in the archive -> a safe extractor rejects it. This is the exact
    # shape that -1'd the RC upload.
    _wire_skill(tmp_path, relay_target="../../.agents/skills/magpie-x")
    _git_repo(tmp_path)
    problems = symlink_lint.find_archive_symlink_problems(tmp_path)
    assert [(p, kind) for p, _t, kind in problems] == [(".claude/skills/magpie-x", "chain")]


def test_archive_relay_chain_export_ignored_is_clean(tmp_path: Path) -> None:
    # The fix: export-ignore the relay dir so only the single-hop .agents view
    # ships. The chain never reaches the archive.
    _wire_skill(tmp_path, relay_target="../../.agents/skills/magpie-x")
    _git_repo(tmp_path, gitattributes=".claude/skills/ export-ignore\n")
    assert symlink_lint.find_archive_symlink_problems(tmp_path) == []


def test_archive_dangling_link_flagged(tmp_path: Path) -> None:
    # export-ignore the real skills/ dir but keep the .agents view: the link's
    # target is gone from the archive -> dangling.
    (tmp_path / "skills" / "x").mkdir(parents=True)
    (tmp_path / "skills" / "x" / "SKILL.md").write_text("x\n")
    _symlink(tmp_path, ".agents/skills/magpie-x", "../../skills/x")
    # Root-anchored so only the real skills/ dir drops, not .agents/skills/.
    _git_repo(tmp_path, gitattributes="/skills/ export-ignore\n")
    problems = symlink_lint.find_archive_symlink_problems(tmp_path)
    assert [(p, kind) for p, _t, kind in problems] == [(".agents/skills/magpie-x", "dangling")]


def test_main_archive_flag_returns_one_on_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_skill(tmp_path, relay_target="../../.agents/skills/magpie-x")
    _git_repo(tmp_path)
    monkeypatch.setattr(symlink_lint, "repo_root", lambda: tmp_path)
    assert symlink_lint.main(["--archive"]) == 1


def test_main_archive_flag_returns_zero_when_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_skill(tmp_path, relay_target="../../.agents/skills/magpie-x")
    _git_repo(tmp_path, gitattributes=".claude/skills/ export-ignore\n")
    monkeypatch.setattr(symlink_lint, "repo_root", lambda: tmp_path)
    assert symlink_lint.main(["--archive"]) == 0
