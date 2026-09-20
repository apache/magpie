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

"""``python3 -m container_gateway`` -- serve, stop, status."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import sys
import time
from pathlib import Path

from . import backends as _backends
from . import daemon


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--project", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    p.add_argument(
        "--run-dir", type=Path, help="socket + pid directory (default: <project>/.apache-magpie-local/run)"
    )
    p.add_argument(
        "--pid-file",
        type=Path,
        help="pid file (default: <run-dir>/container-gateway.pid); must not be a symlink; created 0600 with O_NOFOLLOW",
    )


def _absolute(path: Path) -> Path:
    """Make ``path`` absolute without resolving symlinks (unlike ``Path.resolve()``).

    Every path this module hands to ``daemon``'s guards must still show
    every symlink a path component might be, so those guards can refuse
    one; lexical normalisation (joining onto the cwd) is safe, chasing
    symlinks to find out where they really point is exactly what must
    not happen before the guard runs.
    """
    return path if path.is_absolute() else Path.cwd() / path


def _config(ns: argparse.Namespace) -> daemon.Config:
    root = ns.project.resolve()  # the trust anchor: the operator's own --project value
    run_dir = _absolute(ns.run_dir) if ns.run_dir is not None else root / ".apache-magpie-local" / "run"
    pid_file = _absolute(ns.pid_file) if ns.pid_file is not None else run_dir / "container-gateway.pid"
    return daemon.Config(
        project_root=root,
        run_dir=run_dir,
        backends=tuple(ns.backend) if getattr(ns, "backend", None) else ("podman", "docker"),
        egress_mode=getattr(ns, "egress", "inject-if-available"),
        egress_port=getattr(ns, "egress_port", 8899),
        egress_host=getattr(ns, "egress_host", None),
        extra_bind_roots=tuple(getattr(ns, "extra_bind_root", None) or ()),
        idle_timeout=getattr(ns, "idle_timeout", 4 * 3600.0),
        log_level=getattr(ns, "log_level", "INFO"),
        pid_file=pid_file,
        backend_timeout=getattr(ns, "backend_timeout", 60.0),
    )


def _open_log_fd(log_path: Path) -> int:
    """Open the daemon log, never following a symlink at that exact path."""
    try:
        return os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError as exc:
        print(f"container-gateway: {log_path} could not be opened safely (symlink?): {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def _daemonize(log_path: Path) -> None:
    """Detach from the controlling terminal: the classic double-fork.

    Not exercised by this unit-test suite -- the sandbox denies the
    ``bind()`` a real ``serve()`` needs downstream of this anyway, and a
    ``fork()`` that then races the test process's own event loop and file
    descriptors is not something a unit test can observe safely. Covered
    by the Task 15 integration run instead. ``_open_log_fd`` above, the
    one part of this that can raise on a hostile input, is unit-tested
    directly.
    """
    if os.fork():
        os._exit(0)
    os.setsid()
    if os.fork():
        os._exit(0)
    os.chdir("/")
    os.umask(0o077)
    log_fd = _open_log_fd(log_path)
    devnull_fd = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull_fd, 0)
    os.dup2(log_fd, 1)
    os.dup2(log_fd, 2)
    os.close(log_fd)
    os.close(devnull_fd)


def cmd_serve(ns: argparse.Namespace) -> int:
    cfg = _config(ns)
    daemon.check_run_dir(cfg.run_dir, cfg.project_root)
    running, _ = daemon.probe_pid_lock(cfg.pid_file)
    if running:
        return 0  # already running for this project
    if ns.daemon:
        _daemonize(cfg.run_dir / "container-gateway.log")  # Task 15 integration run covers this path
    return asyncio.run(daemon.run(cfg))


# Matches only the argv shapes `cmd_serve`/the hook actually invoke: a
# python interpreter -- optionally through a runner like `uv run` and/or
# interpreter flags such as `-u` -- running the `container_gateway` module,
# or a `container-gateway` console-script executable, each optionally
# through a path prefix and followed by more argv (or end of line). A plain
# substring check (`"container_gateway" in line`) would also match an
# editor opened on a file named `container_gateway.py`, which is not this
# gateway.
_GATEWAY_ARGV_RE = re.compile(
    r"^(?:\S*/)?(?:uv\s+run\s+)?(?:\S*/)?python\d*(?:\.\d+)?(?:\s+-\S+)*\s+-m\s+container_gateway(?:\s|$)"
    r"|^(?:\S*/)?container-gateway(?:\s|$)"
)


def _looks_like_a_gateway_process(pid: int) -> bool:
    """Refuse to signal anything that does not look like this gateway.

    ``stop`` reads its target pid out of a file under a run directory the
    sandboxed agent can otherwise only plant, not forge (D1's validation
    plus a pid file that must be a regular, euid-owned, mode-0600 file
    closes every forging route) -- but the agent could still start some
    other long-lived process of its own, of a pid the operator's own
    ``container-gateway serve`` later happens to reuse after the agent
    wrote it into a (by then legitimately 0600) pid file through a prior
    run's cleanup race. Checking the live process's own command line
    before ever signalling it guards against that accidental reuse; an
    unreadable command line (``ps`` unavailable, the process already
    gone) refuses rather than guesses. This is a guard, not a security
    boundary: a process's command line (``argv[0]`` included) is
    attacker-settable, so it cannot stop a deliberate adversary already
    running arbitrary code from shaping its own command line to match.

    The check is an argv-shape match against the first line of ``ps``
    output only, not a substring search: a substring match would also
    treat ``vim container_gateway.py`` (an editor opened on a source
    file) as the gateway.
    """
    line = _backends.default_runner(["ps", "-o", "command=", "-p", str(pid)])
    if not line:
        return False
    first_line = line.splitlines()[0].strip()
    return _GATEWAY_ARGV_RE.match(first_line) is not None


def cmd_stop(ns: argparse.Namespace) -> int:
    cfg = _config(ns)
    if not cfg.project_root.is_dir():
        # A missing project root and a missing run directory both make
        # validate_run_dir return False, but they are different situations
        # to report: this one means the --project value itself is wrong.
        print(f"container-gateway: no project root at {cfg.project_root}: nothing to stop")
        return 0
    if not daemon.validate_run_dir(cfg.run_dir, cfg.project_root):
        # Never served, or the run directory itself no longer exists. Not an
        # error -- but silent success here reads identically to "stopped it
        # successfully", which is misleading when nothing was ever running.
        print(f"container-gateway: no run directory at {cfg.run_dir}: nothing to stop")
        return 0
    trust = daemon.pid_file_is_trustworthy(cfg.pid_file)
    if trust is None:
        return 0  # no pid file yet: nothing to stop
    if trust is False:
        print(
            f"container-gateway: {cfg.pid_file} is not a plain, owned, 0600 pid file; refusing",
            file=sys.stderr,
        )
        raise SystemExit(2)
    running, pid = daemon.probe_pid_lock(cfg.pid_file)
    if not running:
        return 0
    if pid is None:
        # Something holds the lock but the pid file's content is missing
        # or unsafe to trust -- there is nothing we can safely signal.
        return 1
    if not _looks_like_a_gateway_process(pid):
        print(
            f"container-gateway: pid {pid} does not look like a container-gateway process; refusing to signal",
            file=sys.stderr,
        )
        return 1
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        running, _ = daemon.probe_pid_lock(cfg.pid_file)
        if not running:
            return 0
        time.sleep(0.1)
    running, _ = daemon.probe_pid_lock(cfg.pid_file)
    if running:
        # pid_alive is a fallback log detail here, never the decision --
        # the lock probe just above is what running/not-running means.
        print(
            f"container-gateway: pid {pid} still holds the lock 5s after SIGTERM (pid_alive={daemon.pid_alive(pid)})",
            file=sys.stderr,
        )
    return 0 if not running else 1


def _status_payload(running: bool, pid: int | None, run_dir: Path) -> dict[str, object]:
    p = daemon.paths(run_dir)
    serving = [k for k in ("podman", "docker") if running and p[k].exists()]
    sockets = {k: (str(p[k]) if k in serving else None) for k in ("podman", "docker")}
    return {"running": running, "pid": pid if running else None, "sockets": sockets, "serving": serving}


def cmd_status(ns: argparse.Namespace) -> int:
    cfg = _config(ns)
    if not daemon.validate_run_dir(cfg.run_dir, cfg.project_root):
        print(json.dumps(_status_payload(False, None, cfg.run_dir)))
        return 3
    trust = daemon.pid_file_is_trustworthy(cfg.pid_file)
    if trust is not True:
        # Missing: never served. Untrustworthy: report not-running without
        # touching a file that failed the ownership/type/mode check --
        # `status` never deletes something it does not trust.
        print(json.dumps(_status_payload(False, None, cfg.run_dir)))
        return 3
    running, pid = daemon.probe_pid_lock(cfg.pid_file)
    print(json.dumps(_status_payload(running, pid, cfg.run_dir)))
    return 0 if running else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="container-gateway")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the gateway for one project")
    _common(s)
    s.add_argument(
        "--backend",
        action="append",
        choices=["podman", "docker"],
        help="serve only this backend (repeatable)",
    )
    s.add_argument(
        "--egress", choices=["inject-if-available", "require", "off"], default="inject-if-available"
    )
    s.add_argument("--egress-port", type=int, default=8899)
    s.add_argument("--egress-host", help="override the in-container address of the egress gateway")
    s.add_argument(
        "--extra-bind-root",
        action="append",
        type=Path,
        help="additional allowed bind-mount root (repeatable)",
    )
    s.add_argument(
        "--idle-timeout", type=float, default=4 * 3600.0, help="seconds without a connection before exiting"
    )
    s.add_argument(
        "--backend-timeout",
        type=float,
        default=60.0,
        help="seconds before a stalled backend call becomes a 502",
    )
    s.add_argument("--log-level", default="INFO")
    s.add_argument("--daemon", action="store_true", help="detach and log to <run-dir>/container-gateway.log")
    s.set_defaults(fn=cmd_serve)
    for name, fn in (("stop", cmd_stop), ("status", cmd_status)):
        q = sub.add_parser(name)
        _common(q)
        q.set_defaults(fn=fn)
    ns = parser.parse_args(argv)
    return int(ns.fn(ns))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
