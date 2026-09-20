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
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from container_gateway import backends, daemon

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


def _short_project_dir() -> Path:
    """A project root short enough that its gateway socket fits ``sun_path``.

    ``pytest``'s own ``tmp_path`` / ``tmp_path_factory.mktemp`` fixtures nest
    under ``pytest-of-<user>/pytest-<n>/<test-name>/`` inside ``$TMPDIR``,
    which on a normal macOS ``TMPDIR`` (``/var/folders/<2>/<~30>/T/``) is
    already long enough that adding
    ``.apache-magpie-local/run/<kind>.sock`` (36 bytes) blows the ~103-byte
    ``sun_path`` limit. ``tempfile.mkdtemp()`` sits directly under
    ``$TMPDIR`` with none of that nesting, exactly like
    ``tests/test_daemon.py``'s ``short_run_dir`` fixture, so it stays short
    everywhere ``tmp_path`` might not.
    """
    return Path(tempfile.mkdtemp(prefix="cg-"))


def _check_socket_path_length(project: Path, kind: str) -> Path:
    sock = project / ".apache-magpie-local" / "run" / f"{kind}.sock"
    length = len(str(sock).encode())
    assert length <= daemon.MAX_SUN_PATH, (
        f"gateway socket path is {length} bytes (limit {daemon.MAX_SUN_PATH}): {sock} "
        "-- the project root fixture is not short enough for this host's TMPDIR"
    )
    return sock


def _stop(proc: subprocess.Popen[bytes]) -> None:
    """Terminate a gateway subprocess, escalating to a hard kill if it ignores SIGTERM."""
    proc.terminate()
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(5)


def _wait_for_socket(sock: Path, attempts: int = 50, interval: float = 0.1) -> bool:
    for _ in range(attempts):
        if sock.exists():
            return True
        time.sleep(interval)
    return False


@pytest.fixture(scope="module")
def gateway() -> Iterator[tuple[Path, str]]:
    b = _backend()
    cli = shutil.which(b.kind) if b else None
    if b is None or cli is None:
        pytest.skip("no podman/docker backend on this host")
    project = _short_project_dir()
    try:
        (project / "data").mkdir()
        sock = _check_socket_path_length(project, b.kind)
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "container_gateway",
                "serve",
                "--project",
                str(project),
                "--egress",
                "off",
            ],
            env=env,
        )
        try:
            if not _wait_for_socket(sock):
                pytest.fail("gateway did not come up")
        except BaseException:
            _stop(proc)
            raise
        yield project, cli
        _stop(proc)
    finally:
        shutil.rmtree(project, ignore_errors=True)


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


def test_other_project_is_invisible(gateway: tuple[Path, str]) -> None:
    project, cli = gateway
    _run(cli, project, "run", "-d", "--name", "gw-it-sleeper", "docker.io/library/alpine:3", "sleep", "30")
    try:
        mine = json.loads(_run(cli, project, "ps", "-a", "--format", "json").stdout or "[]")
        assert any("gw-it-sleeper" in json.dumps(c) for c in (mine if isinstance(mine, list) else [mine]))
        other = _short_project_dir()
        try:
            other_kind = Path(cli).name
            other_sock = _check_socket_path_length(other, other_kind)
            env = {**os.environ, "PYTHONPATH": str(SRC)}
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "container_gateway",
                    "serve",
                    "--project",
                    str(other),
                    "--egress",
                    "off",
                ],
                env=env,
            )
            try:
                assert _wait_for_socket(other_sock), "second gateway did not come up"
                theirs = _run(cli, other, "ps", "-a", "--format", "json").stdout
                assert "gw-it-sleeper" not in theirs
                denied = _run(cli, other, "rm", "-f", "gw-it-sleeper")
                assert "label-check" in denied.stderr
            finally:
                _stop(proc)
        finally:
            shutil.rmtree(other, ignore_errors=True)
    finally:
        _run(cli, project, "rm", "-f", "gw-it-sleeper")
