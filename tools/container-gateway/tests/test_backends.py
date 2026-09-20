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

from pathlib import Path

from container_gateway.backends import Backend, discover, egress_proxy_env, host_alias

ALL = frozenset({"podman", "docker"})


def test_podman_machine_on_darwin() -> None:
    sock = Path("/var/folders/x/T/podman/podman-machine-default-api.sock")

    def run(argv: list[str]) -> str | None:
        if argv[:3] == ["podman", "machine", "inspect"]:
            return str(sock)
        return None

    found = discover("Darwin", {}, run, lambda p: p == sock, ALL)
    assert found == [Backend("podman", sock, "host.containers.internal")]


def test_machine_socket_missing_means_no_backend() -> None:
    run = lambda argv: "/nope.sock" if argv[:2] == ["podman", "machine"] else None  # noqa: E731
    assert discover("Darwin", {}, run, lambda p: False, ALL) == []


def test_rootless_podman_on_linux() -> None:
    sock = Path("/run/user/1000/podman/podman.sock")
    found = discover("Linux", {"XDG_RUNTIME_DIR": "/run/user/1000"}, lambda a: None, lambda p: p == sock, ALL)
    assert found == [Backend("podman", sock, "10.88.0.1")]


def test_docker_desktop_context_then_fallback() -> None:
    ctx_sock = Path("/Users/a/.docker/run/docker.sock")

    def run(argv: list[str]) -> str | None:
        if argv[:3] == ["docker", "context", "inspect"]:
            return f"unix://{ctx_sock}"
        return None

    found = discover("Darwin", {"HOME": "/Users/a"}, run, lambda p: p == ctx_sock, ALL)
    assert found == [Backend("docker", ctx_sock, "host.docker.internal")]
    fallback = discover("Darwin", {"HOME": "/Users/a"}, lambda a: None, lambda p: p == ctx_sock, ALL)
    assert fallback == [Backend("docker", ctx_sock, "host.docker.internal")]


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
