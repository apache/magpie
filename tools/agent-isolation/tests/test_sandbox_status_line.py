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
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "sandbox-status-line.sh"

ANSI = re.compile(r"\x1b\[[0-9;]*m")

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

BRANCH = "feature-x"


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


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
# the cases
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    """One layout on disk plus the line it must produce.

    `worktree` is a path relative to tmp_path, so a sibling layout and a
    nested one differ only in that string. `main` and `worktree_settings`
    are the `sandbox` blocks written to each checkout's
    `.claude/settings.local.json`; `None` means no file at all.
    """

    id: str
    tag: str
    folder: str
    main: dict | None = None
    worktree: str | None = None
    worktree_settings: dict | None = None
    subdir: str | None = None
    git: bool = True


def _build(tmp_path: Path, case: Case) -> Path:
    """Materialise *case* under tmp_path and return the <cwd> to report."""
    if not case.git:
        cwd = tmp_path / case.folder
        cwd.mkdir(parents=True)
        return cwd

    repo = _init_repo(tmp_path / "repo")
    if case.main is not None:
        _settings(repo, case.main)

    cwd = repo
    if case.worktree is not None:
        cwd = tmp_path / case.worktree
        _git(repo, "worktree", "add", "-q", "-b", BRANCH, str(cwd))
        if case.worktree_settings is not None:
            _settings(cwd, case.worktree_settings)

    if case.subdir is not None:
        cwd = cwd / case.subdir
        cwd.mkdir(parents=True)
    return cwd


CASES = [
    # --- sandbox tag, plain (non-worktree) checkout ------------------------
    Case(
        id="project-scope-true",
        main={"enabled": True},
        tag="[sandbox]",
        folder="repo",
    ),
    Case(
        id="project-scope-false-beats-user-scope-true",
        main={"enabled": False},
        tag="[NO SANDBOX]",
        folder="repo",
    ),
    Case(
        id="auto-allow-gets-its-own-tag",
        main={"enabled": True, "autoAllowBashIfSandboxed": True},
        tag="[sandbox-auto]",
        folder="repo",
    ),
    Case(
        id="no-project-scope-falls-through-to-user-scope",
        tag="[sandbox]",
        folder="repo",
    ),
    Case(
        id="non-git-directory-still-renders",
        git=False,
        tag="[sandbox]",
        folder="plain",
    ),
    Case(
        # A subdirectory of a plain checkout is not a linked worktree, so
        # the folder segment stays the plain basename it has always been.
        id="main-checkout-subdirectory-is-not-a-worktree",
        main={"enabled": False},
        subdir="src",
        tag="[NO SANDBOX]",
        folder="src",
    ),
    # --- sandbox tag, linked worktrees -------------------------------------
    #
    # Claude Code scopes a linked worktree's project settings to the main
    # checkout: `/sandbox` writes `enabled` there, and the worktree's own
    # .claude/settings.local.json usually holds only the per-worktree
    # filesystem allowlist. Reading <cwd> alone falls through to user scope
    # and claims a sandbox the session does not have.
    Case(
        id="worktree-reads-main-checkout",
        main={"enabled": False},
        worktree="repo.feature-x",
        # What the post-checkout hook writes: filesystem only, no `enabled`.
        worktree_settings={"filesystem": {"allowRead": ["."]}},
        tag="[NO SANDBOX]",
        folder="repo/feature-x",
    ),
    Case(
        id="worktree-subdirectory-reads-main-checkout",
        main={"enabled": False},
        worktree="repo.feature-x",
        subdir="src/deep",
        tag="[NO SANDBOX]",
        folder="repo/feature-x",
    ),
    Case(
        id="worktree-own-settings-win-over-main",
        main={"enabled": False},
        worktree="repo.feature-x",
        worktree_settings={"enabled": True},
        tag="[sandbox]",
        folder="repo/feature-x",
    ),
    # --- folder segment, per worktree layout -------------------------------
    Case(
        id="folder-worktrunk-dot-separator",
        worktree="repo.feature-x",
        tag="[sandbox]",
        folder="repo/feature-x",
    ),
    Case(
        id="folder-worktrunk-dash-separator",
        worktree="repo-feature-x",
        tag="[sandbox]",
        folder="repo/feature-x",
    ),
    Case(
        id="folder-claude-code-worktrees-layout",
        worktree="repo/.claude/worktrees/feature-x",
        tag="[sandbox]",
        folder="repo/feature-x",
    ),
    Case(
        id="folder-unrelated-worktree-name-left-alone",
        worktree="elsewhere",
        tag="[sandbox]",
        folder="repo/elsewhere",
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_status_line(tmp_path: Path, home: Path, case: Case) -> None:
    out = _run(_build(tmp_path, case), home, tmp_path)
    assert out.startswith(f"{case.tag} "), out
    assert _folder(out) == case.folder, out
