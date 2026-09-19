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
import socket
import subprocess
import tempfile
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
        # The subcommand ended by a shell separator, not by whitespace.
        "git commit; echo done",
        "(git commit)",
        "git commit|tee log",
        "git commit&&echo done",
        # Transport over an ssh remote asks the key for its authentication
        # touch before anything is transferred.
        "git pull",
        "git pull --rebase upstream main",
        "git fetch --all --prune",
        "git push origin HEAD",
        "git clone git@github.com:apache/magpie.git",
        "git ls-remote origin",
        "git remote update",
        "git submodule update --init",
    ],
)
def test_arms_for_commands_that_can_reach_the_key(command: str) -> None:
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


def test_agent_sockets_include_ssh_auth_sock() -> None:
    """The system ssh-agent counts too, not only gpg-agent's socket."""
    result = subprocess.run(
        ["bash", str(SCRIPT), "_agent_sockets"],
        capture_output=True,
        text=True,
        env={**os.environ, "SSH_AUTH_SOCK": "/nonexistent/agent.sock"},
    )
    assert result.returncode == 0
    listed = result.stdout.split()
    assert "/nonexistent/agent.sock" in listed
    assert len(listed) == len(set(listed)), "socket paths are listed once each"


def _agent_socket_rows(path: str) -> int:
    result = subprocess.run(
        ["bash", str(SCRIPT), "_agent_socket_rows", path],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip())


def test_agent_socket_rows_follow_the_connections_held_open() -> None:
    """A request that waits on the key holds its agent connection open.

    ssh and `ssh-keygen -Y sign` connect to the agent, ask, and close
    once answered; while the key waits for a touch the connection stays.
    The watcher reads that as rows in the kernel's socket table for the
    agent's path, one per accepted connection, against a baseline.
    """
    # A short directory: sun_path is 104 bytes on macOS and pytest's
    # tmp_path can be longer than that.
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "agent.sock")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(path)
        except PermissionError:
            # The sandbox lets a command connect to the listed agent
            # sockets and nothing else; it cannot listen on one of its own.
            server.close()
            pytest.skip("cannot create a unix socket here")
        server.listen(1)
        try:
            baseline = _agent_socket_rows(path)
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(path)
            accepted, _ = server.accept()
            try:
                assert _agent_socket_rows(path) > baseline
            finally:
                client.close()
                accepted.close()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and _agent_socket_rows(path) > baseline:
                time.sleep(0.1)
            assert _agent_socket_rows(path) == baseline
        finally:
            server.close()


def test_agent_socket_rows_without_sockets_is_zero() -> None:
    assert _agent_socket_rows("") == 0


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

    def start(name: str, seconds: float = 30) -> None:
        # A symlink, not a copy: the process name follows the path it was
        # exec'd under either way, and copying a system binary out of its
        # place gets the copy killed on a code-signing platform.
        binary = tmp_path / name
        binary.symlink_to(shutil.which("sleep"))
        started.append(subprocess.Popen([str(binary), str(seconds)]))
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


@pytest.mark.skipif(shutil.which("pgrep") is None, reason="needs pgrep")
def test_watcher_outlives_a_signature_that_ends(process_named) -> None:
    """One signature ending is not the end of the watch.

    A hook may run a look-alike before git signs at all — this very
    suite starts a process named ssh-keygen under the pre-commit hook —
    and a rebase signs every commit it replays. A watcher that left with
    the first one would be gone when the real signature blocked.
    """
    watcher = subprocess.Popen(["bash", str(SCRIPT), "_watch"])
    try:
        # Shorter than SHOW_DELAY, so nothing is drawn on a host with a
        # display.
        process_named("ssh-keygen", seconds=1)
        time.sleep(2.5)
        assert watcher.poll() is None, "the watcher left with the first signature"
    finally:
        watcher.terminate()
        watcher.wait(timeout=5)


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
    fields = result.stdout.split()
    if len(fields) < 2:
        # ps could not report on the spawned process: a sandbox that hides
        # other processes, as the framework's own does for the pre-commit
        # run. Nothing to assert on, and nothing wrong with the script.
        pytest.skip("ps cannot see the spawned process here")
    pid, pgid = fields
    assert pid == pgid


