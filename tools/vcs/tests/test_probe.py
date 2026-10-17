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

"""Tests for ``magpie-vcs probe``: is the project Subversion-hosted, and where."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from magpie_vcs import GitBackend, SubversionBackend, main, probe

for _var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX"):
    os.environ.pop(_var, None)

git_required = pytest.mark.skipif(not GitBackend.is_available(), reason="git not installed")
svn_required = pytest.mark.skipif(
    not SubversionBackend.is_available() or shutil.which("svnadmin") is None,
    reason="svn 1.9+ / svnadmin not installed",
)

ASF_ROOT = "https://svn.apache.org/repos/asf"
ASF_UUID = "13f79535-47bb-0310-9956-ffa450edef68"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _git_repo(path: Path, message: str = "initial commit") -> Path:
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Tester")
    _git(path, "config", "commit.gpgsign", "false")
    (path / "file.txt").write_text("hello\n")
    _git(path, "add", "file.txt")
    _git(path, "commit", "-q", "-m", message)
    return path


def _fake_wc(path: Path, root: str, repos_path: str) -> Path:
    """An svn working copy reduced to the two wc.db tables `probe` reads."""
    (path / ".svn").mkdir(parents=True)
    con = sqlite3.connect(path / ".svn" / "wc.db")
    con.execute("CREATE TABLE repository (id INTEGER PRIMARY KEY, root TEXT, uuid TEXT)")
    con.execute(
        "CREATE TABLE nodes (local_relpath TEXT, op_depth INTEGER, repos_id INTEGER, repos_path TEXT)"
    )
    con.execute("INSERT INTO repository VALUES (1, ?, ?)", (root, ASF_UUID))
    con.execute("INSERT INTO nodes VALUES ('', 0, 1, ?)", (repos_path,))
    con.execute("INSERT INTO nodes VALUES ('sub', 0, 1, ?)", (f"{repos_path}/sub",))
    con.commit()
    con.close()
    return path


def _notes(result: dict[str, object]) -> list[str]:
    notes = result["notes"]
    assert isinstance(notes, list)
    return [str(n) for n in notes]


@pytest.fixture
def no_svn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SubversionBackend, "is_available", classmethod(lambda cls: False))


# -- svn working copy --------------------------------------------------------


def test_svn_wc_read_from_wc_db(tmp_path: Path, no_svn: None) -> None:
    wc = _fake_wc(tmp_path / "wc", ASF_ROOT, "foo/trunk")
    (wc / "sub").mkdir()
    result = probe(wc / "sub")  # from a subdirectory: the root's metadata is read
    assert result["kind"] == "svn-working-copy"
    assert result["svn_hosted"] is True
    assert result["root"] == str(wc)
    assert result["svn"] == {
        "url": f"{ASF_ROOT}/foo/trunk",
        "repository_root": ASF_ROOT,
        "project_url": f"{ASF_ROOT}/foo",
        "line_of_work": "trunk",
        "layout": "trunk/branches/tags",
        "uuid": ASF_UUID,
        "source": ".svn/wc.db",
    }
    assert result["proposal"] == {
        "vcs_backend": "svn",
        "svn_url": f"{ASF_ROOT}/foo",
        "svn_repository_root": ASF_ROOT,
        "upstream_default_branch": "trunk",
    }


def test_svn_wc_branch_with_space_is_quoted(tmp_path: Path, no_svn: None) -> None:
    wc = _fake_wc(tmp_path / "wc", ASF_ROOT, "foo/branches/my fix")
    svn = probe(wc)["svn"]
    assert isinstance(svn, dict)
    assert svn["url"] == f"{ASF_ROOT}/foo/branches/my%20fix"
    assert svn["line_of_work"] == "branches/my fix"
    assert svn["project_url"] == f"{ASF_ROOT}/foo"


def test_svn_wc_outside_standard_layout(tmp_path: Path, no_svn: None) -> None:
    wc = _fake_wc(tmp_path / "wc", ASF_ROOT, "foo/site")
    result = probe(wc)
    assert result["svn_hosted"] is True
    svn = result["svn"]
    assert isinstance(svn, dict)
    assert svn["layout"] == "other"
    assert svn["line_of_work"] is None
    assert result["proposal"] == {
        "vcs_backend": "svn",
        "svn_url": f"{ASF_ROOT}/foo/site",
        "svn_repository_root": ASF_ROOT,
        "upstream_default_branch": None,
    }
    assert any("not under a trunk/branches/tags layout" in n for n in _notes(result))


def test_svn_wc_unreadable_metadata(tmp_path: Path, no_svn: None) -> None:
    (tmp_path / "wc" / ".svn").mkdir(parents=True)
    result = probe(tmp_path / "wc")
    assert result["kind"] == "svn-working-copy"
    assert result["svn"] is None
    assert result["proposal"] == {
        "vcs_backend": "svn",
        "svn_url": None,
        "svn_repository_root": None,
        "upstream_default_branch": None,
    }


@svn_required
def test_svn_wc_real_checkout(tmp_path: Path) -> None:
    repos = tmp_path / "svnrepo"
    subprocess.run(["svnadmin", "create", str(repos)], check=True, capture_output=True)
    url = repos.as_uri()
    subprocess.run(
        [
            "svn",
            "--non-interactive",
            "mkdir",
            "--parents",
            "-m",
            "layout",
            f"{url}/proj/trunk",
            f"{url}/proj/tags",
        ],
        check=True,
        capture_output=True,
    )
    wc = tmp_path / "wc"
    subprocess.run(
        ["svn", "--non-interactive", "checkout", f"{url}/proj/trunk", str(wc)],
        check=True,
        capture_output=True,
    )
    result = probe(wc)
    svn = result["svn"]
    assert isinstance(svn, dict)
    assert svn["source"] in ("svn info", ".svn/wc.db")
    assert svn["line_of_work"] == "trunk"
    assert str(svn["project_url"]).endswith("/svnrepo/proj")
    assert result["proposal"] is not None


# -- git checkouts -----------------------------------------------------------


@git_required
def test_plain_git_is_not_svn_hosted(tmp_path: Path) -> None:
    result = probe(_git_repo(tmp_path / "repo"))
    assert result["kind"] == "git"
    assert result["svn_hosted"] is False
    assert result["svn"] is None
    assert result["proposal"] is None


@git_required
def test_git_svn_clone(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    _git(repo, "config", "svn-remote.svn.url", f"{ASF_ROOT}/foo")
    _git(repo, "config", "svn-remote.svn.fetch", "trunk:refs/remotes/origin/trunk")
    _git(repo, "config", "svn-remote.svn.branches", "branches/*:refs/remotes/origin/*")
    metadata = repo / ".git" / "svn" / ".metadata"
    metadata.parent.mkdir()
    _git(repo, "config", "-f", str(metadata), "svn-remote.svn.reposRoot", ASF_ROOT)
    _git(repo, "config", "-f", str(metadata), "svn-remote.svn.uuid", ASF_UUID)
    result = probe(repo)
    assert result["kind"] == "git-svn-clone"
    assert result["backend"] == "git"
    assert result["svn_hosted"] is True
    svn = result["svn"]
    assert isinstance(svn, dict)
    assert svn["url"] == f"{ASF_ROOT}/foo/trunk"
    assert svn["repository_root"] == ASF_ROOT
    assert svn["uuid"] == ASF_UUID
    assert result["proposal"] == {
        "vcs_backend": "svn",
        "svn_url": f"{ASF_ROOT}/foo",
        "svn_repository_root": ASF_ROOT,
        "upstream_default_branch": "trunk",
    }
    assert any("cannot commit to Subversion" in n for n in _notes(result))


@git_required
def test_git_svn_clone_before_first_fetch(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    _git(repo, "config", "svn-remote.svn.url", ASF_ROOT)
    _git(repo, "config", "svn-remote.svn.fetch", "foo/trunk:refs/remotes/trunk")
    result = probe(repo)
    svn = result["svn"]
    assert isinstance(svn, dict)
    assert svn["repository_root"] is None
    assert svn["project_url"] == f"{ASF_ROOT}/foo"
    assert any(".metadata" in n for n in _notes(result))


@git_required
def test_git_svn_mirror(tmp_path: Path) -> None:
    message = f"Fix the widget.\n\ngit-svn-id: {ASF_ROOT}/foo/trunk@1912345 {ASF_UUID}\n"
    result = probe(_git_repo(tmp_path / "repo", message))
    assert result["kind"] == "git-svn-mirror"
    assert result["svn_hosted"] is True
    svn = result["svn"]
    assert isinstance(svn, dict)
    assert svn["source"] == "git-svn-id"
    assert svn["repository_root"] is None
    assert svn["project_url"] == f"{ASF_ROOT}/foo"
    assert result["proposal"] == {
        "vcs_backend": "svn",
        "svn_url": f"{ASF_ROOT}/foo",
        "svn_repository_root": None,
        "upstream_default_branch": "trunk",
    }


@git_required
def test_git_migrated_from_svn_is_git(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo", f"Old.\n\ngit-svn-id: {ASF_ROOT}/foo/trunk@1 {ASF_UUID}\n")
    (repo / "file.txt").write_text("new\n")
    _git(repo, "commit", "-q", "-am", "first commit after the migration")
    result = probe(repo)
    assert result["kind"] == "git"
    assert result["proposal"] is None


# -- neither -----------------------------------------------------------------


def test_no_working_copy(tmp_path: Path) -> None:
    result = probe(tmp_path)
    assert result["kind"] == "none"
    assert result["backend"] is None
    assert result["svn_hosted"] is False
    assert result["proposal"] is None


def test_cli_probe_prints_json(tmp_path: Path, no_svn: None, capsys: pytest.CaptureFixture[str]) -> None:
    wc = _fake_wc(tmp_path / "wc", ASF_ROOT, "foo/trunk")
    assert main(["-C", str(wc), "probe"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kind"] == "svn-working-copy"
    assert out["proposal"]["svn_url"] == f"{ASF_ROOT}/foo"
