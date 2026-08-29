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


def _run(cwd: Path, args: list | None = None, extra_env: dict | None = None) -> subprocess.CompletedProcess:
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
        existing = {"sandbox": {"filesystem": {"allowRead": ["/other"]}}, "someKey": "someValue"}
        (claude_dir / "settings.local.json").write_text(json.dumps(existing))
        _run(repo)
        data = _load(claude_dir / "settings.local.json")
        assert str(repo) in data["sandbox"]["filesystem"]["allowRead"]
        assert data.get("someKey") == "someValue"  # non-sandbox keys untouched


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------


def _seed_settings(repo: Path, content: dict | None = None) -> Path:
    """Pre-create .claude/settings.local.json so dry-run tests can run the full preview path."""
    claude_dir = repo / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings = claude_dir / "settings.local.json"
    settings.write_text(json.dumps(content or {"sandbox": {"filesystem": {"allowRead": []}}}))
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
            repo, extra_env={**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)}
        )

        assert "is not gitignored" not in result.stderr
        assert result.returncode == 0
        assert (repo / ".claude" / "settings.local.json").exists()

    def test_git_dir_exported_still_records_repo_root(self, tmp_path: Path) -> None:
        """The allowlist entry must be the repo root, not the .claude subdir."""
        repo = _make_git_repo(tmp_path)
        (repo / ".claude").mkdir()
        _run(repo, extra_env={**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)})
        data = _load(repo / ".claude" / "settings.local.json")
        assert str(repo) in data["sandbox"]["filesystem"]["allowRead"]

    def test_git_dir_exported_still_refuses_when_not_gitignored(self, tmp_path: Path) -> None:
        """The fix must not turn the safety check into a no-op."""
        repo = _bare_git_repo(tmp_path)
        result = _run(
            repo, extra_env={**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(repo)}
        )

        assert "is not gitignored" in result.stderr
        assert not (repo / ".claude" / "settings.local.json").exists()

    def test_works_in_linked_worktree(self, tmp_path: Path) -> None:
        """The real-world trigger: a hook firing inside a git worktree."""
        repo = _make_git_repo(tmp_path)
        subprocess.run(
            ["git", "-C", str(repo), "add", ".gitignore"], check=True, capture_output=True
        )
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

        (wt / ".claude").mkdir()
        result = _run(wt, extra_env={**_no_global_git_config(tmp_path), "GIT_DIR": _git_dir_of(wt)})

        assert "is not gitignored" not in result.stderr
        assert (wt / ".claude" / "settings.local.json").exists()
        data = _load(wt / ".claude" / "settings.local.json")
        assert str(wt) in data["sandbox"]["filesystem"]["allowRead"]


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
# unknown option
# ---------------------------------------------------------------------------


class TestUnknownOption:
    def test_unknown_option_exits_nonzero(self, tmp_path: Path) -> None:
        result = _run(tmp_path, args=["--bogus-option-xyz"])
        assert result.returncode != 0