def test_tk_python_reports_a_resolved_interpreter_with_a_current_tk() -> None:
    """Importing tkinter is not enough — the macOS window calls Tk().

    A uv or pyenv python ships the module without the Tcl/Tk framework
    behind it, so an import-only probe hands back an interpreter that
    dies the moment it tries to draw. Tcl also finds its own library
    relative to the executable path without following symlinks, so the
    `python3` symlink uv puts on PATH fails where the interpreter behind
    it works: the probe has to report the resolved path. And Apple's
    Tk 8.5 starts and then draws nothing for this window, so 8.6 is the
    floor.
    """
    result = _run("_tk_python")
    if result.returncode != 0:
        pytest.skip("no python with Tk 8.6 on this host")
    interpreter = result.stdout.strip()
    assert Path(interpreter).resolve() == Path(interpreter), (
        "the probe must report the resolved path"
    )
    started = subprocess.run(
        [
            interpreter,
            "-c",
            "import tkinter; t = tkinter.Tk(); "
            "print(t.tk.call('info', 'patchlevel')); t.withdraw(); t.destroy()",
        ],
        capture_output=True,
        text=True,
    )
    assert started.returncode == 0, started.stderr
    major, minor = (int(p) for p in started.stdout.strip().split(".")[:2])
    assert (major, minor) >= (8, 6)


# ---------------------------------------------------------------- wrap ---
#
# `wrap` is the entry point git uses directly — as `gpg.ssh.program`,
# `gpg.program` or `core.sshCommand` — so that a commit or push made from
# a terminal, where no hook of the agent's runs, gets the window too. The
# dry-run seam skips the display probe (there is no display under the
# pre-commit sandbox) but still starts a real watcher, so its lifetime
# can be observed. Every wrapped program here ends well inside
# SHOW_DELAY, so nothing is drawn on a host that has a display.


def _wrap_env(runtime_root: Path) -> dict[str, str]:
    # A terminal's environment, not an agent's and not a git hook's: this
    # suite runs under the agent's own pre-commit hook too, where
    # CLAUDECODE=1 would make the wrapper stand aside and every test below
    # see no watcher, and where git exports GIT_INDEX_FILE / GIT_DIR to
    # the hook -- inherited by the scratch repository below, those point
    # its `git init` and `git commit` at the real repository.
    env = {
        k: v
        for k, v in os.environ.items()
        if k != "CLAUDECODE" and not k.startswith("GIT_")
    }
    return {
        **env,
        "XDG_RUNTIME_DIR": str(runtime_root),
        "MAGPIE_GPG_TOUCH_DRY_RUN": "1",
    }


def _pid_file(runtime_root: Path) -> Path:
    return runtime_root / "magpie-gpg-touch" / "watcher.pid"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_wrap_returns_the_wrapped_programs_status(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "wrap", "sh", "-c", "exit 7"],
        capture_output=True,
        text=True,
        env=_wrap_env(tmp_path),
    )
    assert result.returncode == 7, result.stderr


