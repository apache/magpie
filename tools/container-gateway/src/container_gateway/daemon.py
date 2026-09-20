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

"""Own the run directory, the pid file, the sockets and the process lifetime.

The daemon runs OUTSIDE the sandbox, with the operator's own privileges,
while the run directory it serves out of (``.apache-magpie-local/run/``
by default) lives inside the project tree the sandboxed agent can write,
delete and symlink freely. Every guard in this module exists to stop a
planted symlink, a pre-existing non-directory, or a stale/foreign pid
file from turning "start the gateway" into "the daemon opens, writes or
binds something the agent chose instead of something the operator
chose". See the Task 10 round-1 review findings for the threat model
each function below closes.
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import logging
import os
import platform as _platform
import re
import signal
import stat
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from . import backends as _backends
from .labels import project_slug
from .policy import PolicyContext
from .relay import Handler, Relay, serve_unix, unix_connector

log = logging.getLogger("container-gateway")
MAX_SUN_PATH = 103
_PID_RE = re.compile(r"^[0-9]{1,10}$")


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


def _refuse(message: str) -> NoReturn:
    print(f"container-gateway: {message}", file=sys.stderr)
    raise SystemExit(2)


def _lstat_or_none(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _refuse_if_symlink(path: Path, label: str) -> None:
    st = _lstat_or_none(path)
    if st is not None and stat.S_ISLNK(st.st_mode):
        _refuse(f"{label} ({path}) is a symlink; refusing")


def _refuse_if_parent_missing_or_symlink(path: Path, label: str) -> None:
    """An ancestor this module never creates on its own: it must already exist.

    Used for a custom ``--run-dir``'s parent, which may sit anywhere
    outside the project tree -- "create it for the operator" would be
    presumptuous, and letting a missing parent surface as a bare
    ``FileNotFoundError`` out of a later ``mkdir()`` is not an error
    message worth shipping.
    """
    st = _lstat_or_none(path)
    if st is None:
        _refuse(f"{label} ({path}) does not exist")
    if stat.S_ISLNK(st.st_mode):
        _refuse(f"{label} ({path}) is a symlink; refusing")


def _resolved_existing_project_root(project_root: Path) -> Path:
    resolved = project_root.resolve()
    if not resolved.is_dir():
        _refuse(f"project root ({resolved}) does not exist")
    return resolved


def _owned_private_dir_status(path: Path, label: str) -> bool:
    """Whether ``path`` exists and is a safe, private directory -- without creating it.

    ``True``: exists, is a directory, owned by the current effective
    user, not group- or world-writable. ``False``: does not exist yet
    (not an attack -- just "nothing here"). Refuses (``SystemExit(2)``)
    for every other shape a present path could have: a symlink, a
    regular file, a foreign owner, a group/world-writable mode.
    """
    _refuse_if_symlink(path, label)
    st = _lstat_or_none(path)
    if st is None:
        return False
    if not stat.S_ISDIR(st.st_mode):
        _refuse(f"{label} ({path}) is not a directory; refusing")
    if st.st_uid != os.geteuid():
        _refuse(f"{label} ({path}) is not owned by the current user; refusing")
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        _refuse(f"{label} ({path}) is group- or world-writable; refusing")
    return True


def _ensure_owned_private_dir(path: Path, label: str) -> None:
    """``path`` must not be a symlink; created 0700 when absent.

    An explicit ``mkdir()``, never ``parents=True`` -- each component is
    checked and created one at a time by the caller so a symlink planted
    at an intermediate component is never silently traversed. When it
    already exists it must be a directory owned by the current effective
    user and not group- or world-writable (``_owned_private_dir_status``).
    A ``FileExistsError`` from the ``mkdir`` itself (something else
    created -- or planted -- this path between our check and this call)
    re-runs that same check against whatever is actually there now,
    rather than trusting the race's winner.
    """
    if _owned_private_dir_status(path, label):
        return
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        if not _owned_private_dir_status(path, label):
            _refuse(f"{label} ({path}) could not be created or inspected")


def check_run_dir(run_dir: Path, project_root: Path) -> None:
    """Guarantee ``run_dir`` is a real, owned, non-symlinked, private directory
    at the moment this check runs.

    ``project_root`` is resolved once -- a symlinked *project root* is a
    legitimate thing the operator pointed ``--project`` at, and it must
    already exist (this function creates directories below it, never the
    root itself). Everything strictly below it is walked top-down with
    ``lstat``, refusing a symlink, a non-directory, a foreign owner or a
    group/world-writable mode on each component before creating or
    trusting the next one: first ``.apache-magpie-local``, then ``run``,
    in the default layout. A custom ``--run-dir`` outside the project
    tree must have an existing, non-symlinked parent, then gets the same
    ownership/mode check on itself.

    This closes the symlink-plant attack *at check time*; it does not by
    itself pin the directory components against a race between this
    check and a later operation inside them -- an attacker who can still
    write to a checked-safe parent after this call returns could still
    swap a directory for a symlink before the next thing that touches it.
    What IS pinned across that gap is the *file* opens downstream of this
    check: the pid file and the daemon log are opened with ``O_NOFOLLOW``,
    which atomically refuses a symlink at the exact moment of that open,
    independent of whatever this function saw a moment earlier.
    """
    resolved_root = _resolved_existing_project_root(project_root)
    default_run_dir = resolved_root / ".apache-magpie-local" / "run"
    if run_dir == default_run_dir:
        _ensure_owned_private_dir(
            resolved_root / ".apache-magpie-local", "the project's .apache-magpie-local directory"
        )
        _ensure_owned_private_dir(run_dir, "the run directory")
    else:
        _refuse_if_parent_missing_or_symlink(run_dir.parent, "the run directory's parent")
        _ensure_owned_private_dir(run_dir, "the run directory")


def validate_run_dir(run_dir: Path, project_root: Path) -> bool:
    """Read-only counterpart to ``check_run_dir``, for ``status``/``stop``.

    Those commands must never create anything -- inspecting a project
    that has never been served should have no side effects -- but they
    must not silently walk *through* a planted symlink just because they
    only read. Returns ``True`` when every relevant component exists and
    passes the same checks ``check_run_dir`` enforces; ``False`` when a
    component is simply missing, which callers read as "not running", not
    as an attack. A symlink, wrong owner, wrong type or wrong mode on a
    component that DOES exist still refuses with ``SystemExit(2)``.
    """
    resolved_root = project_root.resolve()
    if not resolved_root.is_dir():
        return False  # nothing has ever been served from a project that is not there
    default_run_dir = resolved_root / ".apache-magpie-local" / "run"
    if run_dir == default_run_dir:
        if not _owned_private_dir_status(
            resolved_root / ".apache-magpie-local", "the project's .apache-magpie-local directory"
        ):
            return False
    else:
        st = _lstat_or_none(run_dir.parent)
        if st is None:
            return False
        if stat.S_ISLNK(st.st_mode):
            _refuse(f"the run directory's parent ({run_dir.parent}) is a symlink; refusing")
    return _owned_private_dir_status(run_dir, "the run directory")


def check_socket_type(p: Path) -> None:
    """Refuse to bind over anything but a stale unix socket or nothing at all.

    A symlink, a regular file or a directory sitting at a gateway socket
    path is not something ``run()`` should ever silently remove and
    replace -- it only unlinks a path after this check has confirmed
    whatever is there really is a stale socket (or nothing).
    """
    st = _lstat_or_none(p)
    if st is not None and not stat.S_ISSOCK(st.st_mode):
        _refuse(f"{p} exists and is not a socket; refusing to bind over it")


def read_pid(pid_file: Path) -> int | None:
    """The pid recorded in ``pid_file``, or ``None`` if it is missing or unsafe.

    Only a bare, base-10, 1-to-10-digit integer greater than 1 is
    accepted -- ``-1``, ``0``, ``1``, non-numeric content and anything
    with trailing garbage all read as ``None``. This is what keeps a
    corrupted or hostile pid file from ever reaching ``os.kill()``:
    ``kill(-1, ...)`` signals every process the caller owns, and ``kill(1,
    ...)`` targets init.
    """
    try:
        text = pid_file.read_text().strip()
    except OSError:
        return None
    if not _PID_RE.fullmatch(text):
        return None
    pid = int(text)
    return pid if pid > 1 else None


def pid_file_is_trustworthy(pid_file: Path) -> bool | None:
    """Whether ``pid_file`` is safe for ``status``/``stop`` to act on.

    ``None``: does not exist yet -- nothing has been distrusted, there is
    simply nothing there. ``True``: exists, is a regular file (not a
    symlink), owned by the current effective user, mode exactly ``0600``
    -- exactly the shape ``acquire_pid_lock`` creates. ``False``: exists
    but fails one of those checks -- a symlink, someone else's file, or a
    mode the agent (or anything else) widened or narrowed after the fact.
    Callers never signal or otherwise trust a file this returns ``False``
    for, and never need to distinguish "doesn't exist" from "exists but
    is fine" for their own decision -- both are handled by the ``bool()``
    of this return value except where the caller needs to tell "never
    served" apart from "untrustworthy", which is why this returns
    ``None`` rather than folding that case into ``False``.
    """
    st = _lstat_or_none(pid_file)
    if st is None:
        return None
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return False
    if st.st_uid != os.geteuid():
        return False
    return st.st_mode & 0o777 == 0o600


def pid_alive(pid: int) -> bool:
    """A cheap liveness probe -- kept only as a fast-path helper for the
    ``stop`` wait loop. The authoritative liveness signal is the pid-file
    flock (see ``acquire_pid_lock`` / ``probe_pid_lock``), not this.
    """
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _open_pid_fd(pid_file: Path, flags: int) -> int:
    """Open the pid file, never following a symlink at that exact path."""
    return os.open(pid_file, flags | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)


def acquire_pid_lock(pid_file: Path) -> int | None:
    """Become the single serving instance for ``pid_file``, or find out we are not.

    On success, returns an fd holding ``LOCK_EX`` for as long as it stays
    open, with our pid already written into it. The caller keeps this fd
    open (and never closes it) for the process's entire life -- closing
    it, or letting it be garbage collected, drops the lock. Returns
    ``None`` when another live instance already holds the lock.

    The fd is opened WITHOUT ``O_TRUNC`` -- truncating unconditionally at
    open time would blank a live daemon's pid file the instant a second,
    losing ``serve`` invocation merely probes it, even though that
    second invocation never wins the lock. The file's content is only
    ever rewritten *after* the lock is actually won, so a contended probe
    leaves the live instance's displayed pid untouched.
    """
    try:
        fd = _open_pid_fd(pid_file, os.O_WRONLY | os.O_CREAT)
    except OSError as exc:
        _refuse(f"{pid_file} could not be opened safely (symlink?): {exc}")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, 0)
    os.write(fd, f"{os.getpid()}\n".encode())
    os.fsync(fd)
    return fd


def probe_pid_lock(pid_file: Path) -> tuple[bool, int | None]:
    """Whether some instance currently holds ``pid_file``'s lock, and its pid.

    ``(False, None)``: nothing has ever served here (the run directory
    does not exist yet), or nothing holds the lock -- a stale pid file,
    if any, is removed in that second case. ``(True, pid)``: the lock is
    held; ``pid`` is whatever ``read_pid`` can validate out of the file,
    which may itself be ``None`` even while the lock is held (unreadable
    or invalid content) -- callers must not signal in that case.
    """
    try:
        fd = _open_pid_fd(pid_file, os.O_RDWR | os.O_CREAT)
    except FileNotFoundError:
        return False, None
    except OSError as exc:
        _refuse(f"{pid_file} could not be opened safely (symlink?): {exc}")
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True, read_pid(pid_file)
        fcntl.flock(fd, fcntl.LOCK_UN)
        pid_file.unlink(missing_ok=True)
        return False, None
    finally:
        os.close(fd)


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
    with contextlib.suppress(OSError):
        await w.wait_closed()
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
    check_run_dir(cfg.run_dir, cfg.project_root)
    p = paths(cfg.run_dir)
    for key in ("podman", "docker"):
        check_socket_path(p[key])

    pid_fd = acquire_pid_lock(cfg.pid_file)
    if pid_fd is None:
        log.info("another instance already holds the pid lock at %s; exiting", cfg.pid_file)
        return 0

    try:
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
        bound_sockets: list[Path] = []
        activity = _Activity()
        signal_handlers_installed: list[signal.Signals] = []
        loop = asyncio.get_running_loop()
        try:
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
                    elif cfg.egress_mode == "require":
                        log.warning(
                            "egress gateway unreachable; every container create will be refused (--egress require)"
                        )
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
                sock_path = p[key]
                check_socket_type(sock_path)
                # The lock is already held (we would not be here
                # otherwise) and `check_socket_type` just confirmed
                # anything present really is a stale socket -- only now
                # is it safe to remove it. `serve_unix` itself performs
                # no unlink of its own.
                sock_path.unlink(missing_ok=True)
                server = await serve_unix(sock_path, activity.wrap(relay))
                servers.append(server)
                bound_sockets.append(sock_path)
                log.info("%s CLI -> %s (backend %s at %s)", key, sock_path, backend.kind, backend.socket)

            stop = asyncio.Event()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, stop.set)
                signal_handlers_installed.append(sig)
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1.0)
                except TimeoutError:
                    if time.monotonic() - activity.last > cfg.idle_timeout:
                        log.info("idle for %.0fs; exiting", cfg.idle_timeout)
                        break
        finally:
            for sig in signal_handlers_installed:
                loop.remove_signal_handler(sig)
            for s in servers:
                s.close()
                await s.wait_closed()
            # Only the sockets *this process* bound -- a partial bind
            # failure must not delete a sibling socket another (already
            # running) instance might still be serving from.
            for sock_path in bound_sockets:
                sock_path.unlink(missing_ok=True)
    finally:
        # Unlink FIRST, while the lock is still held (the fd is still
        # open): once the fd is closed the lock is gone, and any window
        # between that and the unlink is a window where a racing `serve`
        # could win the lock on a *new* inode while this pid file is
        # still the old one on disk. Unlinking before closing removes
        # that window instead of merely narrowing it.
        cfg.pid_file.unlink(missing_ok=True)
        os.close(pid_fd)
    return 0
