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

"""Where config lives — the same vectors as `tools/setup-preflight/tests/test_layers.py`."""

from __future__ import annotations

from pathlib import Path

from sandbox_lint import layers

# --- git_common_dir: shared vectors -------------------------------------------------


def test_vector_dot_git_directory_is_the_common_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.git_common_dir(tmp_path) == tmp_path / ".git"


def test_vector_worktree_file_with_relative_commondir(tmp_path: Path) -> None:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.git_common_dir(wt) == main / ".git"


def test_vector_worktree_file_with_relative_gitdir(tmp_path: Path) -> None:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = main / "nested" / "wt"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../.git/worktrees/wt\n")
    assert layers.git_common_dir(wt) == main / ".git"


def test_vector_worktree_file_with_absolute_commondir(tmp_path: Path) -> None:
    common = tmp_path / "elsewhere.git"
    wt_gitdir = common / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text(f"{common}\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.git_common_dir(wt) == common


def test_vector_gitdir_file_without_commondir_is_its_own_common_dir(tmp_path: Path) -> None:
    """A submodule: `.git` points at `.git/modules/<name>`, which has no `commondir`."""
    module = tmp_path / "super" / ".git" / "modules" / "sub"
    module.mkdir(parents=True)
    sub = tmp_path / "super" / "sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
    assert layers.git_common_dir(sub) == module


def test_vector_not_a_repository(tmp_path: Path) -> None:
    assert layers.git_common_dir(tmp_path) is None


def test_vector_malformed_dot_git_file(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("not a gitdir line\n")
    assert layers.git_common_dir(tmp_path) is None


def test_vector_dangling_gitdir(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text(f"gitdir: {tmp_path / 'gone'}\n")
    assert layers.git_common_dir(tmp_path) is None


# --- the layers ---------------------------------------------------------------------


def test_layers_unadopted_repo_uses_the_git_dir_home(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.config_layers(tmp_path) == [
        tmp_path / ".git" / "apache-magpie",
        tmp_path / ".apache-magpie-overrides",
    ]


def test_layers_adopted_repo_uses_the_in_tree_local_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    (tmp_path / ".apache-magpie-local").mkdir()
    assert layers.config_layers(tmp_path) == [
        tmp_path / ".apache-magpie-local",
        tmp_path / ".apache-magpie-overrides",
    ]


def test_layers_legacy_in_tree_dir_is_a_read_fallback(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie-local").mkdir()
    assert layers.config_layers(tmp_path) == [
        tmp_path / ".git" / "apache-magpie",
        tmp_path / ".apache-magpie-local",
        tmp_path / ".apache-magpie-overrides",
    ]


def test_layers_not_a_repo_and_not_adopted_has_no_personal_layer(tmp_path: Path) -> None:
    assert layers.personal_dir(tmp_path) is None
    assert layers.config_layers(tmp_path) == [tmp_path / ".apache-magpie-overrides"]


def test_layers_never_create_anything(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    layers.config_layers(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [".git"]
    assert list((tmp_path / ".git").iterdir()) == []


# --- the gateway's run directory ----------------------------------------------------


def test_run_dir_adopted_is_in_tree(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    assert layers.default_run_dir(tmp_path) == tmp_path / ".apache-magpie-local" / "run"


def test_run_dir_unadopted_is_in_the_git_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.default_run_dir(tmp_path) == tmp_path / ".git" / "apache-magpie" / "run" / "main"


def test_run_dir_of_a_linked_worktree_is_under_the_common_dir(tmp_path: Path) -> None:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.default_run_dir(wt) == main / ".git" / "apache-magpie" / "run" / "wt"
    assert layers.default_run_dir(main) == main / ".git" / "apache-magpie" / "run" / "main"


def test_run_dir_ignores_a_legacy_in_tree_dir_when_unadopted(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie-local" / "run").mkdir(parents=True)
    assert layers.default_run_dir(tmp_path) == tmp_path / ".git" / "apache-magpie" / "run" / "main"


def test_run_dir_outside_a_repo_unadopted_is_none(tmp_path: Path) -> None:
    assert layers.default_run_dir(tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_run_dir_candidates_name_both_locations(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.run_dir_candidates(tmp_path) == [
        tmp_path / ".apache-magpie-local" / "run",
        tmp_path / ".git" / "apache-magpie" / "run" / "main",
    ]


def test_worktree_ids(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.worktree_id(tmp_path) == "main"
    assert layers.worktree_id(tmp_path / "nowhere") is None


def test_an_unsafe_worktree_name_is_refused(tmp_path: Path) -> None:
    import pytest

    bad = tmp_path / "main" / ".git" / "worktrees" / "we ird$"
    bad.mkdir(parents=True)
    (bad / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {bad}\n")
    with pytest.raises(layers.InvalidWorktreeId):
        layers.default_run_dir(wt)
    # Recognition never raises: it just offers no git-directory candidate.
    assert layers.run_dir_candidates(wt) == [wt / ".apache-magpie-local" / "run"]


def test_valid_worktree_id() -> None:
    assert layers.valid_worktree_id("feat.x_1-2")
    for bad in ("", ".", "..", "a/b", "a b", "ä"):
        assert not layers.valid_worktree_id(bad)
