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

"""Tests for the harness-neutral --check and --exec entry points.

``--check`` inspects a command and reports allow/deny without running it.
``--exec`` inspects then exec-replaces the process on allow, so tests that
reach the exec path use subprocess so the test runner process survives.

The point of both modes is that any harness (or shell wrapper) can call them
without a harness-specific hook adapter — the guard decisions still come from
the same :func:`agent_guard.dispatch` core that backs Claude Code and OpenCode.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

import agent_guard

# ---------------------------------------------------------------------------
# --check mode (check_main called directly — safe, no exec)
# ---------------------------------------------------------------------------


def test_check_denied_coauthor(capsys: pytest.CaptureFixture[str]) -> None:
    """--check should exit DENY_EXIT and print reason for a Co-Authored-By commit."""
    rc = agent_guard.check_main(["git", "commit", "-m", "fix\n\nCo-Authored-By: A <a@b.c>"])
    out = capsys.readouterr().out
    assert rc == agent_guard.DENY_EXIT
    assert "commit-trailer" in out


def test_check_allowed_safe(capsys: pytest.CaptureFixture[str]) -> None:
    """--check should exit ALLOW_EXIT silently for a non-guarded command."""
    rc = agent_guard.check_main(["git", "status"])
    assert rc == agent_guard.ALLOW_EXIT
    assert capsys.readouterr().out == ""


def test_check_non_git_command(capsys: pytest.CaptureFixture[str]) -> None:
    """--check fast-path allows commands that are not in GUARDED_HEADS."""
    rc = agent_guard.check_main(["ls", "-la"])
    assert rc == agent_guard.ALLOW_EXIT
    assert capsys.readouterr().out == ""


def test_check_empty_argv(capsys: pytest.CaptureFixture[str]) -> None:
    """--check with no argv is a usage error: USAGE_EXIT, not DENY_EXIT."""
    rc = agent_guard.check_main([])
    err = capsys.readouterr().err
    assert rc == agent_guard.USAGE_EXIT
    assert rc != agent_guard.DENY_EXIT  # a misinvocation must not read as a policy block
    assert "no command" in err


def test_check_fail_open_on_dispatch_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A guard-engine error must fail open (ALLOW_EXIT), never block the user."""

    def _boom(_command: str, _cwd: str | None = None) -> str | None:
        raise RuntimeError("guard exploded")

    monkeypatch.setattr(agent_guard, "dispatch", _boom)
    rc = agent_guard.check_main(["git", "push", "origin", "main"])
    assert rc == agent_guard.ALLOW_EXIT
    assert "guard engine error" in capsys.readouterr().err


def test_check_decision_matches_dispatch() -> None:
    """--check must deny exactly what dispatch() denies (shared core)."""
    command_tokens = ["git", "commit", "-m", "x\n\nCo-Authored-By: A <a@b.c>"]
    dispatch_denies = agent_guard.dispatch(" ".join(command_tokens)) is not None
    check_denies = agent_guard.check_main(command_tokens) == agent_guard.DENY_EXIT
    assert dispatch_denies is check_denies is True


def test_check_allowed_decision_matches_dispatch() -> None:
    """--check allows exactly what dispatch() allows."""
    command_tokens = ["git", "log", "--oneline"]
    dispatch_allows = agent_guard.dispatch(" ".join(command_tokens)) is None
    check_allows = agent_guard.check_main(command_tokens) == agent_guard.ALLOW_EXIT
    assert dispatch_allows is check_allows is True


def test_cli_routes_check_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """cli() should route --check to check_main."""
    rc = agent_guard.cli(["--check", "git", "status"])
    assert rc == agent_guard.ALLOW_EXIT
    assert capsys.readouterr().out == ""


def test_cli_check_denied(capsys: pytest.CaptureFixture[str]) -> None:
    """cli() --check routing should propagate deny from check_main."""
    rc = agent_guard.cli(["--check", "git", "commit", "-m", "x\n\nCo-Authored-By: A <a@b.c>"])
    assert rc == agent_guard.DENY_EXIT
    assert "commit-trailer" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# --exec mode (subprocess — exec replaces the process image)
# ---------------------------------------------------------------------------


def _run_exec(*args: str) -> subprocess.CompletedProcess[str]:
    """Run agent-guard --exec <args> in a child process."""
    return subprocess.run(
        [sys.executable, "-m", "agent_guard", "--exec", *args],
        capture_output=True,
        text=True,
    )


def test_exec_allowed_runs_command() -> None:
    """--exec should exec the command on allow; its output and exit code survive."""
    proc = _run_exec("echo", "guard-passed")
    assert proc.returncode == 0
    assert "guard-passed" in proc.stdout


def test_exec_denied_does_not_run_command() -> None:
    """--exec should exit DENY_EXIT and NOT run the command on deny."""
    proc = _run_exec("git", "commit", "-m", "x\n\nCo-Authored-By: A <a@b.c>")
    assert proc.returncode == agent_guard.DENY_EXIT
    # Command never ran — no git error on stdout, reason on stderr.
    assert "Co-Authored-By" in proc.stderr or "commit-trailer" in proc.stderr


def test_exec_denied_prints_reason_to_stderr() -> None:
    """--exec deny reason must go to stderr (stdout belongs to the exec'd command)."""
    proc = _run_exec("git", "commit", "-m", "fix\n\nCo-Authored-By: A <a@b.c>")
    assert proc.returncode == agent_guard.DENY_EXIT
    assert proc.stderr.strip() != ""
    assert proc.stdout.strip() == ""


def test_exec_allowed_exit_code_propagates() -> None:
    """The exec'd command's own exit code propagates through --exec."""
    proc = _run_exec(sys.executable, "-c", "import sys; sys.exit(42)")
    assert proc.returncode == 42


def test_exec_empty_argv() -> None:
    """--exec with no command is a usage error: USAGE_EXIT, not DENY_EXIT."""
    proc = subprocess.run(
        [sys.executable, "-m", "agent_guard", "--exec"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == agent_guard.USAGE_EXIT
    assert proc.returncode != agent_guard.DENY_EXIT
    assert "no command" in proc.stderr


def test_exec_nonexistent_command() -> None:
    """--exec with a nonexistent binary should exit 1 with an OS error."""
    proc = _run_exec("__nonexistent_command_xyz__")
    assert proc.returncode == 1
    assert proc.stderr.strip() != ""


def test_exec_recursion_guard_refuses_at_depth_cap() -> None:
    """A PATH wrapper re-resolving into --exec must error out, not loop forever.

    Simulated by pre-seeding the depth counter at the cap: the next --exec of an
    allowed command must refuse with exit 1 and a diagnostic, rather than exec.
    """
    env = dict(os.environ)
    env[agent_guard._EXEC_DEPTH_VAR] = str(agent_guard._EXEC_DEPTH_MAX)
    proc = subprocess.run(
        [sys.executable, "-m", "agent_guard", "--exec", "echo", "should-not-run"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 1
    assert "should-not-run" not in proc.stdout
    assert "re-entry depth" in proc.stderr


def test_exec_depth_counter_increments_for_child() -> None:
    """A normally-run command sees the depth counter bumped to 1 in its env."""
    proc = _run_exec(
        sys.executable,
        "-c",
        f"import os; print(os.environ.get({agent_guard._EXEC_DEPTH_VAR!r}))",
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "1"


def test_cli_routes_exec_flag() -> None:
    """cli() should route --exec to exec_main (allowed → runs echo)."""
    proc = subprocess.run(
        [sys.executable, "-m", "agent_guard", "--exec", "echo", "cli-exec-ok"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "cli-exec-ok" in proc.stdout
