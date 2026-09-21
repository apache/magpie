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

"""Find the daemon sockets the gateway may forward to. Each backend is optional."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

Runner = Callable[[list[str]], str | None]


@dataclass(frozen=True)
class Backend:
    kind: str
    socket: Path
    host_alias: str
    started_service: bool = False


def default_runner(argv: list[str]) -> str | None:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def host_alias(kind: str, platform: str) -> str:
    if platform == "Darwin":
        return "host.containers.internal" if kind == "podman" else "host.docker.internal"
    return "10.88.0.1" if kind == "podman" else "172.17.0.1"


def _podman_socket(platform: str, env: Mapping[str, str], run: Runner) -> list[Path]:
    if platform == "Darwin":
        out = run(["podman", "machine", "inspect", "--format", "{{.ConnectionInfo.PodmanSocket.Path}}"])
        if not out:
            return []
        reported = Path(out)
        # `podman machine inspect` builds that path from the *caller's* TMPDIR,
        # not from the machine's. A caller whose TMPDIR differs from the one the
        # machine was started under -- an agent, a hook, a launchd service -- is
        # told a path that does not exist, and discovery finds no backend on a
        # host where podman works fine by hand. Only the basename is stable, so
        # also look for it under the per-user temp directory, which `getconf`
        # reports regardless of the environment.
        candidates = [reported]
        user_temp = run(["getconf", "DARWIN_USER_TEMP_DIR"])
        if user_temp:
            candidates.append(Path(user_temp, "podman", reported.name))
        return candidates
    runtime_dir = env.get("XDG_RUNTIME_DIR")
    return [Path(runtime_dir, "podman", "podman.sock")] if runtime_dir else []


def _docker_socket(platform: str, env: Mapping[str, str], run: Runner) -> list[Path]:
    if platform == "Darwin":
        candidates = []
        out = run(["docker", "context", "inspect", "--format", '{{(index .Endpoints "docker").Host}}'])
        if out and out.startswith("unix://"):
            candidates.append(Path(out[len("unix://") :]))
        home = env.get("HOME")
        if home:
            candidates.append(Path(home, ".docker", "run", "docker.sock"))
        return candidates
    return [Path("/var/run/docker.sock")]


def discover(
    platform: str,
    env: Mapping[str, str],
    run: Runner,
    exists: Callable[[Path], bool],
    wanted: frozenset[str],
) -> list[Backend]:
    found: list[Backend] = []
    for kind, finder in (("podman", _podman_socket), ("docker", _docker_socket)):
        if kind not in wanted:
            continue
        for sock in finder(platform, env, run):
            if exists(sock):
                found.append(Backend(kind, sock, host_alias(kind, platform)))
                break
    return found


def egress_proxy_env(backend: Backend, port: int) -> dict[str, str]:
    url = f"http://{backend.host_alias}:{port}"
    return {"HTTP_PROXY": url, "HTTPS_PROXY": url, "NO_PROXY": f"localhost,127.0.0.1,{backend.host_alias}"}
