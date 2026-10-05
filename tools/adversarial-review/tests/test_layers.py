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

from adversarial_review import layers

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


# --- the main checkout of a linked worktree: shared vectors -------------------------

LOCAL = ".apache-magpie-local"


def _linked_worktree(tmp_path: Path, *, adopt: bool = True) -> tuple[Path, Path]:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    if adopt:
        for root in (main, wt):
            (root / ".apache-magpie.lock").write_text("method: local\n")
    return main, wt


def test_vector_main_worktree_of_a_linked_worktree(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    assert layers.main_worktree(wt) == main


def test_vector_main_worktree_of_the_main_checkout_is_none(tmp_path: Path) -> None:
    main, _ = _linked_worktree(tmp_path)
    assert layers.main_worktree(main) is None


def test_vector_main_worktree_of_a_bare_repository_is_none(tmp_path: Path) -> None:
    common = tmp_path / "repo.git"
    wt_gitdir = common / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.main_worktree(wt) is None


def test_vector_main_worktree_of_a_submodule_is_none(tmp_path: Path) -> None:
    (tmp_path / "super" / ".git" / "modules" / "sub").mkdir(parents=True)
    sub = tmp_path / "super" / "sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
    assert layers.main_worktree(sub) is None


def test_vector_main_worktree_outside_a_repository_is_none(tmp_path: Path) -> None:
    assert layers.main_worktree(tmp_path) is None


def test_vector_adopted_worktree_without_its_own_dir_uses_the_main_checkouts(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    (main / LOCAL).mkdir()
    assert layers.personal_layers(wt) == [wt / LOCAL, main / LOCAL]
    assert layers.personal_dir(wt) == main / LOCAL


def test_vector_adopted_worktree_with_its_own_dir_writes_there(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    (main / LOCAL).mkdir()
    (wt / LOCAL).mkdir()
    assert layers.personal_layers(wt) == [wt / LOCAL, main / LOCAL]
    assert layers.personal_dir(wt) == wt / LOCAL


def test_vector_adopted_worktree_with_neither_dir_writes_its_own(tmp_path: Path) -> None:
    _, wt = _linked_worktree(tmp_path)
    assert layers.personal_layers(wt) == [wt / LOCAL]
    assert layers.personal_dir(wt) == wt / LOCAL


def test_vector_a_worktree_falls_back_to_the_main_checkout_file_by_file(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    for root in (main, wt):
        (root / LOCAL).mkdir()
    (main / LOCAL / "a.md").write_text("main")
    (main / LOCAL / "b.md").write_text("main")
    (wt / LOCAL / "a.md").write_text("worktree")

    def first(name: str) -> Path | None:
        return next((p / name for p in layers.config_layers(wt) if (p / name).exists()), None)

    assert first("a.md") == wt / LOCAL / "a.md"
    assert first("b.md") == main / LOCAL / "b.md"


def test_vector_the_main_checkout_does_not_fall_back(tmp_path: Path) -> None:
    main, _ = _linked_worktree(tmp_path)
    assert layers.personal_layers(main) == [main / LOCAL]
    assert layers.personal_dir(main) == main / LOCAL


def test_vector_an_unadopted_worktree_is_unchanged(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path, adopt=False)
    (main / LOCAL).mkdir()
    assert layers.personal_layers(wt) == [main / ".git" / "apache-magpie"]
    assert layers.personal_dir(wt) == main / ".git" / "apache-magpie"
