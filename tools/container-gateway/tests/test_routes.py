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
"""API path routing covers both the compat and the libpod path families."""

from __future__ import annotations

import pytest

from container_gateway.routes import ACT_BY_NAME, LIST_LIKE, Family, name_span, route, strip_version


@pytest.mark.parametrize(
    ("raw", "path", "version", "libpod"),
    [
        ("/v1.45/containers/json", "/containers/json", "v1.45", False),
        ("/containers/json", "/containers/json", None, False),
        ("/v5.2.0/libpod/containers/json", "/containers/json", "v5.2.0", True),
        ("/libpod/pods/create", "/pods/create", None, True),
        ("/_ping", "/_ping", None, False),
    ],
)
def test_strip_version(raw: str, path: str, version: str | None, libpod: bool) -> None:
    assert strip_version(raw) == (path, version, libpod)


@pytest.mark.parametrize(
    ("method", "path", "family", "action", "name"),
    [
        ("GET", "/v1.45/containers/json", Family.CONTAINERS, "list", None),
        ("POST", "/v1.45/containers/create", Family.CONTAINERS, "create", None),
        ("GET", "/v1.45/containers/web1/json", Family.CONTAINERS, "inspect", "web1"),
        ("POST", "/v1.45/containers/web1/start", Family.CONTAINERS, "start", "web1"),
        ("DELETE", "/v1.45/containers/web1", Family.CONTAINERS, "remove", "web1"),
        ("POST", "/v1.45/containers/web1/exec", Family.CONTAINERS, "exec", "web1"),
        ("POST", "/v1.45/exec/abc/start", Family.EXEC, "exec_start", "abc"),
        ("GET", "/v1.45/exec/abc/json", Family.EXEC, "exec_inspect", "abc"),
        ("POST", "/v1.45/containers/prune", Family.CONTAINERS, "prune", None),
        ("GET", "/v1.45/containers/web1/archive", Family.CONTAINERS, "archive", "web1"),
        ("PUT", "/v1.45/containers/web1/archive", Family.CONTAINERS, "archive", "web1"),
        ("POST", "/v5.2.0/libpod/pods/create", Family.PODS, "create", None),
        ("POST", "/v5.2.0/libpod/pods/p1/start", Family.PODS, "start", "p1"),
        ("GET", "/v1.45/images/json", Family.IMAGES, "list", None),
        ("POST", "/v1.45/images/create", Family.IMAGES, "pull", None),
        ("GET", "/v1.45/images/alpine:3/json", Family.IMAGES, "inspect", "alpine:3"),
        ("DELETE", "/v1.45/images/alpine:3", Family.IMAGES, "remove", "alpine:3"),
        ("POST", "/v1.45/images/alpine:3/push", Family.DENIED, "push", "alpine:3"),
        ("POST", "/v1.45/build", Family.BUILD, "build", None),
        ("POST", "/v1.45/volumes/create", Family.VOLUMES, "create", None),
        ("GET", "/v1.45/volumes", Family.VOLUMES, "list", None),
        ("POST", "/v1.45/networks/n1/connect", Family.NETWORKS, "connect", "n1"),
        ("GET", "/_ping", Family.SYSTEM, "ping", None),
        ("GET", "/v1.45/info", Family.SYSTEM, "info", None),
        ("GET", "/v1.45/events", Family.SYSTEM, "events", None),
        ("POST", "/v1.45/auth", Family.DENIED, "auth", None),
        ("GET", "/v1.45/swarm", Family.DENIED, "swarm", None),
        ("GET", "/v1.45/secrets", Family.DENIED, "secrets", None),
        ("GET", "/v1.45/plugins", Family.DENIED, "plugins", None),
        ("GET", "/v1.45/frobnicate", Family.UNKNOWN, "frobnicate", None),
    ],
)
def test_route(method: str, path: str, family: Family, action: str, name: str | None) -> None:
    r = route(method, path)
    assert (r.family, r.action, r.name) == (family, action, name)


def test_image_names_with_slashes_and_tags_are_one_name() -> None:
    r = route("GET", "/v1.45/images/quay.io/podman/hello:latest/json")
    assert r.family is Family.IMAGES and r.action == "inspect"
    assert r.name == "quay.io/podman/hello:latest"


def test_act_by_name_and_list_like_sets() -> None:
    assert (Family.CONTAINERS, "start") in ACT_BY_NAME
    assert (Family.CONTAINERS, "create") not in ACT_BY_NAME
    assert (Family.IMAGES, "inspect") not in ACT_BY_NAME
    assert (Family.IMAGES, "remove") in ACT_BY_NAME
    assert (Family.CONTAINERS, "list") in LIST_LIKE
    assert (Family.SYSTEM, "events") in LIST_LIKE
    assert (Family.VOLUMES, "prune") in LIST_LIKE


# --- Fix round 1 additions below ---


@pytest.mark.parametrize(
    ("method", "path", "span"),
    [
        ("POST", "/v1.45/containers/mine/start", (2, 3)),
        ("POST", "/containers/mine/start", (1, 2)),
        ("POST", "/v1.45/containers/containers/start", (2, 3)),
        ("POST", "/v1.45/containers/v1.45/start", (2, 3)),
        ("POST", "/v1.45/containers/libpod/start", (2, 3)),
        ("POST", "/v1.45/libpod/containers/mine/start", (3, 4)),
        ("POST", "/libpod/containers/mine/start", (2, 3)),
        ("DELETE", "/v1.45/images/quay.io/podman/hello:latest", (2, 5)),
        ("POST", "/v1.45/exec/ex1/start", (2, 3)),
        ("GET", "/v1.45/containers/json", None),
        ("GET", "/_ping", None),
        ("POST", "/v1.45/containers/create", None),
    ],
)
def test_name_span_matches_the_route_name(method: str, path: str, span: tuple[int, int] | None) -> None:
    assert name_span(method, path) == span
    segments = [s for s in path.split("/") if s]
    expected = route(method, path).name
    assert (None if span is None else "/".join(segments[span[0] : span[1]])) == expected
