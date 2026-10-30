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

"""The hook-manager shim puts a manager's hook in the repository's own hooks dir."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SHIM = Path(__file__).parent.parent / "hook-manager-shim.sh"


def _setup(tmp_path: Path, name: str = "prek") -> tuple[dict[str, str], Path]:
    """A fake real `name` that records its argv, behind the shim installed as `name`."""
    real = tmp_path / "real"
    real.mkdir()
    argv = tmp_path / "argv"
    (real / name).write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {argv}\n')
    (real / name).chmod(0o755)
    shims = tmp_path / "shims"
    shims.mkdir()
    (shims / name).symlink_to(SHIM)
    env = dict(os.environ, PATH=f"{shims}:{real}:/usr/bin:/bin")
    return env, argv


def _run(
    env: dict[str, str], cwd: Path, *args: str, name: str = "prek"
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [name, *args], cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def test_install_targets_the_common_git_dir(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path)
    repo = _repo(tmp_path)
    assert _run(env, repo, "install", "-t", "pre-push").returncode == 0
    git_dir = str((repo / ".git").resolve())
    assert argv.read_text().splitlines() == [
        "install",
        "--git-dir",
        git_dir,
        "-t",
        "pre-push",
    ]


def test_a_linked_worktree_targets_the_main_checkout(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path)
    repo = _repo(tmp_path)
    # A developer's global commit.gpgsign would make this commit wait for (or
    # fail on) their signing key; the throwaway repo has nothing to sign.
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "x"],
        check=True,
        env=dict(
            os.environ,
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@t",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@t",
        ),
    )
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(worktree)], check=True
    )
    assert _run(env, worktree, "install").returncode == 0
    assert argv.read_text().splitlines() == [
        "install",
        "--git-dir",
        str((repo / ".git").resolve()),
    ]


@pytest.mark.parametrize(
    "args",
    [
        ["install", "--git-dir", "/x"],
        ["install", "--git-dir=/x"],
        ["install", "--help"],
        ["run", "--all-files"],
        ["--version"],
    ],
)
def test_other_invocations_pass_through(tmp_path: Path, args: list[str]) -> None:
    env, argv = _setup(tmp_path)
    assert _run(env, _repo(tmp_path), *args).returncode == 0
    assert argv.read_text().splitlines() == args


def test_install_outside_a_work_tree_passes_through(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    env["GIT_CEILING_DIRECTORIES"] = str(tmp_path)
    assert _run(env, outside, "install").returncode == 0
    assert argv.read_text().splitlines() == ["install"]


def test_a_name_without_an_adapter_is_refused(tmp_path: Path) -> None:
    env, _ = _setup(tmp_path, name="not-a-hook-manager")
    result = _run(env, tmp_path, "install", name="not-a-hook-manager")
    assert result.returncode == 127
    assert "no adapter" in result.stderr


def test_a_missing_real_binary_is_reported(tmp_path: Path) -> None:
    env, _ = _setup(tmp_path)
    (tmp_path / "real" / "prek").unlink()
    result = _run(env, tmp_path, "run")
    assert result.returncode == 127
    assert "could not locate the real 'prek'" in result.stderr
