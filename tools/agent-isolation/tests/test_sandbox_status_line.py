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

"""Tests for sandbox-status-line.sh.

The helper reads the Claude Code statusLine JSON payload on stdin and
prints one line: the sandbox tag, the folder, the branch, the PR, the
model. The cases that matter here are the sandbox tag (it must never
claim a sandbox the session does not have) and the folder segment
inside a linked git worktree, where the project settings that decide
the tag live in the *main* checkout rather than in <cwd>.

Claude-Code-specific by construction, so `.claude/` is the only
settings directory under test: the script is wired through Claude
Code's `statusLine` setting, is fed Claude Code's statusLine payload on
stdin, and reads Claude Code's `sandbox.enabled` schema. No other
harness the framework supports has a status-line hook of that shape —
Codex, Gemini, OpenCode and Kiro carry their sandbox posture in their
own config files and surface it (when they surface it at all) through
their own UI. A harness that grows one gets its own helper and its own
tests; see `docs/adapters/add-a-harness.md`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "sandbox-status-line.sh"

ANSI = re.compile(r"\x1b\[[0-9;]*m")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


# Ignore the operator's own git config: a global `commit.gpgsign` (or a
# signing key this process cannot read) would fail every fixture commit.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )


def _init_repo(path: Path) -> Path:
    """Create a git repo at *path* with one commit, ready for worktrees."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )
    _git(path, "commit", "-q", "--allow-empty", "-m", "init")
    return path


def _settings(path: Path, sandbox: dict) -> None:
    """Write <path>/.claude/settings.local.json with a sandbox block."""
    claude = path / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "settings.local.json").write_text(json.dumps({"sandbox": sandbox}))


def _fake_gh(tmp_path: Path) -> Path:
    """A `gh` on PATH that always fails, so the PR segment stays silent."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n")
    gh.chmod(0o755)
    return bin_dir


def _run(cwd: Path, home: Path, tmp_path: Path) -> str:
    env = dict(GIT_ENV)
    env["HOME"] = str(home)
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    env["PATH"] = f"{_fake_gh(tmp_path)}{os.pathsep}{env['PATH']}"
    payload = json.dumps({"cwd": str(cwd), "model": {"display_name": "Opus 5"}})
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return ANSI.sub("", result.stdout)


def _folder(out: str) -> str:
    """The folder segment: everything between the tag and the first ' | '."""
    return out.split("] ", 1)[1].split(" | ", 1)[0]


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A user scope that says the sandbox is ON — the drift-prone default."""
    h = tmp_path / "home"
    (h / ".claude").mkdir(parents=True)
    (h / ".claude" / "settings.json").write_text(
        json.dumps({"sandbox": {"enabled": True}})
    )
    return h


# ---------------------------------------------------------------------------
# sandbox tag — plain (non-worktree) checkout
# ---------------------------------------------------------------------------


