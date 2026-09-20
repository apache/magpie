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

"""Against a real backend, when one is present. Skipped otherwise."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from container_gateway import backends

pytestmark = pytest.mark.integration
SRC = Path(__file__).resolve().parents[1] / "src"


def _exists(p: Path) -> bool:
    """``Path.exists`` without raising: a sandboxed session denies ``stat()``.

    on some candidate socket paths (e.g. ``~/.docker/run/docker.sock``) with
    ``PermissionError`` rather than reporting "missing", so this test module
    must not let that surface as a collection/test error -- it must fall
    through to "no backend found" and skip cleanly instead.
    """
    try:
        return p.exists()
    except OSError:
        return False


def _backend() -> backends.Backend | None:
    found = backends.discover(
        platform.system(),
        os.environ,
        backends.default_runner,
        _exists,
        frozenset({"podman", "docker"}),
    )
    return found[0] if found else None


@pytest.fixture(scope="module")
def gateway(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, str]]:
    b = _backend()
    cli = shutil.which(b.kind) if b else None
    if b is None or cli is None:
        pytest.skip("no podman/docker backend on this host")
    project = tmp_path_factory.mktemp("proj")
    (project / "data").mkdir()
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "container_gateway", "serve", "--project", str(project), "--egress", "off"],
        env=env,
    )
    sock = project / ".apache-magpie-local" / "run" / f"{b.kind}.sock"
    for _ in range(50):
        if sock.exists():
            break
        time.sleep(0.1)
    else:
        proc.terminate()
        pytest.fail("gateway did not come up")
    yield project, cli
    proc.terminate()
    proc.wait(10)


def _run(cli: str, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    kind = Path(cli).name
    var = "CONTAINER_HOST" if kind == "podman" else "DOCKER_HOST"
    sock = project / ".apache-magpie-local" / "run" / f"{kind}.sock"
    return subprocess.run(
        [cli, *args], capture_output=True, text=True, env={**os.environ, var: f"unix://{sock}"}, check=False
    )


def test_run_with_project_bind_mount(gateway: tuple[Path, str]) -> None:
    project, cli = gateway
    done = _run(
        cli,
        project,
        "run",
        "--rm",
        "-v",
        f"{project / 'data'}:/data",
        "docker.io/library/alpine:3",
        "sh",
        "-c",
        "echo hi > /data/out",
    )
    assert done.returncode == 0, done.stderr
    assert (project / "data" / "out").read_text() == "hi\n"


def test_home_bind_mount_is_refused(gateway: tuple[Path, str]) -> None:
    project, cli = gateway
    done = _run(cli, project, "run", "--rm", "-v", f"{Path.home()}:/h", "docker.io/library/alpine:3", "true")
    assert done.returncode != 0
    assert "container-gateway: bind-mount" in done.stderr


def test_privileged_is_refused(gateway: tuple[Path, str]) -> None:
    project, cli = gateway
    done = _run(cli, project, "run", "--rm", "--privileged", "docker.io/library/alpine:3", "true")
    assert "container-gateway: privileged" in done.stderr


def test_other_project_is_invisible(gateway: tuple[Path, str], tmp_path: Path) -> None:
    project, cli = gateway
    _run(cli, project, "run", "-d", "--name", "gw-it-sleeper", "docker.io/library/alpine:3", "sleep", "30")
    try:
        mine = json.loads(_run(cli, project, "ps", "-a", "--format", "json").stdout or "[]")
        assert any("gw-it-sleeper" in json.dumps(c) for c in (mine if isinstance(mine, list) else [mine]))
        other = tmp_path / "other"
        other.mkdir()
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        proc = subprocess.Popen(
            [sys.executable, "-m", "container_gateway", "serve", "--project", str(other), "--egress", "off"],
            env=env,
        )
        try:
            time.sleep(1.5)
            theirs = _run(cli, other, "ps", "-a", "--format", "json").stdout
            assert "gw-it-sleeper" not in theirs
            denied = _run(cli, other, "rm", "-f", "gw-it-sleeper")
            assert "label-check" in denied.stderr
        finally:
            proc.terminate()
            proc.wait(10)
    finally:
        _run(cli, project, "rm", "-f", "gw-it-sleeper")
