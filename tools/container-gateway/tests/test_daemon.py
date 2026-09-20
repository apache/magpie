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
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import AsyncIterator, Coroutine, Iterator
from pathlib import Path
from typing import Any, TypeVar

import pytest

from container_gateway import __main__ as cli
from container_gateway import daemon
from container_gateway.backends import Backend

from .fakebackend import FakeBackend

SRC = Path(__file__).resolve().parents[1] / "src"

_T = TypeVar("_T")

# Every scenario in this file is bounded. A daemon test that wedges --
# waiting on a bind that never completes, a socket nobody answers, an
# idle timer that never fires -- must fail in seconds, naming itself,
# rather than hang the whole run until CI's job limit kills it with no
# output at all. Generous enough that no healthy scenario can reach it:
# the longest one here idles out after 1.5s.
SCENARIO_TIMEOUT = 15.0
# The same bound for the subprocess-level CLI tests further down.
SUBPROCESS_TIMEOUT = 30


def run(coro: Coroutine[Any, Any, _T], timeout: float = SCENARIO_TIMEOUT) -> _T:
    """Drive a coroutine to completion without pytest-asyncio, under a hard bound."""

    async def bounded() -> _T:
        return await asyncio.wait_for(coro, timeout)

    return asyncio.run(bounded())


async def _tcp_listener_or_skip() -> asyncio.AbstractServer:
    """A loopback TCP listener, skipping the caller where the sandbox refuses ``bind()``.

    Returning the server rather than binding inside the caller's ``try``
    keeps the caller's ``finally`` from ever referencing a name that was
    never assigned.

    The connection callback closes its side immediately. A callback that
    leaves the accepted transport open makes ``Server.wait_closed()`` block
    forever once anything has connected -- ``StreamReaderProtocol`` keeps the
    transport alive after the peer's EOF, and since Python 3.12.1
    ``wait_closed()`` waits for every accepted connection, not just the
    listening socket. That is what hung this file's teardown on CI.
    """

    def _close_immediately(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    try:
        return await asyncio.start_server(_close_immediately, host="127.0.0.1", port=0)
    except PermissionError:
        pytest.skip("sandbox denies TCP bind; runs in CI")


async def _close_server(server: asyncio.AbstractServer) -> None:
    """Close a listener and wait for it, bounded.

    Teardown must never be the thing that hangs a test: an unbounded
    ``wait_closed()`` turns one stuck connection into a whole-job timeout
    with no failing test to point at.
    """
    server.close()
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(server.wait_closed(), 5)


def _ns(project: Path, run_dir: Path, **extra: Any) -> argparse.Namespace:
    """A minimal argparse.Namespace for calling cmd_serve/cmd_stop/cmd_status directly."""
    base = {"project": project, "run_dir": run_dir, "pid_file": None}
    base.update(extra)
    return argparse.Namespace(**base)


class _HeldPidLock:
    """A pid lock the test body may hand back early, at most once.

    The ``stop``-path tests below release the lock mid-test, from inside
    a fake ``os.kill``, to simulate the daemon exiting and dropping its
    flock. ``released`` is how ``held_pid_lock`` knows not to close the
    same descriptor a second time on the way out -- by then the number
    may belong to something else entirely.
    """

    def __init__(self, fd: int) -> None:
        self._fd = fd
        self.released = False

    def close(self) -> None:
        if not self.released:
            self.released = True
            os.close(self._fd)


@contextlib.contextmanager
def held_pid_lock(pid_file: Path) -> Iterator[_HeldPidLock]:
    """Hold ``pid_file``'s lock for the body, releasing it however the body ends."""
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    lock = _HeldPidLock(fd)
    try:
        yield lock
    finally:
        if not lock.released:
            lock.released = True
            os.close(fd)


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
        """Stop serving, without waiting on a connection nobody will close.

        ``wait_closed`` waits for every accepted connection's handler
        too (Python 3.12.1 and later), and the fake's handler sits
        reading the next request on a keep-alive connection the gateway
        has not closed yet. Teardown is bounded so a test that leaves
        one open fails on its own assertion rather than wedging the run.
        """
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._server.wait_closed(), 5)


