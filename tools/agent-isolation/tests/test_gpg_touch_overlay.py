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

"""Tests for gpg-touch-overlay.sh.

The hook reads a JSON tool-use payload on stdin and decides whether the
command about to run could produce a signature. ``MAGPIE_GPG_TOUCH_DRY_RUN``
makes ``arm`` print its decision instead of spawning a watcher, so the
matcher is exercisable with no X display and nothing left running.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "gpg-touch-overlay.sh"


def _arm(command: str) -> str:
    env = {**os.environ, "MAGPIE_GPG_TOUCH_DRY_RUN": "1"}
    result = subprocess.run(
        ["bash", str(SCRIPT), "arm"],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x'",
        "git commit --amend --no-edit",
        "git -C /some/repo commit -m 'x'",
        "cd /tmp/repo && git commit -m 'x'",
        "git tag -s v1.0.0 -m 'release'",
        "git rebase --continue",
        "git cherry-pick abc1234",
        "git merge --no-ff feature",
    ],
)
def test_arms_for_commands_that_can_sign(command: str) -> None:
    assert _arm(command) == "arm"


@pytest.mark.parametrize(
    "command",
    [
        "git status --short",
        "git log --oneline -5",
        "git diff HEAD",
        "ls -la",
        "echo 'committing to the plan'",
        "grep -r commit .",
    ],
)
def test_stays_quiet_for_commands_that_cannot_sign(command: str) -> None:
    assert _arm(command) == ""


def test_payload_without_a_command_is_ignored() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "arm"],
        input=json.dumps({"tool_input": {}}),
        capture_output=True,
        text=True,
        env={**os.environ, "MAGPIE_GPG_TOUCH_DRY_RUN": "1"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_disarm_is_silent_when_nothing_is_armed(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "disarm"],
        capture_output=True,
        text=True,
        env={**os.environ, "XDG_RUNTIME_DIR": str(tmp_path)},
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_unknown_mode_is_rejected() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "wibble"], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "arm|disarm" in result.stderr


def test_gi_python_only_reports_an_interpreter_that_can_import_gi() -> None:
    """Whatever the resolver picks must actually be able to import gi.

    `python3` alone is not a reliable probe: a Homebrew, pyenv or asdf
    python ahead of the system one on PATH has no PyGObject, while a
    distro's python3-gi is bound to /usr/bin/python3. Probing only the
    PATH python there reports "no PyGObject" while a working gi sits one
    path away, and the overlay silently degrades to the zenity box.
    """
    result = subprocess.run(
        ["bash", str(SCRIPT), "_gi_python"], capture_output=True, text=True
    )
    if result.returncode != 0:
        assert result.stdout.strip() == ""
        pytest.skip("no interpreter on this machine can import gi")

    interpreter = result.stdout.strip()
    assert interpreter
    probe = subprocess.run([interpreter, "-c", "import gi"], capture_output=True)
    assert probe.returncode == 0, f"{interpreter} was selected but cannot import gi"