class TestSandboxTag:
    def test_project_scope_true_renders_sandbox(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _settings(repo, {"enabled": True})
        assert _run(repo, home, tmp_path).startswith("[sandbox] ")

    def test_project_scope_false_beats_user_scope_true(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _settings(repo, {"enabled": False})
        assert _run(repo, home, tmp_path).startswith("[NO SANDBOX] ")

    def test_auto_allow_gets_its_own_tag(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _settings(repo, {"enabled": True, "autoAllowBashIfSandboxed": True})
        assert _run(repo, home, tmp_path).startswith("[sandbox-auto] ")

    def test_falls_through_to_user_scope(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert _run(repo, home, tmp_path).startswith("[sandbox] ")

    def test_non_git_directory_still_renders(self, tmp_path: Path, home: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        out = _run(plain, home, tmp_path)
        assert out.startswith("[sandbox] ")
        assert "plain" in out


# ---------------------------------------------------------------------------
# sandbox tag — linked worktrees
#
# Claude Code scopes a linked worktree's project settings to the main
# checkout: `/sandbox` writes `enabled` there, and the worktree's own
# .claude/settings.local.json usually holds only the per-worktree
# filesystem allowlist. Reading <cwd> alone falls through to user scope
# and claims a sandbox the session does not have.
# ---------------------------------------------------------------------------


class TestLinkedWorktreeSandboxTag:
    def test_worktrunk_worktree_reads_main_checkout(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _settings(repo, {"enabled": False})
        wt = tmp_path / "repo.feature-x"
        _git(repo, "worktree", "add", "-q", "-b", "feature-x", str(wt))
        # What the post-checkout hook writes: filesystem only, no `enabled`.
        _settings(wt, {"filesystem": {"allowRead": [str(wt)]}})
        assert _run(wt, home, tmp_path).startswith("[NO SANDBOX] ")

    def test_worktree_subdirectory_reads_main_checkout(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _settings(repo, {"enabled": False})
        wt = tmp_path / "repo.feature-x"
        _git(repo, "worktree", "add", "-q", "-b", "feature-x", str(wt))
        sub = wt / "src" / "deep"
        sub.mkdir(parents=True)
        assert _run(sub, home, tmp_path).startswith("[NO SANDBOX] ")

    def test_main_checkout_beats_a_hand_written_worktree_setting(
        self, tmp_path: Path, home: Path
    ) -> None:
        """The main checkout is the file the harness reads, so it wins.

        A worktree-local `enabled` is not read by Claude Code at all.
        Preferring it because it is "more specific" would paint a green
        [sandbox] over a session that has none -- the one thing this line
        must never do.
        """
        repo = _init_repo(tmp_path / "repo")
        _settings(repo, {"enabled": False})
        wt = tmp_path / "repo.feature-x"
        _git(repo, "worktree", "add", "-q", "-b", "feature-x", str(wt))
        _settings(wt, {"enabled": True})
        assert _run(wt, home, tmp_path).startswith("[NO SANDBOX] ")

    def test_bare_repo_worktree_does_not_read_the_bare_dir_s_parent(
        self, tmp_path: Path, home: Path
    ) -> None:
        """`clone --bare` + worktrees has no main checkout to read.

        The common dir is `<repo>.git`, so its parent is whatever directory
        happens to contain it -- an unrelated project's settings, or none.
        Falling through to user scope is the honest answer.
        """
        container = tmp_path / "container"
        container.mkdir()
        # The trap: a `.claude` belonging to the containing directory.
        _settings(container, {"enabled": False})
        bare = container / "proj.git"
        seed = _init_repo(tmp_path / "seed")
        subprocess.run(
            ["git", "clone", "-q", "--bare", str(seed), str(bare)],
            check=True,
            capture_output=True,
            text=True,
            env=GIT_ENV,
        )
        wt = container / "feature-x"
        _git(bare, "worktree", "add", "-q", "-b", "feature-x", str(wt))
        out = _run(wt, home, tmp_path)
        # User scope says on, and nothing legitimate overrides it.
        assert out.startswith("[sandbox] ")
        # The repo name comes from the bare dir, not from its parent.
        assert _folder(out) == "proj/feature-x"

    def test_main_checkout_subdirectory_is_not_a_worktree(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _settings(repo, {"enabled": False})
        sub = repo / "src"
        sub.mkdir()
        out = _run(sub, home, tmp_path)
        assert out.startswith("[NO SANDBOX] ")
        # Not a linked worktree, so no "<source>/<worktree>" split — the
        # folder segment stays the plain basename it has always been.
        assert _folder(out) == "src"


# ---------------------------------------------------------------------------
# folder segment
# ---------------------------------------------------------------------------


class TestFolderSegment:
    def test_worktrunk_layout_strips_the_repeated_repo_name(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        wt = tmp_path / "repo.feature-x"
        _git(repo, "worktree", "add", "-q", "-b", "feature-x", str(wt))
        assert _folder(_run(wt, home, tmp_path)) == "repo/feature-x"

    def test_worktrunk_dash_separator(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        wt = tmp_path / "repo-feature-x"
        _git(repo, "worktree", "add", "-q", "-b", "feature-x", str(wt))
        assert _folder(_run(wt, home, tmp_path)) == "repo/feature-x"

    def test_claude_code_worktree_layout(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        wt = repo / ".claude" / "worktrees" / "feature-x"
        _git(repo, "worktree", "add", "-q", "-b", "feature-x", str(wt))
        assert _folder(_run(wt, home, tmp_path)) == "repo/feature-x"

    def test_unrelated_worktree_name_is_left_alone(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        wt = tmp_path / "elsewhere"
        _git(repo, "worktree", "add", "-q", "-b", "feature-x", str(wt))
        assert _folder(_run(wt, home, tmp_path)) == "repo/elsewhere"

    def test_main_checkout_renders_one_segment(self, tmp_path: Path, home: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert _folder(_run(repo, home, tmp_path)) == "repo"
