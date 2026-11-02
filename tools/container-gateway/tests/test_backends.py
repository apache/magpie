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

"""Backend discovery is table-driven and testable without a daemon."""

from __future__ import annotations

import hashlib
import json
import socket
import tempfile
from pathlib import Path

import pytest

from container_gateway.backends import Backend, discover, egress_proxy_env, host_alias, socket_answers

ALL = frozenset({"podman", "docker"})


def test_podman_machine_on_darwin() -> None:
    sock = Path("/var/folders/x/T/podman/podman-machine-default-api.sock")

    def run(argv: list[str]) -> str | None:
        if argv[:3] == ["podman", "machine", "inspect"]:
            return str(sock)
        return None

    found = discover("Darwin", {}, run, lambda p: p == sock, ALL)
    assert found == [Backend("podman", sock, "host.containers.internal")]


def test_podman_machine_path_reported_under_a_foreign_tmpdir() -> None:
    # `podman machine inspect` renders the socket path from the caller's TMPDIR,
    # so a hook or agent with a different TMPDIR is told a path that does not
    # exist. Discovery must still find the socket the machine really listens on.
    reported = Path("/tmp/podman/podman-machine-default-api.sock")
    real = Path("/var/folders/sm/xxx/T/podman/podman-machine-default-api.sock")

    def run(argv: list[str]) -> str | None:
        if argv[:3] == ["podman", "machine", "inspect"]:
            return str(reported)
        if argv == ["getconf", "DARWIN_USER_TEMP_DIR"]:
            return "/var/folders/sm/xxx/T/"
        return None

    found = discover("Darwin", {}, run, lambda p: p == real, ALL)
    assert found == [Backend("podman", real, "host.containers.internal")]


def test_machine_socket_missing_means_no_backend() -> None:
    run = lambda argv: "/nope.sock" if argv[:2] == ["podman", "machine"] else None  # noqa: E731
    assert discover("Darwin", {}, run, lambda p: False, ALL) == []


def test_rootless_podman_on_linux() -> None:
    sock = Path("/run/user/1000/podman/podman.sock")
    found = discover("Linux", {"XDG_RUNTIME_DIR": "/run/user/1000"}, lambda a: None, lambda p: p == sock, ALL)
    assert found == [Backend("podman", sock, "10.88.0.1")]


