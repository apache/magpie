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
import shutil
import subprocess
from pathlib import Path

import pytest

from magpie_vcs import (
    BACKENDS,
    FossilBackend,
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
hg_required = pytest.mark.skipif(not MercurialBackend.is_available(), reason="hg not installed")
svn_required = pytest.mark.skipif(
    not SubversionBackend.is_available() or shutil.which("svnadmin") is None,
    reason="svn 1.9+ / svnadmin not installed",
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _hg(repo: Path, *args: str) -> None:
    subprocess.run(["hg", *args], cwd=repo, check=True, capture_output=True)


def _svn(cwd: Path, *args: str) -> None:
    subprocess.run(["svn", "--non-interactive", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "file.txt").write_text("hello\n")
    _git(repo, "add", "file.txt")
    _git(repo, "commit", "-q", "-m", "initial commit")
    return repo


@pytest.fixture
def hg_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo_hg"
    repo.mkdir()
    _hg(repo, "init")
    with open(repo / ".hg" / "hgrc", "w") as f:
        f.write("[ui]\nusername = Tester <t@example.com>\n")
    (repo / "file.txt").write_text("hello\n")
    _hg(repo, "add", "file.txt")
    _hg(repo, "commit", "-m", "initial commit")
    return repo


@pytest.fixture
def svn_wc(tmp_path: Path) -> Path:
    """A trunk working copy of a local repo with the standard trunk/branches/tags layout.

    History: r1 creates the layout, r2 (by ``alice``) adds file.txt, r3 (by ``bob``)
    adds other.txt — so ``file.txt`` is ``hello`` at r2 and the WC is at r3.
    """
    repos = tmp_path / "svnrepo"
    subprocess.run(["svnadmin", "create", str(repos)], check=True, capture_output=True)
    url = repos.as_uri()
    _svn(
        tmp_path, "mkdir", "--parents", "-m", "layout",
        f"{url}/proj/trunk", f"{url}/proj/branches", f"{url}/proj/tags",
    )  # fmt: skip
    wc = tmp_path / "wc"
    _svn(tmp_path, "checkout", f"{url}/proj/trunk", str(wc))
    (wc / "file.txt").write_text("hello\n")
    _svn(wc, "add", "file.txt")
    _svn(wc, "commit", "--username", "alice", "-m", "initial commit")
    (wc / "other.txt").write_text("other\n")
    _svn(wc, "add", "other.txt")
    _svn(wc, "commit", "--username", "bob", "-m", "add other.txt")
    _svn(wc, "update")
    return wc


# -- detection -------------------------------------------------------------


def test_detect_git(git_repo: Path) -> None:
    backend = detect_backend(git_repo)
    assert backend is not None
    assert backend.name == "git"
    assert backend.root == git_repo


def test_detect_marks_hg_svn_fossil(tmp_path: Path) -> None:
    (tmp_path / ".hg").mkdir()
    backend = detect_backend(tmp_path)
    assert isinstance(backend, MercurialBackend)

    svn = tmp_path / "svn_wc"
    svn.mkdir()
    (svn / ".svn").mkdir()
    assert isinstance(detect_backend(svn), SubversionBackend)

    fossil_dir = tmp_path / "fossil_wc"
    fossil_dir.mkdir()
    (fossil_dir / ".fslckout").touch()
    assert isinstance(detect_backend(fossil_dir), FossilBackend)

    fossil_dir2 = tmp_path / "fossil_wc_win"
    fossil_dir2.mkdir()
    (fossil_dir2 / "_FOSSIL_").touch()
    assert isinstance(detect_backend(fossil_dir2), FossilBackend)


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


@git_required
def test_git_cat(git_repo: Path) -> None:
    backend = GitBackend(git_repo)
    assert backend.cat("HEAD", "file.txt") == "hello\n"


# -- svn backend operations ------------------------------------------------


@svn_required
def test_svn_detect_from_subdir(svn_wc: Path) -> None:
    sub = svn_wc / "sub"
    sub.mkdir()
    backend = detect_backend(sub)
    assert isinstance(backend, SubversionBackend)
    assert backend.root == svn_wc
    assert backend.distributed is False  # centralized model flagged


@svn_required
def test_svn_clean_then_dirty(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    assert backend.is_clean()
    (svn_wc / "file.txt").write_text("changed\n")
    (svn_wc / "untracked.txt").write_text("u\n")
    status = backend.status()
    assert "M       file.txt" in status
    assert "?       untracked.txt" in status
    assert not backend.is_clean()


@svn_required
def test_svn_branch_switch_and_commit(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    assert backend.current_branch() == "trunk"
    backend.create_branch("feature")
    assert backend.current_branch() == "branches/feature"
    (svn_wc / "pkg").mkdir()
    (svn_wc / "pkg" / "new.txt").write_text("new\n")
    backend.stage(["pkg/new.txt"])  # unversioned parent dir is added too
    backend.commit("add new.txt")
    assert backend.is_clean()
    assert "add new.txt" in backend.log(max_count=1)
    backend.switch("trunk")
    assert backend.current_branch() == "trunk"
    assert not (svn_wc / "pkg").exists()
    backend.switch("feature")  # a name created by create_branch switches back
    assert (svn_wc / "pkg" / "new.txt").read_text() == "new\n"


@svn_required
def test_svn_stage_modified_and_deleted(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    (svn_wc / "file.txt").write_text("changed\n")
    (svn_wc / "other.txt").unlink()
    backend.stage(["file.txt", "other.txt"])  # versioned: no-op; gone from disk: scheduled delete
    assert backend.status().splitlines() == ["M       file.txt", "D       other.txt"]
    backend.commit("edit file.txt, drop other.txt")
    assert backend.is_clean()
    with pytest.raises(VCSError, match="refusing to stage nothing"):
        backend.stage([])


@svn_required
@pytest.mark.parametrize("name", ["", "..", ".", "../escape", "team/fix"])
def test_svn_create_branch_rejects_bad_names(svn_wc: Path, name: str) -> None:
    with pytest.raises(VCSError, match="invalid branch or ref name"):
        SubversionBackend(svn_wc).create_branch(name)
    assert SubversionBackend(svn_wc).current_branch() == "trunk"


@svn_required
def test_svn_branch_name_is_url_quoted(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    backend.create_branch("fix 1")
    assert backend._url().endswith("/branches/fix%201")
    assert backend.current_branch() == "branches/fix 1"  # decoded, not branches/fix%201
    branch = backend.current_branch()
    backend.switch("trunk")
    backend.switch(branch)  # branch output round-trips through switch
    assert backend._url().endswith("/branches/fix%201")
    backend.switch("trunk")
    backend.switch("fix 1")
    assert backend._url().endswith("/branches/fix%201")


def test_svn_too_old_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SubversionBackend, "_version", staticmethod(lambda: (1, 8)))
    assert SubversionBackend.is_available() is False
    with pytest.raises(VCSError, match=r"svn 1\.8 is too old.*1\.9\+"):
        SubversionBackend(tmp_path).status()


@svn_required
def test_svn_layout_uses_rightmost_marker(tmp_path: Path) -> None:
    repos = tmp_path / "nested"
    subprocess.run(["svnadmin", "create", str(repos)], check=True, capture_output=True)
    url = repos.as_uri()
    _svn(
        tmp_path, "mkdir", "--parents", "-m", "layout",
        f"{url}/branches/projects/foo/trunk", f"{url}/branches/projects/foo/branches",
    )  # fmt: skip
    wc = tmp_path / "nestedwc"
    _svn(tmp_path, "checkout", f"{url}/branches/projects/foo/trunk", str(wc))
    backend = SubversionBackend(wc)
    assert backend.current_branch() == "trunk"
    backend.create_branch("fix")
    assert backend._url() == f"{url}/branches/projects/foo/branches/fix"


@svn_required
def test_svn_branch_named_trunk_is_a_branch(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    backend.create_branch("trunk")
    assert backend.current_branch() == "branches/trunk"
    backend.create_branch("fix")  # base stays .../proj, not .../proj/branches
    assert backend._url().endswith("/proj/branches/fix")


@svn_required
def test_svn_switch_rejects_nested_bare_name(svn_wc: Path) -> None:
    with pytest.raises(VCSError, match="one path segment"):
        SubversionBackend(svn_wc).switch("team/fix")


@svn_required
def test_svn_create_branch_outside_layout_rejected(tmp_path: Path) -> None:
    repos = tmp_path / "flat"
    subprocess.run(["svnadmin", "create", str(repos)], check=True, capture_output=True)
    wc = tmp_path / "flatwc"
    _svn(tmp_path, "checkout", repos.as_uri(), str(wc))
    backend = SubversionBackend(wc)
    assert backend.current_branch() == ""  # repository root, no line-of-work segment
    with pytest.raises(VCSError, match="trunk/branches/tags"):
        backend.create_branch("feature")


@svn_required
def test_svn_log_filters(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    assert backend.log().splitlines() == ["r3 add other.txt", "r2 initial commit", "r1 layout"]
    assert backend.log(max_count=1).splitlines() == ["r3 add other.txt"]
    assert backend.log(grep="initial").splitlines() == ["r2 initial commit"]
    assert backend.log(author="bob").splitlines() == ["r3 add other.txt"]
    assert backend.log(grep="other", author="alice") == ""
    assert backend.log(paths=["file.txt"]).splitlines() == ["r2 initial commit"]
    assert backend.log(paths=["file.txt", "other.txt"]).splitlines() == [
        "r3 add other.txt",
        "r2 initial commit",
    ]
    # max_count applies after filtering, not to the raw history window
    assert backend.log(max_count=1, author="alice").splitlines() == ["r2 initial commit"]
    assert backend.log(since="2000-01-01").splitlines()[0] == "r3 add other.txt"


@svn_required
@pytest.mark.parametrize("target", ["pkg", "."])
def test_svn_stage_directory_schedules_nested_deletions(svn_wc: Path, target: str) -> None:
    (svn_wc / "pkg").mkdir()
    (svn_wc / "pkg" / "a.txt").write_text("a\n")
    (svn_wc / "pkg" / "b.txt").write_text("b\n")
    _svn(svn_wc, "add", "pkg")
    _svn(svn_wc, "commit", "-m", "add pkg")
    _svn(svn_wc, "update")
    (svn_wc / "pkg" / "a.txt").unlink()
    (svn_wc / "pkg" / "new.txt").write_text("n\n")
    backend = SubversionBackend(svn_wc)
    backend.stage([target])
    assert sorted(backend.status().splitlines()) == ["A       pkg/new.txt", "D       pkg/a.txt"]
    backend.commit("rework pkg")
    assert backend.is_clean()


@svn_required
def test_svn_stage_keeps_dangling_versioned_symlink(svn_wc: Path) -> None:
    (svn_wc / "link").symlink_to("nowhere")  # dangling from the start
    _svn(svn_wc, "add", "link")
    _svn(svn_wc, "commit", "-m", "add dangling link")
    _svn(svn_wc, "update")
    backend = SubversionBackend(svn_wc)
    backend.stage(["link"])
    assert backend.status() == ""  # not scheduled for deletion
    assert (svn_wc / "link").is_symlink()


@svn_required
def test_svn_diff_base_takes_a_revision(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    (svn_wc / "file.txt").write_text("changed\n")
    assert "+changed" in backend.diff(base="HEAD")
    for name in ("trunk", "main", "branches/fix"):
        with pytest.raises(VCSError, match="takes a revision"):
            backend.diff(base=name)


@svn_required
def test_svn_diff_and_cat(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    (svn_wc / "file.txt").write_text("changed\n")
    working = backend.diff()
    assert "-hello" in working
    assert "+changed" in working
    assert "other.txt" not in working
    assert "+other" in backend.diff(base="2")  # r3 added other.txt after the base
    assert "file.txt" in backend.diff(paths=["file.txt"])
    with pytest.raises(VCSError, match="does not support staging area"):
        backend.diff(cached=True)
    assert backend.cat("2", "file.txt") == "hello\n"


@svn_required
def test_svn_cat_follows_branch_history(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    backend.create_branch("feature")  # r4: copy of trunk@3
    assert backend.cat("2", "file.txt") == "hello\n"  # pre-branch revision, via copy history
    (svn_wc / "file.txt").unlink()
    backend.stage(["file.txt"])
    backend.commit("drop file.txt")  # r5: gone from the working copy
    _svn(svn_wc, "update")
    assert backend.cat("4", "file.txt") == "hello\n"  # deleted path still resolves at an older rev
    assert backend.cat("2", "file.txt") == "hello\n"  # deleted on the branch, pre-branch revision


@svn_required
def test_svn_reset_worktree(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    _svn(svn_wc, "propset", "svn:ignore", "ignored.txt", ".")
    _svn(svn_wc, "commit", "-m", "ignore ignored.txt")
    _svn(svn_wc, "update")
    (svn_wc / "file.txt").write_text("changed\n")
    (svn_wc / "untracked.txt").write_text("u\n")
    (svn_wc / "ignored.txt").write_text("i\n")
    backend.reset_worktree()
    assert backend.is_clean()
    assert (svn_wc / "file.txt").read_text() == "hello\n"
    assert not (svn_wc / "untracked.txt").exists()
    assert (svn_wc / "ignored.txt").exists()  # ignored files are preserved, as with git clean -fd


@svn_required
def test_svn_fetch_leaves_wc_and_push_refuses(svn_wc: Path) -> None:
    backend = SubversionBackend(svn_wc)
    (svn_wc / "file.txt").write_text("changed\n")
    backend.fetch()
    assert (svn_wc / "file.txt").read_text() == "changed\n"
    with pytest.raises(VCSError, match="already published"):
        backend.push("origin", "trunk")


@svn_required
def test_svn_checkout_and_update(svn_wc: Path, tmp_path: Path) -> None:
    url = subprocess.run(
        ["svn", "info", "--show-item", "url"], cwd=svn_wc, check=True, capture_output=True, text=True
    ).stdout.strip()
    second = tmp_path / "second"
    assert main(["--backend", "svn", "-C", str(tmp_path), "checkout", url, "second"]) == 0
    assert (second / "file.txt").read_text() == "hello\n"
    (svn_wc / "file.txt").write_text("from the first copy\n")
    _svn(svn_wc, "commit", "-m", "change file.txt")
    assert main(["-C", str(second), "update"]) == 0
    assert (second / "file.txt").read_text() == "from the first copy\n"
    with pytest.raises(VCSError, match="already exists"):
        SubversionBackend.checkout(url, second)


# -- hg backend operations -------------------------------------------------


@hg_required
def test_hg_clean_then_dirty(hg_repo: Path) -> None:
    backend = MercurialBackend(hg_repo)
    assert backend.is_clean()
    (hg_repo / "file.txt").write_text("changed\n")
    assert not backend.is_clean()
    assert "file.txt" in backend.status()


@hg_required
def test_hg_bookmark_and_commit(hg_repo: Path) -> None:
    backend = MercurialBackend(hg_repo)
    assert backend.current_branch() == "default"
    backend.create_branch("fix-bookmark")
    assert backend.current_branch() == "fix-bookmark"
    (hg_repo / "new.txt").write_text("x\n")
    backend.stage(["new.txt"])
    assert "new.txt" in backend.diff()
    backend.commit("add new.txt")
    assert backend.is_clean()
    assert "add new.txt" in backend.log(max_count=1)


@hg_required
def test_hg_cached_diff_raises(hg_repo: Path) -> None:
    backend = MercurialBackend(hg_repo)
    with pytest.raises(VCSError, match="does not support staging area"):
        backend.diff(cached=True)


@hg_required
def test_hg_reset_worktree(hg_repo: Path) -> None:
    backend = MercurialBackend(hg_repo)
    (hg_repo / ".hgignore").write_text("ignored.txt\n")
    backend.stage([".hgignore"])
    backend.commit("add hgignore")

    (hg_repo / "file.txt").write_text("dirty\n")
    (hg_repo / "untracked.txt").write_text("junk\n")
    (hg_repo / "ignored.txt").write_text("ignored\n")
    backend.reset_worktree()
    assert backend.is_clean()
    assert not (hg_repo / "untracked.txt").exists()
    assert (hg_repo / "file.txt").read_text() == "hello\n"
    assert (hg_repo / "ignored.txt").exists()  # ignored files should be preserved


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
    for name in ("git", "hg", "svn", "fossil"):
        assert name in out


def test_cli_unknown_backend_errors(git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-C", str(git_repo), "--backend", "bzr", "status"]) == 2
    assert "unknown backend" in capsys.readouterr().err


@svn_required
def test_cli_svn_detect_and_status(svn_wc: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-C", str(svn_wc), "detect"]) == 0
    assert capsys.readouterr().out.strip() == "svn"
    assert main(["-C", str(svn_wc), "clean"]) == 0
    (svn_wc / "file.txt").write_text("changed\n")
    assert main(["-C", str(svn_wc), "clean"]) == 1
    assert main(["-C", str(svn_wc), "push", "origin", "trunk"]) == 2
    assert "already published" in capsys.readouterr().err


@git_required
def test_git_checkout_and_update(git_repo: Path, tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    assert main(["--backend", "git", "-C", str(tmp_path), "checkout", str(git_repo), "clone"]) == 0
    assert (clone / "file.txt").read_text() == "hello\n"
    (git_repo / "file.txt").write_text("upstream change\n")
    _git(git_repo, "commit", "-q", "-am", "upstream change")
    assert main(["-C", str(clone), "update"]) == 0
    assert (clone / "file.txt").read_text() == "upstream change\n"


def test_cli_checkout_needs_backend(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-C", str(tmp_path), "checkout", "https://example.org/repo", "dest"]) == 2
    assert "checkout needs --backend" in capsys.readouterr().err


def test_fossil_checkout_unsupported(tmp_path: Path) -> None:
    with pytest.raises(VCSError, match="not supported"):
        FossilBackend.checkout("https://example.org/repo", tmp_path / "dest")


@git_required
def test_cli_cat(git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-C", str(git_repo), "cat", "HEAD", "file.txt"]) == 0
    assert capsys.readouterr().out == "hello\n"


def test_fossil_parser_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_run(args: list[str], cwd: str | None = None, **kwargs: object) -> str:
        if "changes" in args:
            return "EDITED     file1.txt\nADDED      file2.txt\nDELETED    file3.txt\n"
        if "extras" in args:
            return "untracked1.txt\nuntracked2.txt\n"
        return ""

    monkeypatch.setattr("magpie_vcs._run", mock_run)
    backend = FossilBackend(Path("/tmp/repo"))
    status_out = backend.status()
    assert "M file1.txt" in status_out
    assert "A file2.txt" in status_out
    assert "D file3.txt" in status_out
    assert "? untracked1.txt" in status_out
    assert "? untracked2.txt" in status_out


def test_fossil_parser_status_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_run(args: list[str], cwd: str | None = None, **kwargs: object) -> str:
        raise VCSError("command failed")

    monkeypatch.setattr("magpie_vcs._run", mock_run)
    backend = FossilBackend(Path("/tmp/repo"))
    assert backend.status() == ""


def test_fossil_parser_log(monkeypatch: pytest.MonkeyPatch) -> None:
    sample_timeline = """
=== 2026-07-08 ===
17:00:00 [a1b2c3d4e5f6] Initial commit (user: arnav tags: trunk)
16:30:00 [f6e5d4c3b2a1] Fix a bug in forum post rendering (user: jsmith tags: trunk)
16:00:00 [1234567890ab] Add a new feature [options] (user: alice tags: trunk)
"""

    def mock_run(args: list[str], cwd: str | None = None, **kwargs: object) -> str:
        if "timeline" in args:
            return sample_timeline
        return ""

    monkeypatch.setattr("magpie_vcs._run", mock_run)
    backend = FossilBackend(Path("/tmp/repo"))

    # Test basic log
    log_out = backend.log()
    assert "a1b2c3d4e5f6 Initial commit" in log_out
    assert "f6e5d4c3b2a1 Fix a bug in forum post rendering" in log_out
    assert "1234567890ab Add a new feature [options]" in log_out

    # Test grep search
    grep_out = backend.log(grep="bug")
    assert "f6e5d4c3b2a1 Fix a bug in forum post rendering" in grep_out
    assert "a1b2c3d4e5f6" not in grep_out