@contextlib.asynccontextmanager
async def _gateway(
    project_root: Path, run_dir: Path, idle_timeout: float
) -> AsyncIterator[tuple[daemon.Config, asyncio.Task[int]]]:
    """A running ``daemon.run()`` task with a real backend socket behind it.

    Skips the caller wherever the sandbox refuses the binds this needs,
    exactly like every other bind-touching test in this suite: the
    backend's own listener up front, the gateway's two sockets via the
    task's early exception.
    """
    backend = _RealSocketBackend(run_dir / "d.sock")
    try:
        await asyncio.wait_for(backend.start(), 5)
    except PermissionError:
        pytest.skip("sandbox denies unix bind; runs in CI")
    try:
        cfg = daemon.Config(
            project_root,
            run_dir,
            ("podman", "docker"),
            "off",
            8899,
            None,
            (),
            idle_timeout,
            "INFO",
            run_dir / "pid",
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
            yield cfg, task
        finally:
            # Only reached when the body did not get the daemon to exit
            # on its own -- the failure is the body's to report, so the
            # teardown just makes sure nothing is left running behind it.
            if not task.done():
                task.cancel()
                await asyncio.wait([task], timeout=5)
    finally:
        await asyncio.wait_for(backend.stop(), 5)


async def _ping(sock_path: Path) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Ping the gateway over a fresh client connection, and leave it open.

    The response is read by its framing rather than to EOF: the gateway
    keeps the connection alive after a ``/_ping``, so a read to EOF
    would only return once the daemon tore the connection down, which
    is the very thing the callers below are measuring.
    """
    try:
        r, w = await asyncio.wait_for(asyncio.open_unix_connection(str(sock_path)), 5)
    except PermissionError:
        pytest.skip("sandbox denies unix socket connections; runs in CI")
    w.write(b"GET /_ping HTTP/1.1\r\nHost: x\r\n\r\n")
    await asyncio.wait_for(w.drain(), 5)
    # Every await here is bounded: a gateway that accepts the connection
    # and then never answers must fail the test, not wedge the run.
    assert b"200 OK" in await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), 5)
    assert await asyncio.wait_for(r.readexactly(2), 5) == b"OK"
    return r, w


async def _close_client(w: asyncio.StreamWriter) -> None:
    """Close a client connection and wait for the close to land.

    Guarded twice over: the peer may already be gone (``OSError``), and
    a close that does not complete must not wedge a test that has
    finished with the connection anyway.
    """
    w.close()
    with contextlib.suppress(OSError, TimeoutError):
        await asyncio.wait_for(w.wait_closed(), 5)


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


def test_check_run_dir_accepts_a_symlinked_ancestor_above_the_project_root(tmp_path: Path) -> None:
    """The host's own layout is not the threat model.

    ``/tmp`` is a symlink to ``/private/tmp`` on macOS, ``/var`` likewise,
    and a home directory can sit on a linked volume -- a project reached
    through any of those must be served, not refused. The same shape is
    built portably here, so it runs on Linux too: a symlinked directory
    with a real project tree underneath it.
    """
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    project_root = link / "proj"
    project_root.mkdir()
    run_dir = project_root / ".apache-magpie-local" / "run"
    daemon.check_run_dir(run_dir, project_root)
    assert (real / "proj" / ".apache-magpie-local" / "run").is_dir()
    assert daemon.validate_run_dir(run_dir, project_root) is True


def test_check_run_dir_accepts_a_custom_run_dir_under_a_symlinked_ancestor(tmp_path: Path) -> None:
    """``--run-dir /tmp/whatever`` on macOS: the parent chain resolves, it is not refused."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    project_root = tmp_path / "proj"
    project_root.mkdir()
    run_dir = link / "custom-run"
    daemon.check_run_dir(run_dir, project_root)
    assert (real / "custom-run").is_dir()
    assert (real / "custom-run").stat().st_mode & 0o777 == 0o700
    assert daemon.validate_run_dir(run_dir, project_root) is True


def test_check_run_dir_refuses_a_symlinked_run_under_a_symlinked_ancestor(tmp_path: Path) -> None:
    """Resolving the chain above the anchor does not excuse a symlink AT an owned component."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    project_root = link / "proj"
    magpie_local = project_root / ".apache-magpie-local"
    magpie_local.mkdir(parents=True, mode=0o700)
    evil = tmp_path / "evil"
    evil.mkdir()
    (magpie_local / "run").symlink_to(evil)
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(magpie_local / "run", project_root)
    assert exc.value.code == 2


def test_check_run_dir_refuses_a_foreign_owned_intermediate_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ownership is still checked on every component the gateway owns, not just the last one."""
    project_root = tmp_path / "proj"
    (project_root / ".apache-magpie-local").mkdir(parents=True, mode=0o700)
    foreign = os.geteuid() + 1  # captured before the patch, or the lambda recurses
    monkeypatch.setattr(os, "geteuid", lambda: foreign)
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(project_root / ".apache-magpie-local" / "run", project_root)
    assert exc.value.code == 2


def test_check_run_dir_refuses_a_group_writable_intermediate_component(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    magpie_local = project_root / ".apache-magpie-local"
    magpie_local.mkdir(parents=True, mode=0o700)
    magpie_local.chmod(0o770)
    with pytest.raises(SystemExit) as exc:
        daemon.check_run_dir(magpie_local / "run", project_root)
    assert exc.value.code == 2


def test_validate_run_dir_refuses_a_group_writable_intermediate_component(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    magpie_local = project_root / ".apache-magpie-local"
    (magpie_local / "run").mkdir(parents=True, mode=0o700)
    magpie_local.chmod(0o770)
    with pytest.raises(SystemExit) as exc:
        daemon.validate_run_dir(magpie_local / "run", project_root)
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
    # `fd` stays None because the refusal fires before the open returns;
    # the `finally` is what keeps this test from leaking a descriptor if
    # `acquire_pid_lock` ever stops refusing.
    fd: int | None = None
    try:
        with pytest.raises(SystemExit) as exc:
            fd = daemon.acquire_pid_lock(link)
        assert exc.value.code == 2
    finally:
        if fd is not None:
            os.close(fd)


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
    # Same shape as the pid-lock refusal above: nothing should be opened,
    # and the `finally` proves it rather than assuming it.
    fd: int | None = None
    try:
        with pytest.raises(SystemExit) as exc:
            fd = cli._open_log_fd(link)
        assert exc.value.code == 2
    finally:
        if fd is not None:
            os.close(fd)


# --------------------- D2: acquire_pid_lock never blanks a live pid file


def test_acquire_pid_lock_does_not_blank_a_live_daemons_pid_file(tmp_path: Path) -> None:
    pid_file = tmp_path / "container-gateway.pid"
    fd = daemon.acquire_pid_lock(pid_file)
    assert fd is not None
    second: int | None = None
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, 0)
        os.write(fd, b"4242\n")
        os.fsync(fd)
        second = daemon.acquire_pid_lock(pid_file)
        assert second is None
        assert pid_file.read_text() == "4242\n"
    finally:
        if second is not None:
            os.close(second)  # only reachable if the contended probe ever won the lock
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
    our_pid = os.getpid()
    calls: list[tuple[int, int]] = []
    terminated = False

    with held_pid_lock(pid_file) as lock:

        def fake_kill(pid: int, sig: int) -> None:
            nonlocal terminated
            calls.append((pid, sig))
            if sig == signal.SIGTERM:
                terminated = True
                lock.close()  # simulate the daemon exiting: release the flock
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
    our_pid = os.getpid()
    calls: list[tuple[int, int]] = []
    terminated = False

    with held_pid_lock(pid_file) as lock:

        def fake_kill(pid: int, sig: int) -> None:
            nonlocal terminated
            calls.append((pid, sig))
            if sig == signal.SIGTERM:
                terminated = True
                lock.close()  # simulate the daemon exiting: release the flock
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
    our_pid = os.getpid()
    calls: list[tuple[int, int]] = []
    terminated = False

    with held_pid_lock(pid_file) as lock:

        def fake_kill(pid: int, sig: int) -> None:
            nonlocal terminated
            calls.append((pid, sig))
            if sig == signal.SIGTERM:
                terminated = True
                lock.close()  # simulate the daemon exiting: release the flock
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
        rc = await asyncio.wait_for(daemon.run(cfg, discover_fn=lambda *a, **k: [], platform="Darwin"), 5)
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
            await asyncio.wait_for(daemon.run(cfg, discover_fn=lambda *a, **k: found, platform="Darwin"), 5)

    run(scenario())
    assert closed == [True]
    assert not (short_run_dir / "podman.sock").exists()
    assert not cfg.pid_file.exists()


# ------------------------------------------------------- M9: probe_egress


def test_probe_egress_true_when_something_listens() -> None:
    async def scenario() -> None:
        server = await _tcp_listener_or_skip()
        try:
            port = server.sockets[0].getsockname()[1]
            assert await daemon.probe_egress("host.containers.internal", port) is True
        finally:
            await _close_server(server)

    run(scenario())


def test_probe_egress_false_when_nothing_listens() -> None:
    async def scenario() -> None:
        server = await _tcp_listener_or_skip()
        port = server.sockets[0].getsockname()[1]
        await _close_server(server)
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
        rc = await asyncio.wait_for(daemon.run(cfg, discover_fn=lambda *a, **k: [], platform="Darwin"), 5)
        assert rc == 0
        assert not (short_run_dir / "podman.sock").exists()

    run(scenario())


def test_run_serves_both_sockets_from_podman_only_and_idles_out(tmp_path: Path, short_run_dir: Path) -> None:
    async def scenario() -> None:
        async with _gateway(tmp_path, short_run_dir, 1.5) as (cfg, task):
            clients = [await _ping(short_run_dir / name) for name in ("podman.sock", "docker.sock")]
            assert daemon.read_pid(cfg.pid_file) == os.getpid()
            # What is being measured below is the daemon's own exit, so
            # the test's connections go first and the idle clock runs
            # against nothing but the daemon. The test after this one is
            # the one that leaves a connection open on purpose.
            for _, w in clients:
                await _close_client(w)
            rc = await asyncio.wait_for(task, 10)  # idle timeout fires 1.5s after the last close
            assert rc == 0
            assert not cfg.pid_file.exists()

    run(scenario())


def test_handlers_cancel_all_lets_wait_closed_return() -> None:
    """The one mechanism the two idle-exit tests around this one rest on.

    Since Python 3.12.1 ``Server.wait_closed()`` returns only once every
    accepted connection's handler has finished, so a handler parked on a
    client that sends nothing more holds the server -- and the process
    -- open indefinitely. The loopback listener here stands in for the
    gateway's unix sockets: the same ``asyncio.Server``, over a bind
    this sandbox allows where it refuses a unix one.
    """

    async def scenario() -> None:
        handlers = daemon._Handlers()
        started = asyncio.Event()
        unwound = asyncio.Event()

        async def blocked(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            started.set()
            try:
                await reader.read()  # the next keep-alive request, which never comes
            finally:
                unwound.set()

        try:
            server = await asyncio.start_server(handlers.track(blocked), host="127.0.0.1", port=0)
        except PermissionError:
            pytest.skip("sandbox denies TCP bind; runs in CI")
        try:
            port = server.sockets[0].getsockname()[1]
            _, w = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 5)
            try:
                await asyncio.wait_for(started.wait(), 5)
                server.close()
                await asyncio.wait_for(handlers.cancel_all(), 5)
                assert unwound.is_set()
                await asyncio.wait_for(server.wait_closed(), 5)
                # Every handler deregistered as it unwound, so a second
                # shutdown pass has nothing left to do.
                await asyncio.wait_for(handlers.cancel_all(), 5)
            finally:
                await _close_client(w)
        finally:
            server.close()

    run(scenario())


def test_run_idles_out_with_a_client_still_connected(tmp_path: Path, short_run_dir: Path) -> None:
    """A connected client must not be able to hold the gateway open.

    ``Server.wait_closed()`` waits for every accepted connection's
    handler as well (Python 3.12.1 and later), and the relay's handler
    blocks reading the next request on a keep-alive connection, so a
    daemon that closed its listening sockets and waited would never
    reach its idle exit while anything was connected -- and would not
    answer SIGTERM either. It ends its own handlers instead, so the
    client's connection dies with the daemon rather than outliving it.
    """

    async def scenario() -> None:
        async with _gateway(tmp_path, short_run_dir, 1.5) as (cfg, task):
            reader, writer = await _ping(short_run_dir / "podman.sock")
            try:
                rc = await asyncio.wait_for(task, 10)  # 1.5s idle plus the 1s poll, with margin
                assert rc == 0
                assert not cfg.pid_file.exists()
                assert not (short_run_dir / "podman.sock").exists()
                # The connection was closed on the way out, not left
                # dangling into a daemon that is no longer there.
                assert await asyncio.wait_for(reader.read(), 5) == b""
            finally:
                await _close_client(writer)

    run(scenario())


# --------------------------------------------------------------- CLI e2e


def test_cli_status_when_not_running(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "container_gateway", "status", "--project", str(tmp_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
        timeout=SUBPROCESS_TIMEOUT,
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
        timeout=SUBPROCESS_TIMEOUT,
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
        timeout=SUBPROCESS_TIMEOUT,
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
