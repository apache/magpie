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

"""Tests for the Kiro entry point of agent-iso.sh (`kiro-iso`).

Same strategy as ``test_opencode_iso.py``, with one Kiro-specific wrinkle:
the harness is invoked as ``kiro`` but ships the ``kiro-cli`` binary, so the
wrapper normalises the name. The fake binary is therefore ``kiro-cli``, and
the banner/error use ``kiro-cli-iso``. Verifies the clean-env strip and that
the Claude-only ``--settings`` injection is not applied.

(The bubblewrap OS sandbox layer is not exercised here — it is unavailable in
this environment; this test covers the ``env -i`` credential-strip launcher,
which is the harness-portable part.)
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "agent-iso.sh"
BASH = shutil.which("bash") or "/bin/bash"


def _make_fake_kiro(tmp_path: Path) -> Path:
    """A fake 'kiro-cli' that prints ARG: lines for its argv, then its env."""
    fake = tmp_path / "kiro-cli"
    fake.write_text('#!/bin/sh\nfor a in "$@"; do echo "ARG:$a"; done\nprintenv\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return tmp_path


def _run_kiro(
    tmp_path: Path,
    extra_env: dict | None = None,
    extra_args: list | None = None,
    via_symlink: bool = False,
) -> subprocess.CompletedProcess:
    bin_dir = _make_fake_kiro(tmp_path)
    env: dict[str, str] = {
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": "/tmp/testhome",
        "USER": "testuser",
        "SHELL": "/bin/sh",
        "TERM": "xterm",
        "LANG": "en_US.UTF-8",
    }
    if not via_symlink:
        # The harness name `kiro` must normalise to the `kiro-cli` binary.
        env["AGENT_ISO_AGENT"] = "kiro"
    if extra_env:
        env.update(extra_env)

    script: Path = SCRIPT
    if via_symlink:
        link = tmp_path / "kiro-iso.sh"
        if not link.exists():
            link.symlink_to(SCRIPT)
        script = link

    return subprocess.run(
        [BASH, str(script)] + (extra_args or []),
        env=env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )


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
    return [
        line[len("ARG:") :] for line in stdout.splitlines() if line.startswith("ARG:")
    ]


class TestKiroAgent:
    def test_launches_kiro_cli_binary(self, tmp_path: Path) -> None:
        res = _run_kiro(tmp_path)
        assert res.returncode == 0
        assert "[kiro-cli-iso] running in isolated env" in res.stderr

    def test_credentials_stripped(self, tmp_path: Path) -> None:
        res = _run_kiro(
            tmp_path,
            extra_env={"GH_TOKEN": "ghp_secret", "ANTHROPIC_API_KEY": "sk-ant-secret"},
        )
        assert res.returncode == 0
        env = _parse_env(res.stdout)
        assert "GH_TOKEN" not in env
        assert "ANTHROPIC_API_KEY" not in env

    def test_passthrough_preserved(self, tmp_path: Path) -> None:
        res = _run_kiro(tmp_path, extra_env={"HOME": "/home/testuser"})
        assert res.returncode == 0
        assert _parse_env(res.stdout).get("HOME") == "/home/testuser"

    def test_no_claude_settings_injection(self, tmp_path: Path) -> None:
        res = _run_kiro(tmp_path, extra_args=["chat", "--no-interactive", "hello"])
        assert res.returncode == 0
        argv = _argv(res.stdout)
        assert "--settings" not in argv
        assert argv == ["chat", "--no-interactive", "hello"]

    def test_symlink_name_selects_kiro(self, tmp_path: Path) -> None:
        res = _run_kiro(tmp_path, via_symlink=True)
        assert res.returncode == 0
        assert "[kiro-cli-iso] running in isolated env" in res.stderr

    def test_missing_kiro_exits_127(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            env={
                "PATH": str(tmp_path),  # no kiro-cli binary here
                "HOME": "/tmp",
                "USER": "testuser",
                "SHELL": "/bin/sh",
                "AGENT_ISO_AGENT": "kiro",
            },
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 127
        assert "kiro-cli-iso: 'kiro-cli' not found" in result.stderr
