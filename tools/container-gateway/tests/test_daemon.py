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

"""Daemon plumbing: paths, guards, idle exit, status and stop.

Threat model exercised throughout this file: the daemon runs OUTSIDE the
sandbox with the operator's own privileges, while the sandboxed agent
can create, delete and symlink anything under the project tree,
including ``.apache-magpie-local/run/``. Every guard test below plants
exactly the kind of hostile filesystem state that threat model implies
and checks the guard refuses it -- no bind needed for any of them.

No ``pytest-asyncio`` in the ``magpie-dev`` dependency group, so each
async scenario is a plain ``def`` test driving its coroutine through the
``run()`` helper, exactly as ``test_http.py`` and ``test_relay.py`` do.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Coroutine, Iterator
from pathlib import Path
from typing import Any, TypeVar

import pytest

from container_gateway import __main__ as cli
from container_gateway import daemon
from container_gateway.backends import Backend

from .fakebackend import FakeBackend

SRC = Path(__file__).resolve().parents[1] / "src"

_T = TypeVar("_T")


def run(coro: Coroutine[Any, Any, _T]) -> _T:
    """Drive a coroutine to completion without pytest-asyncio."""
    return asyncio.run(coro)


def _ns(project: Path, run_dir: Path, **extra: Any) -> argparse.Namespace:
    """A minimal argparse.Namespace for calling cmd_serve/cmd_stop/cmd_status directly."""
    base = {"project": project, "run_dir": run_dir, "pid_file": None}
    base.update(extra)
    return argparse.Namespace(**base)


@pytest.fixture
def short_run_dir() -> Iterator[Path]:
    """A run directory short enough to hold a unix-socket path.

    ``pytest``'s own ``tmp_path`` fixture nests under
    ``pytest-of-<user>/pytest-<n>/<test-name>/`` inside ``$TMPDIR``, which
    in this sandboxed dev environment is already long enough on its own
    to blow the ~103-byte ``sun_path`` limit before ``run_dir`` even adds
    ``podman.sock``. ``tempfile.mkdtemp()`` sits directly under
    ``$TMPDIR`` with none of that nesting, so it stays short everywhere
    ``tmp_path`` might not. It is also already 0700 and owned by us, so
    it satisfies ``check_run_dir``'s "custom run-dir" branch as-is.
    """
    d = Path(tempfile.mkdtemp(prefix="cg-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


class _RealSocketBackend:
    """A ``FakeBackend`` served over a real filesystem unix socket.

    ``tests/fakebackend.FakeBackend`` only ever hands out in-process
    ``socket.socketpair()`` connections (the sandbox refuses ``bind()``,
    so it never listens on a path) -- but ``daemon.run()`` needs a real
    socket path to hand to ``unix_connector`` for a ``Backend``. This
    thin wrapper does the one real bind these daemon tests need, so it
    can hit the same ``PermissionError`` the sandbox raises and skip
    exactly like every other bind-touching test in this suite.
    """

    def __init__(self, socket_path: Path) -> None:
        self.socket = socket_path
        self._fake = FakeBackend()
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_unix_server(self._fake._handle, path=str(self.socket))

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()


# --------------------------------------------------------------- paths


def test_paths_and_socket_length(tmp_path: Path) -> None:
    p = daemon.paths(tmp_path)
    assert p["podman"].name == "podman.sock" and p["docker"].name == "docker.sock"
    # A literal short path, not tmp_path: with TMPDIR unset, tmp_path's
    # pytest-of-<user>/pytest-<n>/<test-name>/ nesting is already long
    # enough to exceed the ~103-byte sun_path limit on its own, and
    # check_socket_path only measures byte length.
    daemon.check_socket_path(Path("/tmp/ok.sock"))
    with pytest.raises(SystemExit) as exc:
        daemon.check_socket_path(Path("/" + "x" * 120 + "/podman.sock"))
    assert exc.value.code == 2


# ------------------------------------------------ C2: run dir / symlinks


def test_check_run_dir_default_layout_creates_both_dirs_0700(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    project_root.mkdir()
    run_dir = project_root / ".apache-magpie-local" / "run"
    daemon.check_run_dir(run_dir, project_root)
    assert (project_root / ".apache-magpie-local").stat().st_mode & 0o777 == 0o700
    assert run_dir.stat().st_mode & 0o777 == 0o700


def test_check_run_dir_refuses_world_writable_existing_dir(tmp_path: Path) -> None:
    project_root = tmp_path
    run_dir = tmp_path / "custom-run"
    daemon.check_run_dir(run_dir, project_root)
    assert run_dir.stat().st_mode & 0o777 == 0o700
    run_dir.chmod(0o777)
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(run_dir, project_root)
    assert exc.value.code == 2


def test_check_run_dir_refuses_symlinked_run(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    magpie_local = project_root / ".apache-magpie-local"
    magpie_local.mkdir(parents=True, mode=0o700)
    evil = tmp_path / "evil"
    evil.mkdir()
    (magpie_local / "run").symlink_to(evil)
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(magpie_local / "run", project_root)
    assert exc.value.code == 2


def test_check_run_dir_refuses_symlinked_apache_magpie_local(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    project_root.mkdir()
    evil = tmp_path / "evil"
    evil.mkdir()
    (project_root / ".apache-magpie-local").symlink_to(evil)
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(project_root / ".apache-magpie-local" / "run", project_root)
    assert exc.value.code == 2


def test_check_run_dir_refuses_symlinked_custom_run_dir(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    project_root.mkdir()
    evil = tmp_path / "evil"
    evil.mkdir()
    custom = tmp_path / "custom-run"
    custom.symlink_to(evil)
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(custom, project_root)
    assert exc.value.code == 2


# ------------------------------------------- D5: missing ancestors refuse


def test_check_run_dir_refuses_missing_project_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "does-not-exist"
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(missing_root / ".apache-magpie-local" / "run", missing_root)
    assert exc.value.code == 2


def test_check_run_dir_refuses_missing_custom_run_dir_parent(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    project_root.mkdir()
    missing_parent_run_dir = tmp_path / "does-not-exist" / "run"
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(missing_parent_run_dir, project_root)
    assert exc.value.code == 2


def test_validate_run_dir_false_when_project_root_missing(tmp_path: Path) -> None:
    missing_root = tmp_path / "does-not-exist"
    assert daemon.validate_run_dir(missing_root / ".apache-magpie-local" / "run", missing_root) is False


def test_validate_run_dir_false_when_custom_parent_missing(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    project_root.mkdir()
    missing_parent_run_dir = tmp_path / "does-not-exist" / "run"
    assert daemon.validate_run_dir(missing_parent_run_dir, project_root) is False


# --------------------------------------- D6: lstat-then-mkdir race safety


def test_ensure_owned_private_dir_handles_mkdir_race_with_planted_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "custom-run"
    evil = tmp_path / "evil"
    evil.mkdir()
    real_mkdir = Path.mkdir

    def racy_mkdir(self: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False) -> None:
        if self == target:
            target.symlink_to(evil)  # someone (or something) won the race and planted a symlink
            raise FileExistsError(f"[Errno 17] File exists: '{target}'")
        real_mkdir(self, mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", racy_mkdir)
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(target, tmp_path)
    assert exc.value.code == 2


# --------------------------------------------------- C2: socket guards


def test_check_socket_type_refuses_non_socket(tmp_path: Path) -> None:
    p = tmp_path / "podman.sock"
    p.write_text("not a socket")
    with pytest.raises(SystemExit) as exc:
        daemon.check_socket_type(p)
    assert exc.value.code == 2


def test_check_socket_type_allows_missing_path(tmp_path: Path) -> None:
    daemon.check_socket_type(tmp_path / "missing.sock")  # nothing there yet: fine


# ------------------------------------------------------ C2: pid / log fd


def test_acquire_pid_lock_refuses_symlink(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.pid"
    target.write_text("")
    link = tmp_path / "container-gateway.pid"
    link.symlink_to(target)
    with pytest.raises(SystemExit) as exc:
        daemon.acquire_pid_lock(link)
    assert exc.value.code == 2


def test_probe_pid_lock_refuses_symlink(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.pid"
    target.write_text("")
    link = tmp_path / "container-gateway.pid"
    link.symlink_to(target)
    with pytest.raises(SystemExit) as exc:
        daemon.probe_pid_lock(link)
    assert exc.value.code == 2


def test_probe_pid_lock_not_running_when_run_dir_absent(tmp_path: Path) -> None:
    never_created = tmp_path / "never" / "container-gateway.pid"
    assert daemon.probe_pid_lock(never_created) == (False, None)


def test_open_log_fd_refuses_symlink(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.log"
    target.write_text("")
    link = tmp_path / "container-gateway.log"
    link.symlink_to(target)
    with pytest.raises(SystemExit) as exc:
        cli._open_log_fd(link)
    assert exc.value.code == 2


# --------------------- D2: acquire_pid_lock never blanks a live pid file


def test_acquire_pid_lock_does_not_blank_a_live_daemons_pid_file(tmp_path: Path) -> None:
    pid_file = tmp_path / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, 0)
        os.write(fd, b"4242\n")
        os.fsync(fd)
        second = daemon.acquire_pid_lock(pid_file)
        assert second is None
        assert pid_file.read_text() == "4242\n"
    finally:
        os.close(fd)


# ------------------------------------- D1: status/stop bypassed check_run_dir


def test_pid_file_is_trustworthy_none_when_missing(tmp_path: Path) -> None:
    assert daemon.pid_file_is_trustworthy(tmp_path / "container-gateway.pid") is None


def test_pid_file_is_trustworthy_true_for_a_lock_created_file(tmp_path: Path) -> None:
    pid_file = tmp_path / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        assert daemon.pid_file_is_trustworthy(pid_file) is True
    finally:
        os.close(fd)


def test_pid_file_is_trustworthy_false_for_symlink(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.pid"
    target.write_text("4242\n")
    target.chmod(0o600)
    link = tmp_path / "container-gateway.pid"
    link.symlink_to(target)
    assert daemon.pid_file_is_trustworthy(link) is False


def test_pid_file_is_trustworthy_false_for_wrong_mode(tmp_path: Path) -> None:
    pid_file = tmp_path / "container-gateway.pid"
    pid_file.write_text("4242\n")
    pid_file.chmod(0o644)
    assert daemon.pid_file_is_trustworthy(pid_file) is False


def test_cli_status_refuses_symlinked_run_dir(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    magpie_local = project_root / ".apache-magpie-local"
    magpie_local.mkdir(parents=True, mode=0o700)
    evil = tmp_path / "evil"
    evil.mkdir()
    (magpie_local / "run").symlink_to(evil)
    with pytest.raises(SystemExit) as exc:
        cli.cmd_status(_ns(project_root, magpie_local / "run"))
    assert exc.value.code == 2


def test_cli_stop_refuses_symlinked_run_dir_without_signalling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "proj"
    magpie_local = project_root / ".apache-magpie-local"
    magpie_local.mkdir(parents=True, mode=0o700)
    evil = tmp_path / "evil"
    evil.mkdir()
    (magpie_local / "run").symlink_to(evil)
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
    with pytest.raises(SystemExit) as exc:
        cli.cmd_stop(_ns(project_root, magpie_local / "run"))
    assert exc.value.code == 2
    assert calls == []


def test_cli_stop_refuses_pid_file_with_wrong_mode(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    pid_file.write_text("4242\n")
    pid_file.chmod(0o644)
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
    with pytest.raises(SystemExit) as exc:
        cli.cmd_stop(_ns(tmp_path, short_run_dir))
    assert exc.value.code == 2
    assert calls == []


def test_cli_status_treats_wrong_mode_pid_file_as_not_running(
    tmp_path: Path, short_run_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    pid_file.write_text("4242\n")
    pid_file.chmod(0o644)
    rc = cli.cmd_status(_ns(tmp_path, short_run_dir))
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["running"] is False
    # Untrustworthy content is left alone, not deleted, by `status`.
    assert pid_file.exists()


# -------------------------------- D4: stop verifies the signalled process


def test_cli_stop_refuses_when_process_does_not_look_like_gateway(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        monkeypatch.setattr("container_gateway.backends.default_runner", lambda argv: "bash -c sleep 100")
        calls: list[tuple[int, int]] = []
        monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
        rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
        assert calls == []
        assert rc == 1
    finally:
        os.close(fd)


def test_cli_stop_refuses_a_process_that_merely_mentions_the_module_name(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An editor opened on a file named ``container_gateway.py`` is not the gateway.

    A substring check on the ``ps`` line would wrongly treat this as a
    match; the argv-shape check must not.
    """
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        monkeypatch.setattr(
            "container_gateway.backends.default_runner", lambda argv: "vim container_gateway.py"
        )
        calls: list[tuple[int, int]] = []
        monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
        rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
        assert calls == []
        assert rc == 1
    finally:
        os.close(fd)


