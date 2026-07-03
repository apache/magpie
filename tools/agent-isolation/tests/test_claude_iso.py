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

"""Tests for agent-iso.sh — the clean-environment wrapper.

Strategy: put a fake ``claude`` binary (``printenv``) on $PATH and run
agent-iso.sh against it.  Verify which variables survive the
``env -i`` filter and which are stripped.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "agent-iso.sh"

# Use the absolute path so tests that restrict PATH still launch bash correctly.
BASH = shutil.which("bash") or "/bin/bash"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_fake_claude(tmp_path: Path) -> Path:
    """Return a directory containing a 'claude' binary that prints its env."""
    fake = tmp_path / "claude"
    fake.write_text("#!/bin/sh\nprintenv\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return tmp_path  # the directory to prepend to PATH


def _run(tmp_path: Path, extra_env: dict | None = None, extra_args: list | None = None) -> subprocess.CompletedProcess:
    """Run agent-iso.sh with a fake claude in a non-git temp directory."""
    bin_dir = _make_fake_claude(tmp_path)
    env: dict[str, str] = {
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": "/tmp/testhome",
        "USER": "testuser",
        "SHELL": "/bin/sh",
        "TERM": "xterm",
        "LANG": "en_US.UTF-8",
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [BASH, str(SCRIPT)] + (extra_args or []),
        env=env,
        # Use tmp_path as cwd — outside any git repo, so the script skips
        # the sandbox auto-allow injection (keeps test output predictable).
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )


def _parse_env(stdout: str) -> dict[str, str]:
    """Parse printenv output (KEY=value lines) into a dict."""
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            result[key] = val
    return result


# ---------------------------------------------------------------------------
# credential stripping
# ---------------------------------------------------------------------------


class TestCredentialStripping:
    def test_aws_access_key_stripped(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"})
        assert res.returncode == 0
        assert "AWS_ACCESS_KEY_ID" not in _parse_env(res.stdout)

    def test_aws_secret_stripped(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"})
        assert res.returncode == 0
        assert "AWS_SECRET_ACCESS_KEY" not in _parse_env(res.stdout)

    def test_aws_session_token_stripped(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"AWS_SESSION_TOKEN": "FQoGZXIvYXdzEJr..."})
        assert res.returncode == 0
        assert "AWS_SESSION_TOKEN" not in _parse_env(res.stdout)

    def test_gh_token_stripped(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"GH_TOKEN": "ghp_s3cr3t"})
        assert res.returncode == 0
        assert "GH_TOKEN" not in _parse_env(res.stdout)

    def test_anthropic_api_key_stripped(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"ANTHROPIC_API_KEY": "sk-ant-api03-secret"})
        assert res.returncode == 0
        assert "ANTHROPIC_API_KEY" not in _parse_env(res.stdout)

    def test_openai_api_key_stripped(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"OPENAI_API_KEY": "sk-proj-secret"})
        assert res.returncode == 0
        assert "OPENAI_API_KEY" not in _parse_env(res.stdout)

    def test_database_url_stripped(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"DATABASE_URL": "postgres://user:pass@host/db"})
        assert res.returncode == 0
        assert "DATABASE_URL" not in _parse_env(res.stdout)

    def test_npm_token_stripped(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"NPM_TOKEN": "npm_abc123"})
        assert res.returncode == 0
        assert "NPM_TOKEN" not in _parse_env(res.stdout)

    def test_multiple_credentials_all_stripped(self, tmp_path: Path) -> None:
        res = _run(
            tmp_path,
            extra_env={
                "AWS_ACCESS_KEY_ID": "AKIA...",
                "GH_TOKEN": "ghp_...",
                "ANTHROPIC_API_KEY": "sk-ant-...",
            },
        )
        assert res.returncode == 0
        env = _parse_env(res.stdout)
        assert "AWS_ACCESS_KEY_ID" not in env
        assert "GH_TOKEN" not in env
        assert "ANTHROPIC_API_KEY" not in env


# ---------------------------------------------------------------------------
# passthrough of whitelisted variables
# ---------------------------------------------------------------------------


class TestPassthrough:
    def test_home_passes_through(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"HOME": "/home/testuser"})
        assert res.returncode == 0
        assert _parse_env(res.stdout).get("HOME") == "/home/testuser"

    def test_path_passes_through(self, tmp_path: Path) -> None:
        res = _run(tmp_path)
        assert res.returncode == 0
        assert "PATH" in _parse_env(res.stdout)

    def test_user_passes_through(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"USER": "myuser"})
        assert res.returncode == 0
        assert _parse_env(res.stdout).get("USER") == "myuser"

    def test_shell_passes_through(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"SHELL": "/bin/zsh"})
        assert res.returncode == 0
        assert _parse_env(res.stdout).get("SHELL") == "/bin/zsh"

    def test_lang_passes_through(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"LANG": "en_GB.UTF-8"})
        assert res.returncode == 0
        assert _parse_env(res.stdout).get("LANG") == "en_GB.UTF-8"

    def test_term_passes_through(self, tmp_path: Path) -> None:
        res = _run(tmp_path, extra_env={"TERM": "screen-256color"})
        assert res.returncode == 0
        assert _parse_env(res.stdout).get("TERM") == "screen-256color"


# ---------------------------------------------------------------------------
# CLAUDE_ISO_ALLOW explicit injection
# ---------------------------------------------------------------------------


class TestClaudeIsoAllow:
    def test_allow_single_var(self, tmp_path: Path) -> None:
        res = _run(
            tmp_path,
            extra_env={
                "CLAUDE_ISO_ALLOW": "GH_TOKEN",
                "GH_TOKEN": "ghp_explicit",
            },
        )
        assert res.returncode == 0
        assert _parse_env(res.stdout).get("GH_TOKEN") == "ghp_explicit"

    def test_allow_multiple_vars(self, tmp_path: Path) -> None:
        res = _run(
            tmp_path,
            extra_env={
                "CLAUDE_ISO_ALLOW": "GH_TOKEN AWS_PROFILE",
                "GH_TOKEN": "ghp_explicit",
                "AWS_PROFILE": "read-only",
            },
        )
        assert res.returncode == 0
        env = _parse_env(res.stdout)
        assert env.get("GH_TOKEN") == "ghp_explicit"
        assert env.get("AWS_PROFILE") == "read-only"

    def test_allow_does_not_pass_unlisted_credentials(self, tmp_path: Path) -> None:
        """CLAUDE_ISO_ALLOW for GH_TOKEN doesn't accidentally pass other secrets."""
        res = _run(
            tmp_path,
            extra_env={
                "CLAUDE_ISO_ALLOW": "GH_TOKEN",
                "GH_TOKEN": "ghp_explicit",
                "ANTHROPIC_API_KEY": "sk-ant-secret",
            },
        )
        assert res.returncode == 0
        env = _parse_env(res.stdout)
        assert env.get("GH_TOKEN") == "ghp_explicit"
        assert "ANTHROPIC_API_KEY" not in env


# ---------------------------------------------------------------------------
# error / edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_missing_claude_exits_127(self, tmp_path: Path) -> None:
        """When 'claude' is not on PATH the wrapper exits 127."""
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            env={
                "PATH": str(tmp_path),  # tmp_path has no claude binary
                "HOME": "/tmp",
                "USER": "testuser",
                "SHELL": "/bin/sh",
            },
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 127
        assert "not found on PATH" in result.stderr

    def test_isolation_banner_on_stderr(self, tmp_path: Path) -> None:
        res = _run(tmp_path)
        assert res.returncode == 0
        assert "[claude-iso] running in isolated env" in res.stderr

    def test_no_credential_leakage_into_env(self, tmp_path: Path) -> None:
        """Sanity check: the complete env output contains no credential-shaped values."""
        creds = {
            "AWS_ACCESS_KEY_ID": "AKIA_LEAK_TEST",
            "GH_TOKEN": "ghp_LEAK_TEST",
            "ANTHROPIC_API_KEY": "sk-ant-LEAK_TEST",
        }
        res = _run(tmp_path, extra_env=creds)
        assert res.returncode == 0
        # None of the secret values should appear in the captured output
        for val in creds.values():
            assert val not in res.stdout
