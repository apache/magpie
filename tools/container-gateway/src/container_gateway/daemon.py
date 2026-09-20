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

"""Own the run directory, the pid file, the sockets and the process lifetime."""

from __future__ import annotations

import asyncio
import logging
import os
import platform as _platform
import signal
import stat
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import backends as _backends
from .labels import project_slug
from .policy import PolicyContext
from .relay import Handler, Relay, serve_unix, unix_connector

log = logging.getLogger("container-gateway")
MAX_SUN_PATH = 103


@dataclass
class Config:
    project_root: Path
    run_dir: Path
    backends: tuple[str, ...]
    egress_mode: str
    egress_port: int
    egress_host: str | None
    extra_bind_roots: tuple[Path, ...]
    idle_timeout: float
    log_level: str
    pid_file: Path
    # Bounds every short backend round trip the relay makes on the
    # client's behalf (label-check inspects, the connect, the first
    # response head). Never bounds a streamed body or a hijacked pipe.
    # See Task 10 addendum Ruling A.
    backend_timeout: float = 60.0


def paths(run_dir: Path) -> dict[str, Path]:
    return {
        "podman": run_dir / "podman.sock",
        "docker": run_dir / "docker.sock",
        "pid": run_dir / "container-gateway.pid",
    }


def check_socket_path(p: Path) -> None:
    if len(str(p).encode()) > MAX_SUN_PATH:
        print(f"container-gateway: socket path too long ({p}); pass a shorter --run-dir", file=sys.stderr)
        raise SystemExit(2)


def check_run_dir(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    mode = run_dir.stat().st_mode
    if mode & (stat.S_IWGRP | stat.S_IWOTH):
        print(
            f"container-gateway: {run_dir} is group- or world-writable; refusing to bind sockets there",
            file=sys.stderr,
        )
        raise SystemExit(2)


def read_pid(pid_file: Path) -> int | None:
    try:
        return int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def probe_egress(host: str, port: int) -> bool:
    """Whether something is listening on the host loopback at ``port``.

    ``host`` is the in-container alias (``host.containers.internal`` and
    friends) -- it is not dialled directly. The probe checks the gateway
    from the host side, on ``127.0.0.1``, since that is where the
    listener actually binds; the alias only matters once the request is
    inside a container's own network namespace.
    """
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 1.0)
    except OSError:
        return False
    w.close()
    return True


def build_context(cfg: Config, backend: _backends.Backend, proxy_env: dict[str, str] | None) -> PolicyContext:
    """The policy context for one backend's relay.

    The scratch root comes from ``TMPDIR`` only when it is actually set --
    never a hardcoded ``/tmp`` fallback, which would let every project on
    the machine bind-mount out of the same shared, world-writable
    directory. An unset ``TMPDIR`` means the project root and any
    ``--extra-bind-root`` entries are the only allowed bind-mount roots.
    """
    roots = [cfg.project_root.resolve()]
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        roots.append(Path(tmpdir).resolve())
    roots.extend(root.resolve() for root in cfg.extra_bind_roots)
    return PolicyContext(
        project_slug(cfg.project_root), cfg.project_root.resolve(), tuple(roots), proxy_env, cfg.egress_mode
    )


class _Activity:
    """Idle tracking: every accepted connection bumps the clock."""

    def __init__(self) -> None:
        self.last = time.monotonic()

    def wrap(self, relay: Relay) -> Handler:
        async def handler(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
            self.last = time.monotonic()
            await relay.handle(r, w)
            self.last = time.monotonic()

        return handler


async def run(
    cfg: Config,
    *,
    discover_fn: Callable[..., list[_backends.Backend]] = _backends.discover,
    platform: str = _platform.system(),
) -> int:
    logging.basicConfig(level=cfg.log_level.upper(), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    check_run_dir(cfg.run_dir)
    p = paths(cfg.run_dir)
    for key in ("podman", "docker"):
        check_socket_path(p[key])

    found = discover_fn(
        platform, os.environ, _backends.default_runner, lambda x: x.exists(), frozenset(cfg.backends)
    )
    if not found:
        log.info("no podman or docker backend found; nothing to serve")
        return 0
    by_kind = {b.kind: b for b in found}
    podman = by_kind.get("podman")
    docker = by_kind.get("docker") or podman  # docker CLI speaks the compat API on podman too

    servers: list[asyncio.AbstractServer] = []
    activity = _Activity()
    for key, backend in (("podman", podman), ("docker", docker)):
        if backend is None:
            continue
        proxy_env: dict[str, str] | None = None
        if cfg.egress_mode != "off":
            alias_backend = (
                backend
                if cfg.egress_host is None
                else _backends.Backend(backend.kind, backend.socket, cfg.egress_host)
            )
            if await probe_egress(alias_backend.host_alias, cfg.egress_port):
                proxy_env = _backends.egress_proxy_env(alias_backend, cfg.egress_port)
            else:
                log.warning(
                    "egress gateway not reachable on 127.0.0.1:%s; containers get no proxy (--egress %s)",
                    cfg.egress_port,
                    cfg.egress_mode,
                )
        relay = Relay(
            unix_connector(backend.socket),
            build_context(cfg, backend, proxy_env),
            backend_label=str(backend.socket),
            backend_timeout=cfg.backend_timeout,
        )
        server = await serve_unix(p[key], activity.wrap(relay))
        servers.append(server)
        log.info("%s CLI -> %s (backend %s at %s)", key, p[key], backend.kind, backend.socket)

    cfg.pid_file.write_text(f"{os.getpid()}\n")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.0)
            except TimeoutError:
                if time.monotonic() - activity.last > cfg.idle_timeout:
                    log.info("idle for %.0fs; exiting", cfg.idle_timeout)
                    break
    finally:
        for s in servers:
            s.close()
            await s.wait_closed()
        for key in ("podman", "docker"):
            p[key].unlink(missing_ok=True)
        cfg.pid_file.unlink(missing_ok=True)
    return 0
