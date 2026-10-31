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
    env_file = tmp_path / "env"
    (real / name).write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$@" > {argv}\n'
        f'printf "%s\\n" "${{GIT_CONFIG_COUNT-}}" "${{GIT_CONFIG_KEY_0-}}" '
        f'"${{GIT_CONFIG_VALUE_0-}}" "${{GIT_CONFIG_KEY_1-}}" '
        f'"${{GIT_CONFIG_VALUE_1-}}" > {env_file}\n'
    )
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


def _common_dir(repo: Path) -> str:
    result = subprocess.run(
        ["bash", "-c", 'cd "$(git rev-parse --git-common-dir)" && pwd -P'],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _hooks_env(repo: Path) -> list[str]:
    return ["1", "core.hooksPath", f"{_common_dir(repo)}/hooks", "", ""]


def test_overcommit_install_targets_the_common_hooks_dir(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path, name="overcommit")
    repo = _repo(tmp_path)
    assert _run(env, repo, "--install", name="overcommit").returncode == 0
    assert argv.read_text().splitlines() == ["--install"]
    assert (tmp_path / "env").read_text().splitlines() == _hooks_env(repo)


def test_overcommit_install_help_still_gets_the_override(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path, name="overcommit")
    repo = _repo(tmp_path)
    assert _run(env, repo, "--install", "--help", name="overcommit").returncode == 0
    assert argv.read_text().splitlines() == ["--install", "--help"]
    assert (tmp_path / "env").read_text().splitlines() == _hooks_env(repo)


def test_captainhook_install_targets_the_common_hooks_dir(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    assert _run(env, repo, "install", name="captainhook").returncode == 0
    assert argv.read_text().splitlines() == ["install"]
    assert (tmp_path / "env").read_text().splitlines() == _hooks_env(repo)


def test_captainhook_run_commands_keep_the_override(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    assert _run(env, repo, "hook:pre-commit", name="captainhook").returncode == 0
    assert argv.read_text().splitlines() == ["hook:pre-commit"]
    assert (tmp_path / "env").read_text().splitlines() == _hooks_env(repo)


@pytest.mark.parametrize(
    "args",
    [
        ["-n", "install"],
        ["--ansi", "install"],
        ["inst"],
        ["--configuration=cfg.json", "install"],
    ],
)
def test_captainhook_finds_the_install_behind_options_and_abbreviations(
    tmp_path: Path, args: list[str]
) -> None:
    """A Symfony Console app takes global options before the command and prefixes it."""
    env, argv = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    assert _run(env, repo, *args, name="captainhook").returncode == 0
    assert argv.read_text().splitlines() == args
    assert (tmp_path / "env").read_text().splitlines() == _hooks_env(repo)


def test_hooks_path_env_appends_to_the_callers_git_config(tmp_path: Path) -> None:
    env, _ = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    env.update(
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="alias.captainhook",
        GIT_CONFIG_VALUE_0="status",
    )
    assert _run(env, repo, "install", name="captainhook").returncode == 0
    assert (tmp_path / "env").read_text().splitlines() == [
        "2",
        "alias.captainhook",
        "status",
        "core.hooksPath",
        f"{_common_dir(repo)}/hooks",
    ]


def test_hooks_path_env_install_outside_a_work_tree_passes_through(
    tmp_path: Path,
) -> None:
    env, argv = _setup(tmp_path, name="captainhook")
    outside = tmp_path / "outside"
    outside.mkdir()
    env["GIT_CEILING_DIRECTORIES"] = str(tmp_path)
    assert _run(env, outside, "install", name="captainhook").returncode == 0
    assert argv.read_text().splitlines() == ["install"]
    assert (tmp_path / "env").read_text().splitlines() == ["", "", "", "", ""]


def test_captainhook_falls_back_to_vendor_bin(tmp_path: Path) -> None:
    """A Composer project keeps the binary in vendor/bin, which is not on PATH."""
    env, argv = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    vendored = repo / "vendor" / "bin"
    vendored.mkdir(parents=True)
    (vendored / "captainhook").write_text(
        (tmp_path / "real" / "captainhook").read_text()
    )
    (vendored / "captainhook").chmod(0o755)
    (tmp_path / "real" / "captainhook").unlink()
    subdir = repo / "src"
    subdir.mkdir()
    assert _run(env, subdir, "install", name="captainhook").returncode == 0
    assert argv.read_text().splitlines() == ["install"]
    assert (tmp_path / "env").read_text().splitlines() == _hooks_env(repo)


def _worktree(tmp_path: Path) -> Path:
    """A linked worktree of a repo that has one commit, so `git worktree add` works."""
    repo = _repo(tmp_path)
    # A developer's global commit.gpgsign would make this commit wait for (or
    # fail on) their signing key; the throwaway repo has nothing to sign.
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
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
    return worktree


def test_a_linked_worktree_targets_the_main_checkout(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path)
    worktree = _worktree(tmp_path)
    assert _run(env, worktree, "install").returncode == 0
    assert argv.read_text().splitlines() == [
        "install",
        "--git-dir",
        str((tmp_path / "repo" / ".git").resolve()),
    ]


def test_captainhook_in_a_linked_worktree_targets_the_main_checkout(
    tmp_path: Path,
) -> None:
    env, argv = _setup(tmp_path, name="captainhook")
    worktree = _worktree(tmp_path)
    assert _run(env, worktree, "install", name="captainhook").returncode == 0
    assert argv.read_text().splitlines() == ["install"]
    assert (tmp_path / "env").read_text().splitlines() == _hooks_env(tmp_path / "repo")


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


PLUGIN_COMPOSER = """{
  "require-dev": {
    "captainhook/captainhook": "^5.29",
    "captainhook/hook-installer": "^1.0"
  }
}
"""


@pytest.mark.parametrize("args", [["install"], ["-n", "install"], ["inst"]])
def test_captainhook_warns_when_the_composer_plugin_is_enabled(
    tmp_path: Path, args: list[str]
) -> None:
    env, _ = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    (repo / "composer.json").write_text(PLUGIN_COMPOSER)
    result = _run(env, repo, *args, name="captainhook")
    assert result.returncode == 0
    assert "captainhook/hook-installer is enabled" in result.stderr
    assert "extra.captainhook.disable-plugin" in result.stderr


def test_the_composer_plugin_warning_respects_disable_plugin(
    tmp_path: Path,
) -> None:
    env, _ = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    (repo / "composer.json").write_text(
        """{
  "require-dev": {
    "captainhook/captainhook": "^5.29",
    "captainhook/hook-installer": "^1.0"
  },
  "extra": {"captainhook": {"disable-plugin": true}}
}
"""
    )
    result = _run(env, repo, "install", name="captainhook")
    assert result.returncode == 0
    assert "hook-installer" not in result.stderr


def test_the_composer_plugin_warning_respects_allow_plugins_false(
    tmp_path: Path,
) -> None:
    env, _ = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    (repo / "composer.json").write_text(
        """{
  "require-dev": {
    "captainhook/captainhook": "^5.29",
    "captainhook/hook-installer": "^1.0"
  },
  "config": {"allow-plugins": {"captainhook/hook-installer": false}}
}
"""
    )
    result = _run(env, repo, "install", name="captainhook")
    assert result.returncode == 0
    assert "hook-installer" not in result.stderr


def test_the_composer_plugin_warning_stays_off_run_commands(
    tmp_path: Path,
) -> None:
    """The installed hook runs on every commit; a warning there would be noise."""
    env, _ = _setup(tmp_path, name="captainhook")
    repo = _repo(tmp_path)
    (repo / "composer.json").write_text(PLUGIN_COMPOSER)
    result = _run(env, repo, "hook:pre-commit", name="captainhook")
    assert result.returncode == 0
    assert "hook-installer" not in result.stderr
