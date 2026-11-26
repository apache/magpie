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

"""Tests for sandbox-add-project-root.sh.

The script adds the current git worktree path to the project-local
.claude/settings.local.json allowlists.  Tests use a temporary git repo
with settings.local.json gitignored so the safety check passes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "sandbox-add-project-root.sh"

# Use the absolute path so tests that restrict PATH still launch bash correctly.
BASH = shutil.which("bash") or "/bin/bash"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_git_repo(tmp_path: Path) -> Path:
    """Return an initialised git repo with settings.local.json gitignored."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    # Write .gitignore so the safety check in the script passes.
    (repo / ".gitignore").write_text("/.claude/settings.local.json\n")
    return repo


def _run(
    cwd: Path, args: list | None = None, extra_env: dict | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [BASH, str(SCRIPT)] + (args or []),
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )


def _load(settings_file: Path) -> dict:
    return json.loads(settings_file.read_text())


# ---------------------------------------------------------------------------
# basic creation
# ---------------------------------------------------------------------------


class TestBasicCreation:
    def test_creates_settings_file(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        result = _run(repo)
        assert result.returncode == 0
        assert (repo / ".claude" / "settings.local.json").exists()

    def test_allow_read_contains_repo_root(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _run(repo)
        data = _load(repo / ".claude" / "settings.local.json")
        assert str(repo) in data["sandbox"]["filesystem"]["allowRead"]

    def test_allow_write_contains_repo_root(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _run(repo)
        data = _load(repo / ".claude" / "settings.local.json")
        assert str(repo) in data["sandbox"]["filesystem"]["allowWrite"]

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _run(repo)
        content = (repo / ".claude" / "settings.local.json").read_text()
        parsed = json.loads(content)  # raises if invalid
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# idempotence
# ---------------------------------------------------------------------------


class TestIdempotence:
    def test_second_run_no_duplicates_in_read(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _run(repo)
        _run(repo)
        data = _load(repo / ".claude" / "settings.local.json")
        read_paths = data["sandbox"]["filesystem"]["allowRead"]
        assert read_paths.count(str(repo)) == 1

    def test_second_run_no_duplicates_in_write(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _run(repo)
        _run(repo)
        data = _load(repo / ".claude" / "settings.local.json")
        write_paths = data["sandbox"]["filesystem"]["allowWrite"]
        assert write_paths.count(str(repo)) == 1

    def test_second_run_exit_zero(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _run(repo)
        result = _run(repo)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# merge with existing content
# ---------------------------------------------------------------------------


class TestMerge:
    def test_preserves_existing_read_paths(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        claude_dir = repo / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        existing = {"sandbox": {"filesystem": {"allowRead": ["/some/other/path"]}}}
        (claude_dir / "settings.local.json").write_text(json.dumps(existing))
        _run(repo)
        data = _load(claude_dir / "settings.local.json")
        read_paths = data["sandbox"]["filesystem"]["allowRead"]
        assert "/some/other/path" in read_paths

    def test_adds_repo_root_to_existing_content(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        claude_dir = repo / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        existing = {
            "sandbox": {"filesystem": {"allowRead": ["/other"]}},
            "someKey": "someValue",
        }
        (claude_dir / "settings.local.json").write_text(json.dumps(existing))
        _run(repo)
        data = _load(claude_dir / "settings.local.json")
        assert str(repo) in data["sandbox"]["filesystem"]["allowRead"]
        assert data.get("someKey") == "someValue"  # non-sandbox keys untouched


# ---------------------------------------------------------------------------
# dev-tool paths under $HOME
# ---------------------------------------------------------------------------


def _tool_reads(home: Path) -> list[str]:
    return [
        str(home / p)
        for p in (
            ".gitconfig",
            ".config/git",
            ".cache",
            ".local/share/uv",
            ".local/bin",
        )
    ]


def _tool_writes(home: Path) -> list[str]:
    # Never ~/.local/share/uv: its interpreters and tool venvs run outside the sandbox.
    return [str(home / ".cache")]


class TestToolPaths:
    def test_adds_tool_read_paths(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, extra_env={"HOME": str(home)})
        read_paths = _load(repo / ".claude" / "settings.local.json")["sandbox"][
            "filesystem"
        ]["allowRead"]
        for path in _tool_reads(home):
            assert path in read_paths

    def test_adds_tool_write_paths(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, extra_env={"HOME": str(home)})
        write_paths = _load(repo / ".claude" / "settings.local.json")["sandbox"][
            "filesystem"
        ]["allowWrite"]
        assert write_paths == [str(repo)] + _tool_writes(home)

    def test_never_adds_credential_paths(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, extra_env={"HOME": str(home)})
        data = _load(repo / ".claude" / "settings.local.json")["sandbox"]["filesystem"]
        for path in data["allowRead"] + data["allowWrite"]:
            for secret in (".config/gh", ".config/apache-magpie", ".gnupg", ".ssh"):
                assert secret not in path

    def test_second_run_no_duplicate_tool_paths(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, extra_env={"HOME": str(home)})
        _run(repo, extra_env={"HOME": str(home)})
        data = _load(repo / ".claude" / "settings.local.json")["sandbox"]["filesystem"]
        assert len(data["allowRead"]) == len(set(data["allowRead"]))
        assert len(data["allowWrite"]) == len(set(data["allowWrite"]))

    def test_adds_only_missing_tool_paths(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        cache = str(home / ".cache")
        _seed_settings(
            repo,
            {"sandbox": {"filesystem": {"allowRead": [cache], "allowWrite": [cache]}}},
        )
        _run(repo, extra_env={"HOME": str(home)})
        data = _load(repo / ".claude" / "settings.local.json")["sandbox"]["filesystem"]
        assert data["allowRead"].count(cache) == 1
        assert data["allowWrite"].count(cache) == 1
        assert data["allowRead"][0] == cache  # existing entries keep their place

    def test_removes_the_uv_data_dir_write_an_earlier_version_added(
        self, tmp_path: Path
    ) -> None:
        """Hooks, MCP servers and excluded uv commands run its interpreters unsandboxed."""
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        uv = str(home / ".local" / "share" / "uv")
        stale = [uv, uv + "/", "~/.local/share/uv", "~/.local/share/uv/"]
        _seed_settings(
            repo,
            {
                "sandbox": {
                    "filesystem": {
                        "allowRead": [uv],
                        "allowWrite": ["/opt/data", *stale],
                    }
                }
            },
        )
        _run(repo, extra_env={"HOME": str(home)})
        data = _load(repo / ".claude" / "settings.local.json")["sandbox"]["filesystem"]
        assert not set(stale) & set(data["allowWrite"])
        assert "/opt/data" in data["allowWrite"]
        assert uv in data["allowRead"]  # reading it stays allowed

    def test_removes_the_uv_data_dir_write_even_without_tool_paths(
        self, tmp_path: Path
    ) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        uv = str(home / ".local" / "share" / "uv")
        _seed_settings(repo, {"sandbox": {"filesystem": {"allowWrite": [uv]}}})
        _run(repo, args=["--no-tool-paths"], extra_env={"HOME": str(home)})
        assert (
            uv
            not in _load(repo / ".claude" / "settings.local.json")["sandbox"][
                "filesystem"
            ]["allowWrite"]
        )

    def test_no_tool_paths_flag_adds_project_root_only(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, args=["--no-tool-paths"], extra_env={"HOME": str(home)})
        data = _load(repo / ".claude" / "settings.local.json")["sandbox"]["filesystem"]
        assert data["allowRead"] == [str(repo)]
        assert data["allowWrite"] == [str(repo)]


# ---------------------------------------------------------------------------
# working directories (permissions.additionalDirectories)
# ---------------------------------------------------------------------------


def _work_dirs(home: Path) -> list[str]:
    return [f"/tmp/claude-{os.getuid()}"]


class TestWorkingDirs:
    def test_adds_resolved_working_dirs(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, extra_env={"HOME": str(home)})
        data = _load(repo / ".claude" / "settings.local.json")
        assert data["permissions"]["additionalDirectories"] == _work_dirs(home)

    def test_never_writes_a_glob_or_tilde(self, tmp_path: Path) -> None:
        # additionalDirectories matches literal paths only: a glob is listed but never matched.
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, extra_env={"HOME": str(home)})
        for entry in _load(repo / ".claude" / "settings.local.json")["permissions"][
            "additionalDirectories"
        ]:
            assert "*" not in entry
            assert not entry.startswith("~")

    def test_second_run_no_duplicate_working_dirs(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, extra_env={"HOME": str(home)})
        _run(repo, extra_env={"HOME": str(home)})
        dirs = _load(repo / ".claude" / "settings.local.json")["permissions"][
            "additionalDirectories"
        ]
        assert dirs == _work_dirs(home)

    def test_keeps_existing_working_dirs(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _seed_settings(
            repo,
            {
                "permissions": {
                    "additionalDirectories": ["/opt/data"],
                    "allow": ["Bash(ls *)"],
                }
            },
        )
        _run(repo, extra_env={"HOME": str(home)})
        permissions = _load(repo / ".claude" / "settings.local.json")["permissions"]
        assert permissions["additionalDirectories"] == ["/opt/data"] + _work_dirs(home)
        assert permissions["allow"] == ["Bash(ls *)"]  # other permission keys untouched

    @pytest.mark.parametrize("extra_args", [[], ["--no-working-dirs"]])
    def test_removes_the_writable_magpie_dir(
        self, tmp_path: Path, extra_args: list[str]
    ) -> None:
        # A working directory is sandbox-writable, and the vetted-ops commands
        # run from ~/.claude/magpie outside the sandbox.
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        magpie = str(home / ".claude" / "magpie")
        stale = [magpie, magpie + "/", "~/.claude/magpie", "~/.claude/magpie/"]
        _seed_settings(
            repo, {"permissions": {"additionalDirectories": ["/opt/data", *stale]}}
        )
        _run(repo, extra_args, extra_env={"HOME": str(home)})
        dirs = _load(repo / ".claude" / "settings.local.json")["permissions"][
            "additionalDirectories"
        ]
        assert not set(stale) & set(dirs)
        assert dirs[0] == "/opt/data"

    def test_no_working_dirs_flag_skips_them(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        home = tmp_path / "home"
        _run(repo, args=["--no-working-dirs"], extra_env={"HOME": str(home)})
        assert "permissions" not in _load(repo / ".claude" / "settings.local.json")


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------


def _seed_settings(repo: Path, content: dict | None = None) -> Path:
    """Pre-create .claude/settings.local.json so dry-run tests can run the full preview path."""
    claude_dir = repo / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings = claude_dir / "settings.local.json"
    settings.write_text(
        json.dumps(content or {"sandbox": {"filesystem": {"allowRead": []}}})
    )
    return settings


class TestDryRun:
    def test_dry_run_does_not_modify_existing_file(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        settings = _seed_settings(repo)
        original = settings.read_text()
        _run(repo, args=["--dry-run"])
        assert settings.read_text() == original

    def test_dry_run_exits_zero(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _seed_settings(repo)
        result = _run(repo, args=["--dry-run"])
        assert result.returncode == 0

    def test_dry_run_prints_would_update(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _seed_settings(repo)
        result = _run(repo, args=["--dry-run"])
        assert "would update" in result.stderr or "would create" in result.stderr


# ---------------------------------------------------------------------------
# non-git directory
# ---------------------------------------------------------------------------


class TestNonGitDirectory:
    def test_not_in_git_repo_exits_zero(self, tmp_path: Path) -> None:
        """Script must exit 0 (not error) when run outside a git repo."""
        non_git = tmp_path / "not_a_repo"
        non_git.mkdir()
        result = _run(non_git)
        assert result.returncode == 0

    def test_not_in_git_repo_prints_warning(self, tmp_path: Path) -> None:
        non_git = tmp_path / "not_a_repo"
        non_git.mkdir()
        result = _run(non_git)
        assert "not inside a git working tree" in result.stderr

    def test_not_in_git_repo_creates_no_file(self, tmp_path: Path) -> None:
        non_git = tmp_path / "not_a_repo"
        non_git.mkdir()
        _run(non_git)
        assert not (non_git / ".claude" / "settings.local.json").exists()


# ---------------------------------------------------------------------------
# gitignore safety check
# ---------------------------------------------------------------------------


def _git_dir_of(repo: Path) -> str:
    """Absolute .git dir, as a git hook would export it in GIT_DIR."""
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--absolute-git-dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _no_global_git_config(tmp_path: Path) -> dict:
    """Env that makes only the repo's own .gitignore count.

    A developer's global excludes commonly already ignore
    `**/.claude/settings.local.json`, which would mask the "refuses"
    cases and make these tests pass for the wrong reason on some
    machines and not others.

    Pointing ``GIT_CONFIG_GLOBAL`` at an empty file is not enough: when
    ``core.excludesFile`` is unset git still falls back to its default
    ``$XDG_CONFIG_HOME/git/ignore`` (``~/.config/git/ignore``). So the
    stand-in global config has to set ``core.excludesFile`` explicitly.
    """
    cfg = tmp_path / "gitconfig-isolated"
    cfg.write_text(f"[core]\n\texcludesFile = {os.devnull}\n")
    return {"GIT_CONFIG_GLOBAL": str(cfg), "GIT_CONFIG_SYSTEM": os.devnull}


def _bare_git_repo(tmp_path: Path) -> Path:
    """An initialised repo with **no** .gitignore, so nothing is ignored."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    return repo


class TestGitignoreSafetyCheck:
    def test_refuses_when_not_gitignored(self, tmp_path: Path) -> None:
        """A genuinely un-ignored settings file must not be written to.

        Also covers the case where `.claude/` does not exist yet: the
        check has to resolve the repo from the nearest existing ancestor
        rather than from the file's own (missing) parent directory.
        """
        repo = _bare_git_repo(tmp_path)
        result = _run(repo, extra_env=_no_global_git_config(tmp_path))
        assert result.returncode == 0
        assert "is not gitignored" in result.stderr
        assert not (repo / ".claude" / "settings.local.json").exists()

    def test_writes_when_git_dir_is_exported(self, tmp_path: Path) -> None:
        """Regression: the check must survive the git-hook environment.

        Git hooks export GIT_DIR. With GIT_DIR set and no GIT_WORK_TREE,
        git treats the current directory as the work-tree root, so a
        check run from a subdirectory evaluated the root-anchored
        `/.claude/settings.local.json` pattern against `.claude/` as the
        root and wrongly concluded the file was not ignored.
        """
        repo = _make_git_repo(tmp_path)
        # `.claude/` must already exist, as it does in a real adopter
        # repo. With it missing the pre-fix code failed its `cd` and
        # fell through to writing anyway, which would mask the bug.
        (repo / ".claude").mkdir()
        result = _run(
            repo,
            extra_env={**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)},
        )

        assert "is not gitignored" not in result.stderr
        assert result.returncode == 0
        assert (repo / ".claude" / "settings.local.json").exists()

    def test_git_dir_exported_still_records_repo_root(self, tmp_path: Path) -> None:
        """The allowlist entry must be the repo root, not the .claude subdir."""
        repo = _make_git_repo(tmp_path)
        (repo / ".claude").mkdir()
        _run(
            repo,
            extra_env={**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)},
        )
        data = _load(repo / ".claude" / "settings.local.json")
        assert str(repo) in data["sandbox"]["filesystem"]["allowRead"]

    def test_git_dir_exported_still_refuses_when_not_gitignored(
        self, tmp_path: Path
    ) -> None:
        """The fix must not turn the safety check into a no-op."""
        repo = _bare_git_repo(tmp_path)
        result = _run(
            repo,
            extra_env={**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)},
        )

        assert "is not gitignored" in result.stderr
        assert not (repo / ".claude" / "settings.local.json").exists()

    def test_works_in_linked_worktree(self, tmp_path: Path) -> None:
        """The real-world trigger: a hook firing inside a git worktree."""
        repo = _make_git_repo(tmp_path)
        subprocess.run(
            ["git", "-C", str(repo), "add", ".gitignore"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.email=t@e.st",
                "-c",
                "user.name=t",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "init",
            ],
            check=True,
            capture_output=True,
        )
        wt = tmp_path / "wt"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "-b", "wt"],
            check=True,
            capture_output=True,
        )

        (wt / ".claude").mkdir()
        result = _run(
            wt,
            extra_env={**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(wt)},
        )

        assert "is not gitignored" not in result.stderr
        assert (wt / ".claude" / "settings.local.json").exists()
        data = _load(wt / ".claude" / "settings.local.json")
        assert str(wt) in data["sandbox"]["filesystem"]["allowRead"]

    def test_linked_worktree_may_read_its_main_checkout_but_not_write_it(
        self, tmp_path: Path
    ) -> None:
        """A linked worktree inherits the main checkout's personal layer and settings."""
        repo = _make_git_repo(tmp_path)
        subprocess.run(
            ["git", "-C", str(repo), "add", ".gitignore"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.email=t@e.st",
                "-c",
                "user.name=t",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "init",
            ],
            check=True,
            capture_output=True,
        )
        wt = tmp_path / "wt"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "-b", "wt"],
            check=True,
            capture_output=True,
        )
        (repo / ".apache-magpie-local").mkdir()
        (repo / ".claude").mkdir()
        (repo / ".claude" / "settings.json").write_text("{}")
        (repo / ".claude" / "worktrees").mkdir()  # sibling worktrees live here: never granted
        main = str(repo.resolve())
        inherited = [
            main + "/.apache-magpie-local",
            main + "/.claude/settings.json",
            # Written by the same --all-worktrees run, for the main checkout, first.
            main + "/.claude/settings.local.json",
        ]

        # From the worktree itself (the post-checkout hook): its `.git` file is
        # sandbox-writable, so nothing is granted.
        env = {**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(wt)}
        assert _run(wt, extra_env=env).returncode == 0
        fs = _load(wt / ".claude" / "settings.local.json")["sandbox"]["filesystem"]
        assert not any(path.startswith(main + "/") for path in fs["allowRead"])

        # From the main checkout with --all-worktrees: exactly the inherited files.
        main_env = {**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)}
        assert _run(repo, ["--all-worktrees"], extra_env=main_env).returncode == 0
        fs = _load(wt / ".claude" / "settings.local.json")["sandbox"]["filesystem"]
        for path in inherited:
            assert path in fs["allowRead"]
            assert path not in fs["allowWrite"]
        assert main not in fs["allowRead"]
        assert main + "/.claude" not in fs["allowRead"]
        assert main + "/.claude/worktrees" not in fs["allowRead"]
        own =_load(repo / ".claude" / "settings.local.json")["sandbox"]["filesystem"]
        assert not any(path.startswith(str(wt.resolve())) for path in own["allowRead"])

    def test_a_grant_whose_path_became_a_symlink_is_dropped_on_the_next_run(self, tmp_path: Path) -> None:
        """The main checkout's sandbox can swap its layer for a symlink after the grant; any run drops it."""
        repo = _make_git_repo(tmp_path)
        (repo / ".apache-magpie-local").mkdir()
        subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@e.st", "-c", "user.name=t",
             "-c", "commit.gpgsign=false", "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        wt = tmp_path / "wt"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "-b", "wt"],
            check=True,
            capture_output=True,
        )
        layer = str(repo.resolve() / ".apache-magpie-local")
        main_env = {**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)}
        assert _run(repo, ["--all-worktrees"], extra_env=main_env).returncode == 0
        settings = wt / ".claude" / "settings.local.json"
        assert layer in _load(settings)["sandbox"]["filesystem"]["allowRead"]

        secret = tmp_path / "secret"
        secret.mkdir()
        (repo / ".apache-magpie-local").rmdir()
        (repo / ".apache-magpie-local").symlink_to(secret)
        wt_env = {**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(wt)}
        result = _run(wt, extra_env=wt_env)
        assert result.returncode == 0
        assert layer not in _load(settings)["sandbox"]["filesystem"]["allowRead"]
        assert "dropping the read grant" in result.stderr

    def test_a_symlinked_inherited_path_is_never_granted(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        secret = tmp_path / "secret"
        secret.mkdir()
        (repo / ".apache-magpie-local").symlink_to(secret)
        subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@e.st", "-c", "user.name=t",
             "-c", "commit.gpgsign=false", "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        wt = tmp_path / "wt"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "-b", "wt"],
            check=True,
            capture_output=True,
        )
        env = {**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)}
        assert _run(repo, ["--all-worktrees"], extra_env=env).returncode == 0
        reads = _load(wt / ".claude" / "settings.local.json")["sandbox"]["filesystem"]["allowRead"]
        assert str(repo.resolve() / ".apache-magpie-local") not in reads
        assert not any(path.startswith(str(secret.resolve())) for path in reads)

    def test_a_forged_git_file_never_widens_the_read_grant(
        self, tmp_path: Path
    ) -> None:
        """A `.git` file naming a repository that does not list the worktree grants nothing."""
        other = tmp_path / "other"
        other.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(other)], check=True, capture_output=True
        )
        wt = _make_git_repo(tmp_path)
        # Sandboxed code can rewrite the worktree's `.git` file and create a
        # git dir in writable space whose `commondir` names `other`, but it
        # cannot register a worktree inside `other/.git`.
        fake = tmp_path / "writable" / "forged"
        fake.mkdir(parents=True)
        (fake / "commondir").write_text(str(other / ".git") + "\n")
        (fake / "HEAD").write_text("ref: refs/heads/main\n")
        (fake / "gitdir").write_text(str(wt / ".git") + "\n")
        subprocess.run(["rm", "-rf", str(wt / ".git")], check=True)
        (wt / ".git").write_text(f"gitdir: {fake}\n")
        env = {**_no_global_git_config(tmp_path), "GIT_DIR": str(fake)}
        settings = wt / ".claude" / "settings.local.json"
        for args in ([], ["--all-worktrees"]):
            _run(wt, args, extra_env=env)
            if settings.exists():
                reads = _load(settings)["sandbox"]["filesystem"]["allowRead"]
                assert not any(path.startswith(str(other.resolve())) for path in reads)

    def test_an_inherited_git_dir_never_lists_another_repos_worktrees(
        self, tmp_path: Path
    ) -> None:
        """A run from main checkout A with GIT_DIR naming repository B grants B's worktrees nothing of A."""
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        main = _make_git_repo(tmp_path / "a")
        (main / ".apache-magpie-local").mkdir()
        other = _make_git_repo(tmp_path / "b")
        subprocess.run(
            ["git", "-C", str(other), "-c", "user.name=t", "-c", "user.email=t@t",
             "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "init"],
            check=True,
            capture_output=True,
        )
        foreign = tmp_path / "b-wt"
        subprocess.run(
            ["git", "-C", str(other), "worktree", "add", "-q", str(foreign), "-b", "foreign"],
            check=True,
            capture_output=True,
        )
        (foreign / ".gitignore").write_text("/.claude/settings.local.json\n")
        env = {**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(other)}
        _run(main, ["--all-worktrees"], extra_env=env)
        settings = foreign / ".claude" / "settings.local.json"
        if settings.exists():
            reads = _load(settings)["sandbox"]["filesystem"]["allowRead"]
            assert not any(path.startswith(str(main.resolve())) for path in reads)

    def test_a_repository_planted_in_writable_space_grants_nothing(self, tmp_path: Path) -> None:
        """Sandboxed code can create a repo that registers the worktree and symlinks a secret."""
        wt = _make_git_repo(tmp_path)
        secret = tmp_path / "home" / ".ssh"
        secret.mkdir(parents=True)
        fake_main = tmp_path / "writable" / "fake"
        fake_main.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(fake_main)], check=True, capture_output=True)
        (fake_main / ".apache-magpie-local").symlink_to(secret)
        registered = fake_main / ".git" / "worktrees" / "wt"
        registered.mkdir(parents=True)
        (registered / "commondir").write_text("../..\n")
        (registered / "HEAD").write_text("ref: refs/heads/main\n")
        (registered / "gitdir").write_text(str(wt / ".git") + "\n")
        subprocess.run(["rm", "-rf", str(wt / ".git")], check=True)
        (wt / ".git").write_text(f"gitdir: {registered}\n")
        env = {**_no_global_git_config(tmp_path), "GIT_DIR": str(registered)}
        settings = wt / ".claude" / "settings.local.json"
        for args in ([], ["--all-worktrees"]):
            _run(wt, args, extra_env=env)
            if settings.exists():
                reads = _load(settings)["sandbox"]["filesystem"]["allowRead"]
                assert not any(path.startswith(str(fake_main.resolve())) for path in reads)
                assert not any(path.startswith(str(secret.resolve())) for path in reads)


# ---------------------------------------------------------------------------
# missing jq
# ---------------------------------------------------------------------------


def _fake_bin_without_jq(tmp_path: Path) -> Path:
    """Build a bin directory that has git but no jq."""
    git_path = shutil.which("git")
    if not git_path:
        pytest.skip("git not available")
    fake_bin = tmp_path / "fake_bin"
    fake_bin.mkdir(exist_ok=True)
    (fake_bin / "git").symlink_to(git_path)
    return fake_bin


class TestMissingJq:
    def test_no_jq_exits_zero(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        fake_bin = _fake_bin_without_jq(tmp_path)
        result = _run(repo, extra_env={"PATH": str(fake_bin)})
        assert result.returncode == 0

    def test_no_jq_prints_warning(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        fake_bin = _fake_bin_without_jq(tmp_path)
        result = _run(repo, extra_env={"PATH": str(fake_bin)})
        assert "jq not on PATH" in result.stderr

    def test_no_jq_creates_no_file(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        fake_bin = _fake_bin_without_jq(tmp_path)
        _run(repo, extra_env={"PATH": str(fake_bin)})
        assert not (repo / ".claude" / "settings.local.json").exists()


# ---------------------------------------------------------------------------
# write-protected settings file (the agent sandbox)
# ---------------------------------------------------------------------------


def _fake_bin_failing_mv(tmp_path: Path) -> Path:
    """A bin directory whose `mv` fails like a sandbox write-deny."""
    fake_bin = tmp_path / "fake_mv_bin"
    fake_bin.mkdir(exist_ok=True)
    mv = fake_bin / "mv"
    mv.write_text(
        '#!/bin/sh\necho "mv: rename $1 to $2: Operation not permitted" >&2\nexit 1\n'
    )
    mv.chmod(0o755)
    return fake_bin


class TestReplaceFails:
    def _run_denied(self, repo: Path, tmp_path: Path) -> subprocess.CompletedProcess:
        fake_bin = _fake_bin_failing_mv(tmp_path)
        return _run(
            repo, extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"}
        )

    def test_leaves_no_temp_file(self, tmp_path: Path) -> None:
        """Regression: a failed rename left `settings.local.json.XXXXXX` behind."""
        repo = _make_git_repo(tmp_path)
        _seed_settings(repo)
        self._run_denied(repo, tmp_path)
        leftovers = sorted(
            p.name for p in (repo / ".claude").glob("settings.local.json.*")
        )
        assert leftovers == []

    def test_leaves_file_untouched(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        settings = _seed_settings(repo)
        original = settings.read_text()
        self._run_denied(repo, tmp_path)
        assert settings.read_text() == original

    def test_exits_zero_with_warning(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _seed_settings(repo)
        result = self._run_denied(repo, tmp_path)
        assert result.returncode == 0
        assert "could not replace" in result.stderr


# ---------------------------------------------------------------------------
# unknown option
# ---------------------------------------------------------------------------


class TestUnknownOption:
    def test_unknown_option_exits_nonzero(self, tmp_path: Path) -> None:
        result = _run(tmp_path, args=["--bogus-option-xyz"])
        assert result.returncode != 0
