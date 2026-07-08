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

"""Tests for the generic `agent-iso` entry point of agent-iso.sh.

The generic entry point accepts any harness CLI as its first positional
argument:
  - Sourced: ``agent-iso <cli> [cli-args]``
  - Direct exec: ``bash agent-iso.sh agent-iso <cli> [cli-args]``

Strategy: put a fake arbitrary CLI (named ``my-harness``) on $PATH that
prints ARG: lines for its argv then its env.  Invoke via both paths.
Verify:
  - credential-shaped env vars are stripped (same posture as claude-iso /
    opencode-iso);
  - the Claude-only ``--settings`` sandbox grant is NOT injected;
  - the banner identifies the harness name correctly;
  - missing CLI exits 127 with a helpful message;
  - empty first-arg (no CLI given) exits 1 with a usage hint.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "agent-iso.sh"
BASH = shutil.which("bash") or "/bin/bash"

_FAKE_CLI = "my-harness"


def _make_fake_cli(tmp_path: Path, name: str = _FAKE_CLI) -> Path:
    """A fake CLI that prints ARG: lines for its argv, then its env."""
    fake = tmp_path / name
    fake.write_text('#!/bin/sh\nfor a in "$@"; do echo "ARG:$a"; done\nprintenv\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return tmp_path


def _run_direct(
    tmp_path: Path,
    cli_name: str = _FAKE_CLI,
    extra_env: dict | None = None,
    extra_cli_args: list | None = None,
) -> subprocess.CompletedProcess:
    """Invoke via direct exec: bash agent-iso.sh agent-iso <cli> [args]."""
    _make_fake_cli(tmp_path, cli_name)
    env: dict[str, str] = {
        "PATH": f"{tmp_path}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": "/tmp/testhome",
        "USER": "testuser",
        "SHELL": "/bin/sh",
        "TERM": "xterm",
        "LANG": "en_US.UTF-8",
    }
    if extra_env:
        env.update(extra_env)
    # The generic direct-exec path: first arg selects "agent-iso" mode, second
    # is the harness CLI name, rest are CLI args.
    cmd = [BASH, str(SCRIPT), "agent-iso", cli_name] + (extra_cli_args or [])
    return subprocess.run(cmd, env=env, cwd=str(tmp_path), capture_output=True, text=True)


def _parse_env(stdout: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        if line.startswith("ARG:"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            result[key] = val
    return result


def _argv(stdout: str) -> list[str]:
    return [line[len("ARG:"):] for line in stdout.splitlines() if line.startswith("ARG:")]


class TestGenericIsoDirectExec:
    def test_launches_generic_cli(self, tmp_path: Path) -> None:
        res = _run_direct(tmp_path)
        assert res.returncode == 0, res.stderr
        assert f"[{_FAKE_CLI}-iso] running in isolated env" in res.stderr

    def test_credentials_stripped(self, tmp_path: Path) -> None:
        res = _run_direct(
            tmp_path,
            extra_env={"GH_TOKEN": "ghp_secret", "ANTHROPIC_API_KEY": "sk-ant-secret"},
        )
        assert res.returncode == 0, res.stderr
        env = _parse_env(res.stdout)
        assert "GH_TOKEN" not in env
        assert "ANTHROPIC_API_KEY" not in env

    def test_passthrough_preserved(self, tmp_path: Path) -> None:
        res = _run_direct(tmp_path, extra_env={"HOME": "/home/testuser"})
        assert res.returncode == 0, res.stderr
        assert _parse_env(res.stdout).get("HOME") == "/home/testuser"

    def test_no_settings_injection(self, tmp_path: Path) -> None:
        # The Claude-only --settings sandbox grant must NOT appear for generic CLIs.
        res = _run_direct(tmp_path, extra_cli_args=["run", "hello"])
        assert res.returncode == 0, res.stderr
        argv = _argv(res.stdout)
        assert "--settings" not in argv
        assert argv == ["run", "hello"]

    def test_cli_args_forwarded(self, tmp_path: Path) -> None:
        res = _run_direct(tmp_path, extra_cli_args=["--flag", "value", "positional"])
        assert res.returncode == 0, res.stderr
        assert _argv(res.stdout) == ["--flag", "value", "positional"]

    def test_worktree_flag_stripped_for_generic_cli(self, tmp_path: Path) -> None:
        # -w / --worktree is a Claude-only control flag; it must not leak into a
        # generic CLI's argv where it could be misparsed as a native flag.
        res = _run_direct(tmp_path, extra_cli_args=["-w", "run"])
        assert res.returncode == 0, res.stderr
        argv = _argv(res.stdout)
        assert "-w" not in argv
        assert "--worktree" not in argv
        assert argv == ["run"]

    def test_ssh_auth_sock_passed_through_for_generic_cli(self, tmp_path: Path) -> None:
        # SSH_AUTH_SOCK is a fixed member of the Layer 0 passthrough (RFC-AI-0002
        # § Layer 0) and must reach every harness identically, generic ones
        # included. Gating git push is a separate Layer 3 concern.
        res = _run_direct(tmp_path, extra_env={"SSH_AUTH_SOCK": "/tmp/agent.sock"})
        assert res.returncode == 0, res.stderr
        assert _parse_env(res.stdout).get("SSH_AUTH_SOCK") == "/tmp/agent.sock"

    def test_missing_cli_exits_127(self, tmp_path: Path) -> None:
        # No fake binary in tmp_path — should exit 127.
        env = {
            "PATH": str(tmp_path),
            "HOME": "/tmp",
            "USER": "testuser",
            "SHELL": "/bin/sh",
        }
        res = subprocess.run(
            [BASH, str(SCRIPT), "agent-iso", "nonexistent-cli"],
            env=env,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert res.returncode == 127
        assert "not found" in res.stderr

    def test_no_cli_arg_exits_nonzero(self, tmp_path: Path) -> None:
        # Invoke as: bash agent-iso.sh agent-iso   (no CLI name given)
        env = {
            "PATH": str(tmp_path),
            "HOME": "/tmp",
            "USER": "testuser",
            "SHELL": "/bin/sh",
        }
        res = subprocess.run(
            [BASH, str(SCRIPT), "agent-iso"],
            env=env,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert res.returncode != 0
        assert "Usage" in res.stderr


class TestGenericIsoSourced:
    """Test the ``agent-iso()`` shell function exposed when the script is sourced."""

    def _run_sourced(
        self,
        tmp_path: Path,
        cli_name: str = _FAKE_CLI,
        extra_env: dict | None = None,
        extra_cli_args: list | None = None,
    ) -> subprocess.CompletedProcess:
        _make_fake_cli(tmp_path, cli_name)
        env: dict[str, str] = {
            "PATH": f"{tmp_path}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "HOME": "/tmp/testhome",
            "USER": "testuser",
            "SHELL": "/bin/sh",
            "TERM": "xterm",
            "LANG": "en_US.UTF-8",
        }
        if extra_env:
            env.update(extra_env)
        cli_args_str = " ".join(f'"{a}"' for a in (extra_cli_args or []))
        script_body = (
            f'source "{SCRIPT}"\n'
            f"agent-iso {cli_name} {cli_args_str}\n"
        )
        return subprocess.run(
            [BASH, "-c", script_body],
            env=env,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )

    def test_sourced_launches_generic_cli(self, tmp_path: Path) -> None:
        res = self._run_sourced(tmp_path)
        assert res.returncode == 0, res.stderr
        assert f"[{_FAKE_CLI}-iso] running in isolated env" in res.stderr

    def test_sourced_credentials_stripped(self, tmp_path: Path) -> None:
        res = self._run_sourced(
            tmp_path,
            extra_env={"GH_TOKEN": "ghp_secret", "ANTHROPIC_API_KEY": "sk-ant-secret"},
        )
        assert res.returncode == 0, res.stderr
        env = _parse_env(res.stdout)
        assert "GH_TOKEN" not in env
        assert "ANTHROPIC_API_KEY" not in env

    def test_sourced_no_settings_injection(self, tmp_path: Path) -> None:
        res = self._run_sourced(tmp_path, extra_cli_args=["run", "hello"])
        assert res.returncode == 0, res.stderr
        argv = _argv(res.stdout)
        assert "--settings" not in argv
        assert argv == ["run", "hello"]

    def test_sourced_different_cli_names(self, tmp_path: Path) -> None:
        for cli in ("codex", "cursor", "gemini"):
            _make_fake_cli(tmp_path, cli)
            env: dict[str, str] = {
                "PATH": f"{tmp_path}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                "HOME": "/tmp/testhome",
                "USER": "testuser",
                "SHELL": "/bin/sh",
                "TERM": "xterm",
                "LANG": "en_US.UTF-8",
            }
            script_body = f'source "{SCRIPT}"\nagent-iso {cli}\n'
            res = subprocess.run(
                [BASH, "-c", script_body],
                env=env,
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
            )
            assert res.returncode == 0, f"CLI {cli!r} failed: {res.stderr}"
            assert f"[{cli}-iso] running in isolated env" in res.stderr

    def test_sourced_no_cli_arg_exits_nonzero(self, tmp_path: Path) -> None:
        # Sourced `agent-iso` with no CLI must match the direct-exec path: a
        # usage hint and a non-zero exit, not a confusing "'' not found".
        env = {
            "PATH": f"{tmp_path}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "HOME": "/tmp/testhome",
            "USER": "testuser",
            "SHELL": "/bin/sh",
        }
        res = subprocess.run(
            [BASH, "-c", f'source "{SCRIPT}"\nagent-iso\n'],
            env=env,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert res.returncode != 0
        assert "Usage" in res.stderr


class TestGenericIsoSymlink:
    """The direct-exec ``case "agent-iso")`` branch: a symlink named exactly
    ``agent-iso`` takes its first positional arg as the harness CLI name."""

    @staticmethod
    def _env(tmp_path: Path) -> dict:
        return {
            "PATH": f"{tmp_path}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "HOME": "/tmp/testhome",
            "USER": "testuser",
            "SHELL": "/bin/sh",
            "TERM": "xterm",
            "LANG": "en_US.UTF-8",
        }

    def test_symlink_named_agent_iso_launches_cli(self, tmp_path: Path) -> None:
        _make_fake_cli(tmp_path)
        link = tmp_path / "agent-iso"
        link.symlink_to(SCRIPT)
        res = subprocess.run(
            [BASH, str(link), _FAKE_CLI, "run", "hello"],
            env=self._env(tmp_path),
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stderr
        assert f"[{_FAKE_CLI}-iso] running in isolated env" in res.stderr
        assert _argv(res.stdout) == ["run", "hello"]

    def test_symlink_named_agent_iso_no_cli_arg_exits_nonzero(
        self, tmp_path: Path
    ) -> None:
        link = tmp_path / "agent-iso"
        link.symlink_to(SCRIPT)
        res = subprocess.run(
            [BASH, str(link)],
            env=self._env(tmp_path),
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert res.returncode != 0
        assert "Usage" in res.stderr
