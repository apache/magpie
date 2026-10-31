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
        f'printf "%s\\n" "${{GIT_CONFIG_COUNT-}}" '
        f'"${{GIT_CONFIG_KEY_0-}}" "${{GIT_CONFIG_VALUE_0-}}" '
        f'"${{GIT_CONFIG_KEY_1-}}" "${{GIT_CONFIG_VALUE_1-}}" > {env_file}\n'
    )
    (real / name).chmod(0o755)
    shims = tmp_path / "shims"
    shims.mkdir()
    (shims / name).symlink_to(SHIM)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_CONFIG_")
    }
    env["PATH"] = f"{shims}:{real}:/usr/bin:/bin"
    return env, argv


def _setup_lefthook(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    """A fake lefthook that refuses while a global core.hooksPath is visible.

    It records the global config it was given, then installs a hook where
    `git rev-parse --git-path hooks` resolves, as lefthook does.
    """
    real = tmp_path / "real"
    real.mkdir()
    record = tmp_path / "record"
    shared = tmp_path / "shared-hooks"
    (real / "lefthook").write_text(
        "#!/bin/sh\n"
        f'printf "GIT_CONFIG_GLOBAL=%s\\n" "${{GIT_CONFIG_GLOBAL-<unset>}}" > {record}\n'
        f'printf "%s\\n" "$@" >> {record}\n'
        'for arg in "$@"; do\n'
        '  case "$arg" in -h|--help) exit 0 ;; esac\n'
        "done\n"
        'if [ "$1" = install ]; then\n'
        '  if [ "${GIT_CONFIG_GLOBAL-}" != /dev/null ] '
        '&& [ -n "$(git config --global --get core.hooksPath 2>/dev/null)" ]; then\n'
        '    echo "core.hooksPath is set globally" >&2\n'
        "    exit 1\n"
        "  fi\n"
        '  hooks="$(git rev-parse --path-format=absolute --git-path hooks)"\n'
        '  mkdir -p "$hooks" && printf "#!/bin/sh\\n" > "$hooks/pre-commit"\n'
        "fi\n"
    )
    (real / "lefthook").chmod(0o755)
    shims = tmp_path / "shims"
    shims.mkdir()
    (shims / "lefthook").symlink_to(SHIM)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text(f"[core]\n\thooksPath = {shared}\n")
    env = dict(os.environ)
    for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"):
        env.pop(name, None)
    env.update(PATH=f"{shims}:{real}:/usr/bin:/bin", HOME=str(home), GIT_CONFIG_NOSYSTEM="1")
    return env, record, shared


def _set_global_hooks_path(env: dict[str, str], value: str | None) -> None:
    """Rewrite the fake home's global config: a `core.hooksPath`, or none."""
    (Path(env["HOME"]) / ".gitconfig").write_text(
        f"[core]\n\thooksPath = {value}\n" if value else "[user]\n\tname = t\n"
    )


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


def test_overcommit_install_targets_the_common_hooks_dir(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path, name="overcommit")
    repo = _repo(tmp_path)
    assert _run(env, repo, "--install", name="overcommit").returncode == 0
    assert argv.read_text().splitlines() == ["--install"]
    assert (tmp_path / "env").read_text().splitlines() == [
        "1",
        "core.hooksPath",
        f"{_common_dir(repo)}/hooks",
        "",
        "",
    ]


def test_overcommit_install_help_passes_through(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path, name="overcommit")
    assert (
        _run(env, _repo(tmp_path), "--install", "--help", name="overcommit").returncode
        == 0
    )
    assert argv.read_text().splitlines() == ["--install", "--help"]
    assert (tmp_path / "env").read_text().splitlines() == ["", "", "", "", ""]


@pytest.mark.parametrize(
    "args",
    [
        ["-i"],
        ["--force", "--install"],
        ["--force", "-i"],
        ["-fi"],
        ["--i"],
        ["--inst"],
        ["--force", "--insta"],
    ],
)
def test_overcommit_install_flag_is_found_anywhere(
    tmp_path: Path, args: list[str]
) -> None:
    env, argv = _setup(tmp_path, name="overcommit")
    repo = _repo(tmp_path)
    assert _run(env, repo, *args, name="overcommit").returncode == 0
    assert argv.read_text().splitlines() == args
    assert (tmp_path / "env").read_text().splitlines() == [
        "1",
        "core.hooksPath",
        f"{_common_dir(repo)}/hooks",
        "",
        "",
    ]


@pytest.mark.parametrize("args", [["--run"], ["--uninstall"], ["--"]])
def test_overcommit_other_actions_pass_through(tmp_path: Path, args: list[str]) -> None:
    env, argv = _setup(tmp_path, name="overcommit")
    repo = _repo(tmp_path)
    assert _run(env, repo, *args, name="overcommit").returncode == 0
    assert argv.read_text().splitlines() == args
    assert (tmp_path / "env").read_text().splitlines() == ["", "", "", "", ""]


def test_overcommit_install_preserves_existing_git_config(tmp_path: Path) -> None:
    env, _ = _setup(tmp_path, name="overcommit")
    repo = _repo(tmp_path)
    env.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "user.name",
            "GIT_CONFIG_VALUE_0": "Someone",
        }
    )
    assert _run(env, repo, "--install", name="overcommit").returncode == 0
    assert (tmp_path / "env").read_text().splitlines() == [
        "2",
        "user.name",
        "Someone",
        "core.hooksPath",
        f"{_common_dir(repo)}/hooks",
    ]


