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

import os
import subprocess
from pathlib import Path

import pytest

from magpie_vcs import (
    BACKENDS,
    GitBackend,
    MercurialBackend,
    SubversionBackend,
    VCSError,
    detect_backend,
    get_backend,
    main,
)

# Tests shell out to `git` in temp repos. If the process inherits
# location-redirecting git env vars (e.g. when the suite runs inside a git
# pre-commit hook), git would operate on the outer repo instead. Strip them
# for the whole module so the fixture's own `git init` is unaffected; the tool
# itself does the same scrub at runtime (see _clean_env).
for _var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX"):
    os.environ.pop(_var, None)

git_required = pytest.mark.skipif(not GitBackend.is_available(), reason="git not installed")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "file.txt").write_text("hello\n")
    _git(repo, "add", "file.txt")
    _git(repo, "commit", "-q", "-m", "initial commit")
    return repo


# -- detection -------------------------------------------------------------


def test_detect_git(git_repo: Path) -> None:
    backend = detect_backend(git_repo)
    assert backend is not None
    assert backend.name == "git"
    assert backend.root == git_repo


def test_detect_marks_hg_and_svn(tmp_path: Path) -> None:
    (tmp_path / ".hg").mkdir()
    backend = detect_backend(tmp_path)
    assert isinstance(backend, MercurialBackend)

    svn = tmp_path / "svn_wc"
    svn.mkdir()
    (svn / ".svn").mkdir()
    assert isinstance(detect_backend(svn), SubversionBackend)


def test_detect_none(tmp_path: Path) -> None:
    assert detect_backend(tmp_path) is None


def test_nested_innermost_wins(git_repo: Path) -> None:
    inner = git_repo / "inner"
    inner.mkdir()
    (inner / ".hg").mkdir()
    backend = detect_backend(inner)
    assert isinstance(backend, MercurialBackend)
    assert backend.root == inner


def test_get_backend_override(git_repo: Path) -> None:
    assert get_backend(git_repo, override="git").name == "git"
    with pytest.raises(VCSError, match="unknown backend"):
        get_backend(git_repo, override="bzr")


def test_get_backend_env(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGPIE_VCS", "hg")
    assert get_backend(git_repo).name == "hg"


def test_get_backend_no_repo(tmp_path: Path) -> None:
    with pytest.raises(VCSError, match="no supported VCS"):
        get_backend(tmp_path)


# -- git backend operations ------------------------------------------------


@git_required
def test_git_clean_then_dirty(git_repo: Path) -> None:
    backend = GitBackend(git_repo)
    assert backend.is_clean()
    (git_repo / "file.txt").write_text("changed\n")
    assert not backend.is_clean()
    assert "file.txt" in backend.status()


@git_required
def test_git_branch_and_commit(git_repo: Path) -> None:
    backend = GitBackend(git_repo)
    assert backend.current_branch() == "main"
    backend.create_branch("fix/thing")
    assert backend.current_branch() == "fix/thing"
    (git_repo / "new.txt").write_text("x\n")
    backend.stage(["new.txt"])
    assert "new.txt" in backend.diff(cached=True)
    backend.commit("add new.txt")
    assert backend.is_clean()
    assert "add new.txt" in backend.log(max_count=1)


@git_required
def test_git_ignores_inherited_git_dir(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate running inside an outer git context (e.g. a pre-commit hook):
    # the tool must resolve the repo from its cwd, not from $GIT_DIR.
    monkeypatch.setenv("GIT_DIR", str(git_repo.parent / "elsewhere" / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(git_repo.parent / "elsewhere" / "index"))
    backend = GitBackend(git_repo)
    assert backend.current_branch() == "main"
    assert backend.is_clean()


@git_required
def test_git_log_grep(git_repo: Path) -> None:
    backend = GitBackend(git_repo)
    assert "initial commit" in backend.log(grep="initial")
    assert backend.log(grep="nonexistent-token").strip() == ""


@git_required
def test_git_stage_nothing_rejected(git_repo: Path) -> None:
    with pytest.raises(VCSError, match="refusing to stage nothing"):
        GitBackend(git_repo).stage([])


@git_required
def test_git_reset_worktree(git_repo: Path) -> None:
    backend = GitBackend(git_repo)
    (git_repo / "file.txt").write_text("dirty\n")
    (git_repo / "untracked.txt").write_text("junk\n")
    backend.reset_worktree()
    assert backend.is_clean()
    assert not (git_repo / "untracked.txt").exists()
    assert (git_repo / "file.txt").read_text() == "hello\n"


# -- unimplemented backends ------------------------------------------------


def test_unimplemented_raise_with_issue(tmp_path: Path) -> None:
    hg = MercurialBackend(tmp_path)
    with pytest.raises(VCSError, match=r"apache/magpie#601"):
        hg.status()
    svn = SubversionBackend(tmp_path)
    with pytest.raises(VCSError, match=r"apache/magpie#602"):
        svn.commit("x")
    assert svn.distributed is False  # centralized model flagged


def test_registry_unique_names() -> None:
    names = [b.name for b in BACKENDS]
    assert names == sorted(set(names), key=names.index)
    assert "git" in names


# -- CLI -------------------------------------------------------------------


@git_required
def test_cli_detect_and_status(git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-C", str(git_repo), "detect"]) == 0
    assert capsys.readouterr().out.strip() == "git"

    (git_repo / "file.txt").write_text("z\n")
    assert main(["-C", str(git_repo), "clean"]) == 1
    main(["-C", str(git_repo), "reset-worktree"])
    assert main(["-C", str(git_repo), "clean"]) == 0


def test_cli_backends_lists_all(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["backends"]) == 0
    out = capsys.readouterr().out
    for name in ("git", "hg", "svn"):
        assert name in out


def test_cli_unknown_backend_errors(git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-C", str(git_repo), "--backend", "bzr", "status"]) == 2
    assert "unknown backend" in capsys.readouterr().err


def test_cli_unimplemented_backend_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".hg").mkdir()
    assert main(["-C", str(tmp_path), "status"]) == 2
    assert "apache/magpie#601" in capsys.readouterr().err
