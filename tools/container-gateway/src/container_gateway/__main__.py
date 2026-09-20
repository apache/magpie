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
import signal
import sys
import time
from pathlib import Path

from . import daemon


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--project", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    p.add_argument(
        "--run-dir", type=Path, help="socket + pid directory (default: <project>/.apache-magpie-local/run)"
    )
    p.add_argument("--pid-file", type=Path, help="pid file (default: <run-dir>/container-gateway.pid)")


def _config(ns: argparse.Namespace) -> daemon.Config:
    root = ns.project.resolve()
    run_dir = (ns.run_dir or root / ".apache-magpie-local" / "run").resolve()
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
        pid_file=(ns.pid_file or run_dir / "container-gateway.pid").resolve(),
        backend_timeout=getattr(ns, "backend_timeout", 60.0),
    )


def _daemonize(log_path: Path) -> None:
    """Detach from the controlling terminal: the classic double-fork.

    Not exercised by this unit-test suite -- the sandbox denies the
    ``bind()`` a real ``serve()`` needs downstream of this anyway, and a
    ``fork()`` that then races the test process's own event loop and file
    descriptors is not something a unit test can observe safely. Covered
    by the Task 15 integration run instead.
    """
    if os.fork():
        os._exit(0)
    os.setsid()
    if os.fork():
        os._exit(0)
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    for target in (1, 2):
        os.dup2(fd, target)
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)


def cmd_serve(ns: argparse.Namespace) -> int:
    cfg = _config(ns)
    pid = daemon.read_pid(cfg.pid_file)
    if pid and daemon.pid_alive(pid):
        return 0  # already running for this project
    if ns.daemon:
        daemon.check_run_dir(cfg.run_dir)
        _daemonize(cfg.run_dir / "container-gateway.log")  # Task 15 integration run covers this path
    return asyncio.run(daemon.run(cfg))


def cmd_stop(ns: argparse.Namespace) -> int:
    cfg = _config(ns)
    pid = daemon.read_pid(cfg.pid_file)
    if not pid or not daemon.pid_alive(pid):
        return 0
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and daemon.pid_alive(pid):
        time.sleep(0.1)
    return 0 if not daemon.pid_alive(pid) else 1


def cmd_status(ns: argparse.Namespace) -> int:
    cfg = _config(ns)
    p = daemon.paths(cfg.run_dir)
    pid = daemon.read_pid(cfg.pid_file)
    running = bool(pid and daemon.pid_alive(pid))
    sockets = {k: (str(p[k]) if running and p[k].exists() else None) for k in ("podman", "docker")}
    backends = [k for k, v in sockets.items() if v is not None]
    print(
        json.dumps(
            {"running": running, "pid": pid if running else None, "sockets": sockets, "backends": backends}
        )
    )
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