def test_cli_stop_checks_only_the_first_line_of_ps_output(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gateway-shaped second line must not rescue a non-gateway first line."""
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        monkeypatch.setattr(
            "container_gateway.backends.default_runner",
            lambda argv: "bash -c sleep 100\npython3 -m container_gateway serve --project /x",
        )
        calls: list[tuple[int, int]] = []
        monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
        rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
        assert calls == []
        assert rc == 1
    finally:
        os.close(fd)


def test_cli_stop_signals_when_process_is_the_console_script(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The installed ``container-gateway`` console script is also recognised, not just ``python -m``."""
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    our_pid = os.getpid()
    calls: list[tuple[int, int]] = []
    terminated = False

    def fake_kill(pid: int, sig: int) -> None:
        nonlocal terminated
        calls.append((pid, sig))
        if sig == signal.SIGTERM:
            terminated = True
            os.close(fd)  # simulate the daemon exiting: release the flock
        elif terminated:
            raise ProcessLookupError

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(
        "container_gateway.backends.default_runner",
        lambda argv: "/usr/local/bin/container-gateway serve --project /x",
    )
    rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
    assert rc == 0
    assert (our_pid, signal.SIGTERM) in calls


@pytest.mark.parametrize(
    "command_line",
    [
        "python3 -u -m container_gateway serve --project /x",
        "uv run python -m container_gateway serve --project /x",
    ],
)
def test_cli_stop_signals_a_python_dash_m_invocation_with_extra_argv(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch, command_line: str
) -> None:
    """Interpreter flags (``-u``) and a runner prefix (``uv run``) do not defeat the argv-shape match."""
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    our_pid = os.getpid()
    calls: list[tuple[int, int]] = []
    terminated = False

    def fake_kill(pid: int, sig: int) -> None:
        nonlocal terminated
        calls.append((pid, sig))
        if sig == signal.SIGTERM:
            terminated = True
            os.close(fd)  # simulate the daemon exiting: release the flock
        elif terminated:
            raise ProcessLookupError

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr("container_gateway.backends.default_runner", lambda argv: command_line)
    rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
    assert rc == 0
    assert (our_pid, signal.SIGTERM) in calls


def test_cli_stop_refuses_when_ps_is_unavailable(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        monkeypatch.setattr("container_gateway.backends.default_runner", lambda argv: None)
        calls: list[tuple[int, int]] = []
        monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
        rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
        assert calls == []
        assert rc == 1
    finally:
        os.close(fd)


# --------------------------------------------------------------- C1: pid


@pytest.mark.parametrize("content", ["-1", "0", "1", "abc", "12 34", "99999999999", ""])
def test_read_pid_rejects_unsafe_content(tmp_path: Path, content: str) -> None:
    pid_file = tmp_path / "container-gateway.pid"
    pid_file.write_text(content)
    assert daemon.read_pid(pid_file) is None


def test_read_pid_accepts_a_real_pid(tmp_path: Path) -> None:
    pid_file = tmp_path / "container-gateway.pid"
    pid_file.write_text("42\n")
    assert daemon.read_pid(pid_file) == 42


def test_pid_alive_false_for_pid_le_1() -> None:
    assert daemon.pid_alive(0) is False
    assert daemon.pid_alive(1) is False
    assert daemon.pid_alive(-1) is False


@pytest.mark.parametrize("content", ["-1", "0", "1", "abc", "12 34"])
def test_cli_stop_with_unsafe_pid_file_does_not_signal(
    tmp_path: Path, short_run_dir: Path, content: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    pid_file.write_text(content)
    pid_file.chmod(0o600)  # a trustworthy *file*; the *content* is what's unsafe here
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
    rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
    assert calls == []
    assert rc == 0


def test_cli_stop_does_not_signal_when_lock_held_but_pid_content_poisoned(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live, lock-holding instance whose pid-file *content* was overwritten afterwards.

    ``stop`` must refuse to guess: something is clearly running (the
    lock says so), but nothing safe to signal can be read back out of
    the file.
    """
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, 0)
        os.write(fd, b"-1\n")
        calls: list[tuple[int, int]] = []
        monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
        rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
        assert calls == []
        assert rc == 1
    finally:
        os.close(fd)


# --------------------------------------------- I3+I4: flock single instance


def test_cli_serve_short_circuits_when_lock_already_held(tmp_path: Path, short_run_dir: Path) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        ns = _ns(
            tmp_path,
            short_run_dir,
            daemon=False,
            backend=None,
            egress="off",
            egress_port=8899,
            egress_host=None,
            extra_bind_root=None,
            idle_timeout=5.0,
            backend_timeout=60.0,
            log_level="INFO",
        )
        assert cli.cmd_serve(ns) == 0
        assert not (short_run_dir / "podman.sock").exists()
        assert not (short_run_dir / "docker.sock").exists()
    finally:
        os.close(fd)


def test_cli_status_reports_running_when_lock_held(
    tmp_path: Path, short_run_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    try:
        rc = cli.cmd_status(_ns(tmp_path, short_run_dir))
        out = json.loads(capsys.readouterr().out)
    finally:
        os.close(fd)
    assert rc == 0
    assert out["running"] is True
    assert out["pid"] == os.getpid()
    assert out["serving"] == []  # no sockets actually bound in this test


def test_cli_status_removes_stale_pid_file_when_no_lock_held(
    tmp_path: Path, short_run_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    pid_file.write_text("424242\n")  # a stale pid; nobody holds its lock
    pid_file.chmod(0o600)  # a trustworthy, well-formed pid file -- just stale
    rc = cli.cmd_status(_ns(tmp_path, short_run_dir))
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["running"] is False
    assert out["pid"] is None
    assert not pid_file.exists()


def test_cli_stop_signals_the_pid_and_reports_stopped(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = short_run_dir / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    our_pid = os.getpid()
    calls: list[tuple[int, int]] = []
    terminated = False

    def fake_kill(pid: int, sig: int) -> None:
        nonlocal terminated
        calls.append((pid, sig))
        if sig == signal.SIGTERM:
            terminated = True
            os.close(fd)  # simulate the daemon exiting: release the flock
        elif terminated:
            raise ProcessLookupError

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(
        "container_gateway.backends.default_runner",
        lambda argv: "python3 -m container_gateway serve --project /x",
    )
    rc = cli.cmd_stop(_ns(tmp_path, short_run_dir))
    assert rc == 0
    assert (our_pid, signal.SIGTERM) in calls


def test_cli_stop_when_lock_never_held_is_a_noop(tmp_path: Path, short_run_dir: Path) -> None:
    assert cli.cmd_stop(_ns(tmp_path, short_run_dir)) == 0


def test_cli_stop_prints_a_message_when_project_root_does_not_exist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A --project value that names nothing gets its own message, not the run-directory one."""
    missing_root = tmp_path / "never-served"
    run_dir = missing_root / ".apache-magpie-local" / "run"
    rc = cli.cmd_stop(_ns(missing_root, run_dir))
    out = capsys.readouterr().out
    assert rc == 0
    assert f"no project root at {missing_root}: nothing to stop" in out


def test_cli_stop_prints_a_message_when_no_run_directory_ever_existed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project that exists but was never served must not look identical to "stopped successfully"."""
    project_root = tmp_path / "served-project"
    project_root.mkdir()
    run_dir = project_root / ".apache-magpie-local" / "run"
    rc = cli.cmd_stop(_ns(project_root, run_dir))
    out = capsys.readouterr().out
    assert rc == 0
    assert f"no run directory at {run_dir}: nothing to stop" in out


# ------------------------- D3: unlink the pid file before closing its fd


def test_run_unlinks_pid_file_before_closing_the_lock_fd(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    real_unlink = Path.unlink
    real_close = os.close
    pid_file = short_run_dir / "pid"

    def recording_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == pid_file:
            events.append("unlink")
        real_unlink(self, missing_ok=missing_ok)

    def recording_close(fd: int) -> None:
        events.append("close")
        real_close(fd)

    monkeypatch.setattr(Path, "unlink", recording_unlink)
    monkeypatch.setattr(os, "close", recording_close)

    cfg = daemon.Config(
        tmp_path, short_run_dir, ("podman", "docker"), "off", 8899, None, (), 5.0, "INFO", pid_file
    )

    async def scenario() -> None:
        rc = await daemon.run(cfg, discover_fn=lambda *a, **k: [], platform="Darwin")
        assert rc == 0

    run(scenario())
    assert "unlink" in events
    assert "close" in events
    assert events.index("unlink") < events.index("close")


# ---------------------------------------------------------------- I5


def test_partial_bind_failure_cleans_up_first_socket_and_server(
    tmp_path: Path, short_run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    closed: list[bool] = []

    class _FakeServer:
        def close(self) -> None:
            closed.append(True)

        async def wait_closed(self) -> None:
            return None

    async def fake_serve_unix(path: Path, handler: Any) -> _FakeServer:
        calls.append(path)
        if len(calls) == 2:
            raise OSError("simulated bind failure")
        path.write_text("")  # stand in for "a socket file now exists here"
        return _FakeServer()

    monkeypatch.setattr(daemon, "serve_unix", fake_serve_unix)
    cfg = daemon.Config(
        tmp_path,
        short_run_dir,
        ("podman", "docker"),
        "off",
        8899,
        None,
        (),
        5.0,
        "INFO",
        short_run_dir / "pid",
    )
    found = [Backend("podman", short_run_dir / "upstream.sock", "host.containers.internal")]

    async def scenario() -> None:
        with pytest.raises(OSError, match="simulated bind failure"):
            await daemon.run(cfg, discover_fn=lambda *a, **k: found, platform="Darwin")

    run(scenario())
    assert closed == [True]
    assert not (short_run_dir / "podman.sock").exists()
    assert not cfg.pid_file.exists()


# ------------------------------------------------------- M9: probe_egress


def test_probe_egress_true_when_something_listens() -> None:
    async def scenario() -> None:
        try:
            server = await asyncio.start_server(lambda r, w: None, host="127.0.0.1", port=0)
        except PermissionError:
            pytest.skip("sandbox denies TCP bind; runs in CI")
        try:
            port = server.sockets[0].getsockname()[1]
            assert await daemon.probe_egress("host.containers.internal", port) is True
        finally:
            server.close()
            await server.wait_closed()

    run(scenario())


def test_probe_egress_false_when_nothing_listens() -> None:
    async def scenario() -> None:
        try:
            server = await asyncio.start_server(lambda r, w: None, host="127.0.0.1", port=0)
        except PermissionError:
            pytest.skip("sandbox denies TCP bind; runs in CI")
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()
        assert await daemon.probe_egress("host.containers.internal", port) is False

    run(scenario())


# ------------------------------------------------------------ full run()


def test_run_without_backends_exits_zero(tmp_path: Path, short_run_dir: Path) -> None:
    async def scenario() -> None:
        cfg = daemon.Config(
            tmp_path,
            short_run_dir,
            ("podman", "docker"),
            "off",
            8899,
            None,
            (),
            5.0,
            "INFO",
            short_run_dir / "pid",
        )
        rc = await daemon.run(cfg, discover_fn=lambda *a, **k: [], platform="Darwin")
        assert rc == 0
        assert not (short_run_dir / "podman.sock").exists()

    run(scenario())


def test_run_serves_both_sockets_from_podman_only_and_idles_out(tmp_path: Path, short_run_dir: Path) -> None:
    async def scenario() -> None:
        backend = _RealSocketBackend(short_run_dir / "d.sock")
        try:
            await backend.start()
        except PermissionError:
            pytest.skip("sandbox denies unix bind; runs in CI")
        try:
            cfg = daemon.Config(
                tmp_path,
                short_run_dir,
                ("podman", "docker"),
                "off",
                8899,
                None,
                (),
                1.5,
                "INFO",
                short_run_dir / "pid",
            )
            found = [Backend("podman", backend.socket, "host.containers.internal")]
            task = asyncio.create_task(daemon.run(cfg, discover_fn=lambda *a, **k: found, platform="Darwin"))
            await asyncio.sleep(0.3)
            if task.done():
                exc = task.exception()
                if isinstance(exc, PermissionError):
                    pytest.skip("sandbox denies unix bind; runs in CI")
                if exc is not None:
                    raise exc
            try:
                for name in ("podman.sock", "docker.sock"):
                    r, w = await asyncio.open_unix_connection(str(short_run_dir / name))
                    w.write(b"GET /_ping HTTP/1.1\r\nHost: x\r\n\r\n")
                    await w.drain()
                    assert b"200 OK" in await asyncio.wait_for(r.read(), 5)
                    w.close()
            except PermissionError:
                pytest.skip("sandbox denies unix bind; runs in CI")
            assert daemon.read_pid(cfg.pid_file) == os.getpid()
            rc = await asyncio.wait_for(task, 10)  # idle timeout fires
            assert rc == 0
            assert not cfg.pid_file.exists()
        finally:
            await backend.stop()

    run(scenario())


# --------------------------------------------------------------- CLI e2e


def test_cli_status_when_not_running(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "container_gateway", "status", "--project", str(tmp_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
    )
    assert done.returncode == 3
    out = json.loads(done.stdout)
    assert out["running"] is False
    assert out["serving"] == []
    assert "backends" not in out


def test_cli_stop_when_never_served_reports_no_run_directory(tmp_path: Path) -> None:
    """A project with no ``.apache-magpie-local/run`` at all gets a message, not silence.

    ``tmp_path`` itself has no run directory under it, so this exercises
    ``validate_run_dir`` returning ``False`` end to end through the real
    subprocess entry point, not just the unit-level ``cmd_stop`` call.
    """
    done = subprocess.run(
        [sys.executable, "-m", "container_gateway", "stop", "--project", str(tmp_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
    )
    assert done.returncode == 0
    assert "nothing to stop" in done.stdout


def test_cli_serve_help_lists_flags() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "container_gateway", "serve", "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
    )
    for flag in (
        "--project",
        "--run-dir",
        "--backend",
        "--egress",
        "--egress-port",
        "--egress-host",
        "--extra-bind-root",
        "--idle-timeout",
        "--backend-timeout",
        "--log-level",
        "--pid-file",
        "--daemon",
    ):
        assert flag in done.stdout, flag


# ------------------------------------------- I7: TMPDIR is not a bind root


def test_bind_roots_are_the_project_and_the_extra_roots_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # $TMPDIR used to be a bind root. On macOS it is per-user, not
    # per-project, so it let every project on the machine bind-mount every
    # other project's scratch tree (and the agent's own).
    project = tmp_path / "proj"
    project.mkdir()
    extra = tmp_path / "data"
    extra.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv("TMPDIR", str(scratch))
    cfg = daemon.Config(
        project_root=project,
        run_dir=project / "run",
        backends=(),
        egress_mode="off",
        egress_port=8899,
        egress_host=None,
        extra_bind_roots=(extra,),
        idle_timeout=5.0,
        log_level="INFO",
        pid_file=project / "run" / "container-gateway.pid",
    )
    ctx = daemon.build_context(cfg, Backend("podman", Path("/x.sock"), "host.containers.internal"), None)
    assert ctx.bind_roots == (project.resolve(), extra.resolve())
    assert scratch.resolve() not in ctx.bind_roots
