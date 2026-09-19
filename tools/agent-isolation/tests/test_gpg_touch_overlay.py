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
import shutil
import subprocess
import time
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


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True
    )


@pytest.fixture
def process_named(tmp_path):
    """Start a sleeping process under a chosen name, and clean it up.

    The detector matches on the process name, so the only way to exercise
    it is to give a harmless process the name it looks for.
    """
    started = []

    def start(name: str) -> None:
        # A symlink, not a copy: the process name follows the path it was
        # exec'd under either way, and copying a system binary out of its
        # place gets the copy killed on a code-signing platform.
        binary = tmp_path / name
        binary.symlink_to(shutil.which("sleep"))
        started.append(subprocess.Popen([str(binary), "30"]))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if subprocess.run(["pgrep", "-x", name]).returncode == 0:
                return
            time.sleep(0.05)
        pytest.skip(f"pgrep never saw {name}")

    yield start

    for proc in started:
        proc.kill()
        proc.wait()


@pytest.mark.skipif(shutil.which("pgrep") is None, reason="needs pgrep")
def test_signing_in_flight_sees_an_ssh_keygen_signature(process_named) -> None:
    """`gpg.format=ssh` signs through gpg-agent without ever running gpg."""
    process_named("ssh-keygen")
    assert _run("_signing_in_flight").returncode == 0


@pytest.mark.skipif(shutil.which("pgrep") is None, reason="needs pgrep")
def test_signing_in_flight_matches_the_whole_process_name(process_named) -> None:
    process_named("ssh-keygenx")
    assert _run("_signing_in_flight").returncode != 0


def test_spawn_session_makes_the_backgrounded_pid_the_group_leader() -> None:
    """arm records `$!` as the group disarm later kills.

    So the backgrounded command has to *become* the session leader under
    that same pid. Anything that leaves a shell in between — a wrapper
    function, say — records a pid that leads no group, and disarm then
    kills nothing and leaves the window on screen.
    """
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'"{SCRIPT}" _spawn_session sleep 5 & '
            'pid=$!; sleep 0.3; echo "$pid $(ps -o pgid= -p "$pid")"; '
            "kill -- -\"$pid\" 2>/dev/null",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    pid, pgid = result.stdout.split()
    assert pid == pgid


def test_tk_python_reports_an_interpreter_that_can_start_tk() -> None:
    """Importing tkinter is not enough — the macOS window calls Tk().

    A uv or pyenv python ships the module without the Tcl/Tk framework
    behind it, so an import-only probe hands back an interpreter that
    dies the moment it tries to draw.
    """
    result = _run("_tk_python")
    if result.returncode != 0:
        pytest.skip("no python that can start Tk on this host")
    interpreter = result.stdout.strip()
    started = subprocess.run(
        [
            interpreter,
            "-c",
            "import tkinter; t = tkinter.Tk(); t.withdraw(); t.destroy()",
        ],
        capture_output=True,
    )
    assert started.returncode == 0, started.stderr
