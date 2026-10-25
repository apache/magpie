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

"""The whole-user dispatcher chains to each repository's own hook."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

DISPATCHER = Path(__file__).parent.parent / "git-hook-dispatcher.sh"


def _repo_with_local_hook(
    tmp_path: Path, config: str | None = ".pre-commit-config.yaml"
) -> tuple[Path, Path, Path]:
    """A repository whose own pre-commit records the PREK_HOME it was given.

    `config` is the hook-manager config at its root, or None for a repository
    that has none. The paths stay free of the hook marker ("prek"), so only
    `config` or an explicit hook body makes the repository a prek user.
    """
    tmp_path = tmp_path / "t"
    tmp_path.mkdir()
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    if config is not None:
        (repo / config).write_text("repos: []\n")
    seen = tmp_path / "seen"
    local = repo / ".git" / "hooks" / "pre-commit"
    local.write_text(
        f'#!/bin/sh\nprintf "%s" "${{PREK_HOME-<unset>}}" > {seen}\n'
        f'printf "%s" "${{XDG_CACHE_HOME-<unset>}}" > {seen}.xdg\n'
    )
    local.chmod(0o755)
    hooks = tmp_path / "global-hooks"
    hooks.mkdir()
    (hooks / "pre-commit").symlink_to(DISPATCHER)
    return repo, hooks / "pre-commit", seen


def _run(repo: Path, hook: Path, env_extra: dict[str, str]) -> None:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PREK_HOME", "SANDBOX_RUNTIME", "XDG_CACHE_HOME")
    }
    env.update(env_extra)
    subprocess.run(["bash", str(hook)], cwd=repo, env=env, check=True)


HOST_HOME = "{home}/.local/share/prek-host"


@pytest.mark.parametrize(
    "given", [None, "~/.cache/prek", "{home}/.cache/prek", "{home}/.cache/prek-sandbox"]
)
def test_outside_the_sandbox_prek_gets_the_host_home(
    tmp_path: Path, given: str | None
) -> None:
    """A terminal or bypassed commit must not run environments the sandbox could write."""
    repo, hook, seen = _repo_with_local_hook(tmp_path)
    home = os.environ["HOME"]
    _run(repo, hook, {} if given is None else {"PREK_HOME": given.format(home=home)})
    assert seen.read_text() == HOST_HOME.format(home=home)


@pytest.mark.parametrize("given", [None, "~/.cache/prek"])
def test_inside_the_sandbox_prek_keeps_its_home(
    tmp_path: Path, given: str | None
) -> None:
    repo, hook, seen = _repo_with_local_hook(tmp_path)
    env = {"SANDBOX_RUNTIME": "1"} | ({} if given is None else {"PREK_HOME": given})
    _run(repo, hook, env)
    assert seen.read_text() == ("<unset>" if given is None else given)


def test_an_operator_prek_home_outside_the_cache_is_left_alone(tmp_path: Path) -> None:
    repo, hook, seen = _repo_with_local_hook(tmp_path)
    _run(repo, hook, {"PREK_HOME": "/opt/prek-home"})
    assert seen.read_text() == "/opt/prek-home"


def test_a_repository_without_its_own_hook_is_a_no_op(tmp_path: Path) -> None:
    repo, hook, seen = _repo_with_local_hook(tmp_path)
    (repo / ".git" / "hooks" / "pre-commit").unlink()
    _run(repo, hook, {})
    assert not seen.exists()


@pytest.mark.parametrize("given", [None, "{home}/.cache"])
def test_outside_the_sandbox_tool_caches_move_too(
    tmp_path: Path, given: str | None
) -> None:
    """pip, go, npm and uv caches under ~/.cache would be sandbox-written too."""
    repo, hook, seen = _repo_with_local_hook(tmp_path)
    home = os.environ["HOME"]
    env = {} if given is None else {"XDG_CACHE_HOME": given.format(home=home)}
    _run(repo, hook, env)
    assert Path(f"{seen}.xdg").read_text() == f"{home}/.local/share/prek-host/cache"


def test_inside_the_sandbox_tool_caches_stay(tmp_path: Path) -> None:
    repo, hook, seen = _repo_with_local_hook(tmp_path)
    _run(repo, hook, {"SANDBOX_RUNTIME": "1"})
    assert Path(f"{seen}.xdg").read_text() == "<unset>"


@pytest.fixture
def marker_free_tmp(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A temporary directory whose path does not contain the hook marker."""
    path = tmp_path_factory.mktemp("dispatch")
    assert "prek" not in str(path)
    return path


@pytest.mark.parametrize(
    "config", ["prek.toml", ".pre-commit-config.yaml", ".pre-commit-config.yml"]
)
def test_each_config_file_makes_the_repository_a_user(
    marker_free_tmp: Path, config: str
) -> None:
    repo, hook, seen = _repo_with_local_hook(marker_free_tmp, config=config)
    _run(repo, hook, {})
    assert seen.read_text() == HOST_HOME.format(home=os.environ["HOME"])


def test_a_repository_without_the_manager_gets_no_home(marker_free_tmp: Path) -> None:
    """Only a repository that uses a hook manager gets that manager's home."""
    repo, hook, seen = _repo_with_local_hook(marker_free_tmp, config=None)
    _run(repo, hook, {})
    assert seen.read_text() == "<unset>"
    # The tool caches move whatever runs the hook.
    assert (
        Path(f"{seen}.xdg").read_text()
        == f"{os.environ['HOME']}/.local/share/prek-host/cache"
    )


def test_a_hook_that_runs_the_manager_makes_the_repository_a_user(
    marker_free_tmp: Path,
) -> None:
    """An install with a custom --config, or from a nested workspace project."""
    repo, hook, seen = _repo_with_local_hook(marker_free_tmp, config=None)
    local = repo / ".git" / "hooks" / "pre-commit"
    local.write_text(
        local.read_text() + "# exec prek hook-impl --config=ci/hooks.yaml\n"
    )
    _run(repo, hook, {})
    assert seen.read_text() == HOST_HOME.format(home=os.environ["HOME"])