def test_a_linked_worktree_targets_the_main_checkout(tmp_path: Path) -> None:
    env, argv = _setup(tmp_path)
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
    assert _run(env, worktree, "install").returncode == 0
    assert argv.read_text().splitlines() == [
        "install",
        "--git-dir",
        str((repo / ".git").resolve()),
    ]


def test_lefthook_install_hides_the_global_hooks_path(tmp_path: Path) -> None:
    env, record, shared = _setup_lefthook(tmp_path)
    repo = _repo(tmp_path)
    assert _run(env, repo, "install", name="lefthook").returncode == 0
    assert record.read_text().splitlines() == ["GIT_CONFIG_GLOBAL=/dev/null", "install"]
    assert (repo / ".git" / "hooks" / "pre-commit").is_file()
    assert not (shared / "pre-commit").exists()


def test_lefthook_install_hides_a_custom_global_hooks_path(tmp_path: Path) -> None:
    env, record, _shared = _setup_lefthook(tmp_path)
    other = tmp_path / "other-hooks"
    _set_global_hooks_path(env, str(other))
    repo = _repo(tmp_path)
    assert _run(env, repo, "install", name="lefthook").returncode == 0
    assert record.read_text().splitlines() == ["GIT_CONFIG_GLOBAL=/dev/null", "install"]
    assert (repo / ".git" / "hooks" / "pre-commit").is_file()
    assert not (other / "pre-commit").exists()


def test_lefthook_install_without_a_global_hooks_path_keeps_the_global_config(
    tmp_path: Path,
) -> None:
    env, record, _shared = _setup_lefthook(tmp_path)
    _set_global_hooks_path(env, None)
    repo = _repo(tmp_path)
    assert _run(env, repo, "install", name="lefthook").returncode == 0
    assert record.read_text().splitlines() == ["GIT_CONFIG_GLOBAL=<unset>", "install"]
    assert (repo / ".git" / "hooks" / "pre-commit").is_file()


def test_lefthook_install_in_a_linked_worktree_targets_the_main_checkout(
    tmp_path: Path,
) -> None:
    env, record, _shared = _setup_lefthook(tmp_path)
    repo = _repo(tmp_path)
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
    assert _run(env, worktree, "install", name="lefthook").returncode == 0
    assert record.read_text().splitlines()[0] == "GIT_CONFIG_GLOBAL=/dev/null"
    assert (repo / ".git" / "hooks" / "pre-commit").is_file()


@pytest.mark.parametrize(
    "args",
    [
        ["install", "--force"],
        ["install", "-f"],
        ["install", "--reset-hooks-path"],
        ["install", "-r"],
        ["install", "-fr"],
    ],
)
def test_lefthook_destructive_flags_cannot_reach_the_global_dir(
    tmp_path: Path, args: list[str]
) -> None:
    env, record, shared = _setup_lefthook(tmp_path)
    repo = _repo(tmp_path)
    assert _run(env, repo, *args, name="lefthook").returncode == 0
    assert record.read_text().splitlines()[0] == "GIT_CONFIG_GLOBAL=/dev/null"
    assert (repo / ".git" / "hooks" / "pre-commit").is_file()
    assert not (shared / "pre-commit").exists()


def test_lefthook_other_invocations_pass_through(tmp_path: Path) -> None:
    env, record, _shared = _setup_lefthook(tmp_path)
    assert (
        _run(env, _repo(tmp_path), "run", "pre-commit", name="lefthook").returncode == 0
    )
    assert record.read_text().splitlines() == [
        "GIT_CONFIG_GLOBAL=<unset>",
        "run",
        "pre-commit",
    ]


@pytest.mark.parametrize("help_flag", ["-h", "--help"])
def test_lefthook_help_passes_through(tmp_path: Path, help_flag: str) -> None:
    env, record, _shared = _setup_lefthook(tmp_path)
    assert (
        _run(env, _repo(tmp_path), "install", help_flag, name="lefthook").returncode == 0
    )
    assert record.read_text().splitlines() == [
        "GIT_CONFIG_GLOBAL=<unset>",
        "install",
        help_flag,
    ]


def test_lefthook_install_outside_a_work_tree_passes_through(tmp_path: Path) -> None:
    env, record, _shared = _setup_lefthook(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    env["GIT_CEILING_DIRECTORIES"] = str(tmp_path)
    assert _run(env, outside, "install", name="lefthook").returncode == 1
    assert record.read_text().splitlines() == ["GIT_CONFIG_GLOBAL=<unset>", "install"]


@pytest.mark.parametrize(
    "args",
    [
        ["install", "--git-dir", "/x"],
        ["install", "--git-dir=/x"],
        ["install", "--help"],
        ["run", "--all-files"],
        ["run", "install"],
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
