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