def test_wrap_tears_the_watcher_down_with_the_program(tmp_path: Path) -> None:
    """The watcher lives exactly as long as the wrapped program."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "wrap",
            "sh",
            "-c",
            'cat "$XDG_RUNTIME_DIR/magpie-gpg-touch/watcher.pid"',
        ],
        capture_output=True,
        text=True,
        env=_wrap_env(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    watcher = int(result.stdout.strip())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _alive(watcher):
        time.sleep(0.05)
    assert not _alive(watcher), "the watcher outlived the program it was wrapping"
    assert not _pid_file(tmp_path).exists()


def test_wrap_symlink_name_selects_the_program(tmp_path: Path) -> None:
    """`gpg.ssh.program` is exec'd as one path, not shell-split.

    So the argument-free form of `wrap <program>` is a symlink named
    `gpg-touch-wrap-<program>`, and the script reads the program to wrap
    from its own name.
    """
    link = tmp_path / "gpg-touch-wrap-true"
    link.symlink_to(SCRIPT)
    result = subprocess.run(
        [str(link)], capture_output=True, text=True, env=_wrap_env(tmp_path)
    )
    assert result.returncode == 0, result.stderr
    assert not _pid_file(tmp_path).exists()


def test_wrap_leaves_a_watcher_somebody_else_armed_alone(tmp_path: Path) -> None:
    """A hook's watcher for the enclosing command is not this wrapper's to kill.

    An agent-run `git commit` has the PreToolUse hook's watcher up already
    when git reaches the signing program; the wrapper neither starts a
    second one nor tears that one down when the signature is done.
    """
    other = subprocess.Popen(["sleep", "30"])
    try:
        pid_file = _pid_file(tmp_path)
        pid_file.parent.mkdir(parents=True)
        pid_file.write_text(f"{other.pid}\n")
        result = subprocess.run(
            ["bash", str(SCRIPT), "wrap", "true"],
            capture_output=True,
            text=True,
            env=_wrap_env(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        assert pid_file.read_text().strip() == str(other.pid)
        assert other.poll() is None, "the other watcher was killed"
    finally:
        other.kill()
        other.wait()


def test_wrap_stands_aside_inside_an_agent_session(tmp_path: Path) -> None:
    """One signature, one window: in an agent session the hook owns it.

    The PreToolUse hook armed a watcher outside the sandbox before the
    command started; a second one from the wrapper, running inside it,
    would be a second window wherever the sandbox lets it draw. Claude
    Code marks its Bash with CLAUDECODE=1, and the wrapper only runs the
    program there.
    """
    result = subprocess.run(
        ["bash", str(SCRIPT), "wrap", "sh", "-c", "exit 3"],
        capture_output=True,
        text=True,
        env={**_wrap_env(tmp_path), "CLAUDECODE": "1"},
    )
    assert result.returncode == 3, result.stderr
    assert not (tmp_path / "magpie-gpg-touch").exists()


@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="needs ssh-keygen")
def test_wrap_passes_a_verify_call_straight_through(tmp_path: Path) -> None:
    """`git log --show-signature` runs the signing program once per commit.

    Those calls never reach the key, so they get no watcher and no
    display probe — `wrap` execs the program at once.
    """
    result = subprocess.run(
        ["bash", str(SCRIPT), "wrap", "ssh-keygen", "-Y", "verify"],
        capture_output=True,
        text=True,
        env=_wrap_env(tmp_path),
    )
    assert result.returncode != 0
    assert "verify" in result.stderr, "ssh-keygen itself did not run"
    assert not (tmp_path / "magpie-gpg-touch").exists()


@pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("ssh-keygen") is None,
    reason="needs git and ssh-keygen",
)
def test_git_signs_a_commit_through_the_wrapper(tmp_path: Path) -> None:
    """End to end: `gpg.ssh.program` names the symlink and git commits.

    A software key stands in for the hardware one, so the real
    `ssh-keygen -Y sign` signs without a touch. A shim ahead of it on
    PATH holds the signature for a moment — long enough for the watcher
    to see it in flight, short of SHOW_DELAY so nothing is drawn.
    """
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    link = scripts / "gpg-touch-wrap-ssh-keygen"
    link.symlink_to(SCRIPT)

    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    real_ssh_keygen = shutil.which("ssh-keygen")
    shim = shim_dir / "ssh-keygen"
    shim.write_text(f'#!/bin/sh\nsleep 1\nexec "{real_ssh_keygen}" "$@"\n')
    shim.chmod(0o755)

    key = tmp_path / "key"
    subprocess.run(
        [real_ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **_wrap_env(tmp_path),
        "MAGPIE_GPG_TOUCH_DEBUG": "1",
        "PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, env=env
        )

    assert git("init", "-q").returncode == 0
    for key_name, value in [
        ("gpg.format", "ssh"),
        ("user.signingkey", str(key)),
        ("commit.gpgsign", "true"),
        ("gpg.ssh.program", str(link)),
    ]:
        assert git("config", key_name, value).returncode == 0

    commit = git("commit", "-q", "--allow-empty", "-m", "signed through the wrapper")
    assert commit.returncode == 0, commit.stderr

    shown = git("cat-file", "-p", "HEAD")
    assert "gpgsig " in shown.stdout, "the commit was not signed"

    assert not _pid_file(tmp_path).exists()
    log = tmp_path / "magpie-gpg-touch" / "watcher.log"
    assert log.exists(), "no watcher ran for the signature"
    assert "signing_in_flight" in log.read_text()
