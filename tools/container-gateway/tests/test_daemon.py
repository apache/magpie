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

No ``pytest-asyncio`` in the ``magpie-dev`` dependency group, so each
async scenario is a plain ``def`` test driving its coroutine through the
``run()`` helper, exactly as ``test_http.py`` and ``test_relay.py`` do.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Coroutine, Iterator
from pathlib import Path
from typing import Any, TypeVar

import pytest

from container_gateway import daemon
from container_gateway.backends import Backend

from .fakebackend import FakeBackend

SRC = Path(__file__).resolve().parents[1] / "src"

_T = TypeVar("_T")


def run(coro: Coroutine[Any, Any, _T]) -> _T:
    """Drive a coroutine to completion without pytest-asyncio."""
    return asyncio.run(coro)


@pytest.fixture
def short_run_dir() -> Iterator[Path]:
    """A run directory short enough to hold a unix-socket path.

    ``pytest``'s own ``tmp_path`` fixture nests under
    ``pytest-of-<user>/pytest-<n>/<test-name>/`` inside ``$TMPDIR``, which
    in this sandboxed dev environment is already long enough on its own
    to blow the ~103-byte ``sun_path`` limit before ``run_dir`` even adds
    ``podman.sock``. ``tempfile.mkdtemp()`` sits directly under
    ``$TMPDIR`` with none of that nesting, so it stays short everywhere
    ``tmp_path`` might not.
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


def test_paths_and_socket_length(tmp_path: Path) -> None:
    p = daemon.paths(tmp_path)
    assert p["podman"].name == "podman.sock" and p["docker"].name == "docker.sock"
    daemon.check_socket_path(tmp_path / "ok.sock")
    with pytest.raises(SystemExit) as exc:
        daemon.check_socket_path(Path("/" + "x" * 120 + "/podman.sock"))
    assert exc.value.code == 2


def test_run_dir_must_not_be_group_or_world_writable(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    daemon.check_run_dir(run_dir)
    assert run_dir.stat().st_mode & 0o777 == 0o700
    run_dir.chmod(0o777)
    with pytest.raises(SystemExit):
        daemon.check_run_dir(run_dir)


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


def test_cli_status_when_not_running(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "container_gateway", "status", "--project", str(tmp_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
    )
    assert done.returncode == 3
    assert json.loads(done.stdout)["running"] is False


def test_cli_stop_when_not_running_is_quiet(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "container_gateway", "stop", "--project", str(tmp_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
    )
    assert done.returncode == 0 and done.stdout.strip() == ""


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