def _docker_context(home: Path, current: str | None, contexts: dict[str, str]) -> None:
    """Lay out the docker CLI's config and context store the way the CLI writes them."""
    config_dir = home / ".docker"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {} if current is None else {"currentContext": current}
    (config_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    for name, host in contexts.items():
        meta = config_dir / "contexts" / "meta" / hashlib.sha256(name.encode()).hexdigest()
        meta.mkdir(parents=True)
        body = {"Name": name, "Metadata": {}, "Endpoints": {"docker": {"Host": host, "SkipTLSVerify": False}}}
        (meta / "meta.json").write_text(json.dumps(body), encoding="utf-8")


def _no_docker_cli(argv: list[str]) -> str | None:
    assert argv[0] != "docker", "discovery must not depend on a docker CLI on PATH"
    return None


def test_docker_current_context_read_from_the_context_store(tmp_path: Path) -> None:
    # Colima, or any non-default context: its socket is not Docker Desktop's.
    colima = Path("/Users/a/.colima/default/docker.sock")
    _docker_context(
        tmp_path,
        "colima",
        {"colima": f"unix://{colima}", "desktop-linux": f"unix://{tmp_path}/.docker/run/docker.sock"},
    )
    found = discover("Darwin", {"HOME": str(tmp_path)}, _no_docker_cli, lambda p: p == colima, ALL)
    assert found == [Backend("docker", colima, "host.docker.internal")]


def test_docker_current_context_read_from_docker_config(tmp_path: Path) -> None:
    # DOCKER_CONFIG moves the CLI's config.json and context store out of ~/.docker.
    colima = Path("/Users/a/.colima/default/docker.sock")
    _docker_context(tmp_path / "elsewhere", "colima", {"colima": f"unix://{colima}"})
    env = {"HOME": str(tmp_path), "DOCKER_CONFIG": str(tmp_path / "elsewhere" / ".docker")}
    found = discover("Darwin", env, _no_docker_cli, lambda p: p == colima, ALL)
    assert found == [Backend("docker", colima, "host.docker.internal")]


def test_docker_context_socket_that_does_not_answer_falls_back(tmp_path: Path) -> None:
    desktop = tmp_path / ".docker" / "run" / "docker.sock"
    _docker_context(tmp_path, "colima", {"colima": "unix:///Users/a/.colima/default/docker.sock"})
    found = discover("Darwin", {"HOME": str(tmp_path)}, _no_docker_cli, lambda p: p == desktop, ALL)
    assert found == [Backend("docker", desktop, "host.docker.internal")]


@pytest.mark.parametrize(
    "current, contexts",
    [
        ("default", {}),  # the default context is DOCKER_HOST, which names the gateway in a session
        (None, {}),  # no currentContext key
        ("gone", {}),  # current context without metadata
        ("remote", {"remote": "tcp://10.0.0.1:2376"}),  # not a Unix socket
    ],
)
def test_docker_without_a_usable_context_uses_the_desktop_socket(
    tmp_path: Path, current: str | None, contexts: dict[str, str]
) -> None:
    desktop = tmp_path / ".docker" / "run" / "docker.sock"
    _docker_context(tmp_path, current, contexts)
    found = discover("Darwin", {"HOME": str(tmp_path)}, _no_docker_cli, lambda p: p == desktop, ALL)
    assert found == [Backend("docker", desktop, "host.docker.internal")]


def test_docker_config_that_is_not_json_uses_the_desktop_socket(tmp_path: Path) -> None:
    desktop = tmp_path / ".docker" / "run" / "docker.sock"
    (tmp_path / ".docker").mkdir()
    (tmp_path / ".docker" / "config.json").write_text("{not json", encoding="utf-8")
    found = discover("Darwin", {"HOME": str(tmp_path)}, _no_docker_cli, lambda p: p == desktop, ALL)
    assert found == [Backend("docker", desktop, "host.docker.internal")]


def test_socket_answers_rejects_what_is_not_a_socket(tmp_path: Path) -> None:
    regular = tmp_path / "file.sock"
    regular.write_text("", encoding="utf-8")
    assert not socket_answers(regular)
    assert not socket_answers(tmp_path / "missing.sock")


def test_socket_answers_only_while_something_listens() -> None:
    # A short directory: pytest's tmp_path overflows the AF_UNIX path limit on macOS.
    with tempfile.TemporaryDirectory(prefix="cg") as d:
        live = Path(d, "live.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            try:
                server.bind(str(live))
            except PermissionError:
                pytest.skip("sandbox denies unix bind; runs in CI")
                # Unreachable: pytest.skip() raises. The bare re-raise tells a
                # static analyser the except branch never falls through.
                raise
            server.listen(1)
            assert socket_answers(live)

        # The listener is gone but its socket file stays, as after a daemon stops.
        assert live.exists()
        assert not socket_answers(live)


def test_dockerd_on_linux_and_wanted_filter() -> None:
    sock = Path("/var/run/docker.sock")
    assert discover("Linux", {}, lambda a: None, lambda p: p == sock, ALL) == [
        Backend("docker", sock, "172.17.0.1")
    ]
    assert discover("Linux", {}, lambda a: None, lambda p: p == sock, frozenset({"podman"})) == []


def test_both_backends_podman_first() -> None:
    p = Path("/run/user/1/podman/podman.sock")
    d = Path("/var/run/docker.sock")
    found = discover("Linux", {"XDG_RUNTIME_DIR": "/run/user/1"}, lambda a: None, lambda x: x in (p, d), ALL)
    assert [b.kind for b in found] == ["podman", "docker"]


def test_egress_env() -> None:
    b = Backend("podman", Path("/s"), "host.containers.internal")
    assert egress_proxy_env(b, 8899) == {
        "HTTP_PROXY": "http://host.containers.internal:8899",
        "HTTPS_PROXY": "http://host.containers.internal:8899",
        "NO_PROXY": "localhost,127.0.0.1,host.containers.internal",
    }


def test_host_alias_table() -> None:
    assert host_alias("podman", "Darwin") == "host.containers.internal"
    assert host_alias("docker", "Darwin") == "host.docker.internal"
    assert host_alias("docker", "Linux") == "172.17.0.1"
    assert host_alias("podman", "Linux") == "10.88.0.1"
