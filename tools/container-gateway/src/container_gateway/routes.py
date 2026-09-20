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
"""Map Docker-compatible and libpod API paths to (family, action, name)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

_VERSION_RE = re.compile(r"^/v\d+(?:\.\d+){1,2}(?=/|$)")

# Whole families we never forward. Anything under these prefixes is DENIED.
_DENIED_PREFIXES = (
    "swarm",
    "services",
    "tasks",
    "nodes",
    "plugins",
    "secrets",
    "configs",
    "distribution",
    "session",
)

# Single-segment system endpoints.
_SYSTEM = {"_ping": "ping", "version": "version", "info": "info", "events": "events"}


class Family(str, Enum):  # noqa: UP042
    CONTAINERS = "containers"
    PODS = "pods"
    EXEC = "exec"
    IMAGES = "images"
    BUILD = "build"
    VOLUMES = "volumes"
    NETWORKS = "networks"
    SYSTEM = "system"
    DENIED = "denied"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Route:
    family: Family
    action: str
    name: str | None
    libpod: bool
    version: str | None


def strip_version(path: str) -> tuple[str, str | None, bool]:
    version: str | None = None
    m = _VERSION_RE.match(path)
    if m:
        version = m.group(0)[1:]
        path = path[m.end() :] or "/"
    libpod = False
    if path.startswith("/libpod/"):
        libpod = True
        path = path[len("/libpod") :]
    return path, version, libpod


# Trailing segments that are verbs. The name is everything between the family
# segment and the verb, which lets image names carry registries and tags.
_VERBS = {
    "json",
    "start",
    "stop",
    "kill",
    "restart",
    "pause",
    "unpause",
    "wait",
    "logs",
    "top",
    "stats",
    "rename",
    "update",
    "archive",
    "export",
    "commit",
    "attach",
    "exec",
    "resize",
    "changes",
    "tag",
    "history",
    "push",
    "get",
    "connect",
    "disconnect",
    "healthcheck",
    "mount",
    "unmount",
    "init",
    "checkpoint",
    "restore",
    "generate",
    "play",
    "exists",
}


def _split(path: str) -> tuple[str, list[str]]:
    parts = [p for p in path.split("/") if p]
    return (parts[0] if parts else ""), parts[1:]


def route(method: str, path: str) -> Route:
    clean, version, libpod = strip_version(path)
    head, rest = _split(clean)
    method = method.upper()

    if head in _SYSTEM and not rest:
        return Route(Family.SYSTEM, _SYSTEM[head], None, libpod, version)
    if head == "system" and rest and rest[0] in ("df", "events", "ping", "info", "version"):
        return Route(Family.SYSTEM, rest[0], None, libpod, version)
    if (
        head == "auth"
        or head.startswith(_DENIED_PREFIXES)
        or (head == "system" and rest and rest[0] == "dial-stdio")
    ):
        return Route(Family.DENIED, head if head != "system" else rest[0], None, libpod, version)
    if head == "build":
        return Route(Family.BUILD, "build", None, libpod, version)
    if head == "exec" and rest:
        exec_verb = rest[-1] if len(rest) > 1 else ""
        action = {"start": "exec_start", "json": "exec_inspect", "resize": "exec_resize"}.get(
            exec_verb, "unknown"
        )
        return Route(Family.EXEC, action, rest[0], libpod, version)

    family = {
        "containers": Family.CONTAINERS,
        "pods": Family.PODS,
        "images": Family.IMAGES,
        "volumes": Family.VOLUMES,
        "networks": Family.NETWORKS,
    }.get(head)
    if family is None:
        return Route(Family.UNKNOWN, head or "root", None, libpod, version)

    if not rest:
        # GET /volumes, GET /networks are lists; nothing else is a bare family call.
        return Route(family, "list" if method == "GET" else "unknown", None, libpod, version)
    if len(rest) == 1 and rest[0] in ("json", "create", "prune", "load", "get", "search"):
        action = {
            "json": "list",
            "create": "pull" if family is Family.IMAGES else "create",
            "get": "save",
        }.get(rest[0], rest[0])
        return Route(family, action, None, libpod, version)

    verb: str | None = rest[-1] if rest[-1] in _VERBS else None
    name = "/".join(rest[:-1] if verb else rest)
    if verb is None:
        action = "remove" if method == "DELETE" else "inspect" if method == "GET" else "unknown"
    elif verb == "json":
        action = "inspect"
    elif verb == "get":
        action = "save"
    elif verb == "push":
        return Route(Family.DENIED, "push", name, libpod, version)
    else:
        assert verb is not None
        action = verb
    return Route(family, action, name, libpod, version)


def name_span(method: str, path: str) -> tuple[int, int] | None:
    """The segment range ``route()``'s ``name`` occupies in ``path``.

    Indices are into ``[s for s in path.split("/") if s]`` -- the same
    filtered segment list ``route()`` itself classifies -- shifted past the
    version and ``/libpod`` prefixes ``strip_version`` removes and past the
    family segment. ``None`` when the route carries no name.

    The relay splices a resolved ID over exactly this range. Replacing the
    first textual ``/<name>/`` instead would rewrite the wrong segment for a
    resource legally named ``containers``, ``libpod`` or ``v1.45``:
    ``/v1.45/containers/containers/start`` would become
    ``/v1.45/aaa111/containers/start``, leaving the client's own name at the
    position the daemon acts on.
    """
    named = route(method, path)
    if named.name is None:
        return None
    clean, version, libpod = strip_version(path)
    head, rest = _split(clean)
    if not rest:
        return None
    offset = (1 if version else 0) + (1 if libpod else 0) + 1
    if head == "exec":
        # `route()` takes only rest[0] as the exec id, whatever follows it.
        return offset, offset + 1
    end = len(rest) - 1 if rest[-1] in _VERBS else len(rest)
    return (offset, offset + end) if end > 0 else None


ACT_BY_NAME: frozenset[tuple[Family, str]] = frozenset(
    {
        (Family.CONTAINERS, a)
        for a in (
            "inspect",
            "start",
            "stop",
            "kill",
            "restart",
            "pause",
            "unpause",
            "wait",
            "remove",
            "logs",
            "top",
            "stats",
            "rename",
            "update",
            "archive",
            "export",
            "commit",
            "attach",
            "exec",
            "resize",
            "changes",
            "healthcheck",
            "mount",
            "unmount",
            "init",
            "exists",
        )
    }
    | {
        (Family.PODS, a)
        for a in (
            "inspect",
            "start",
            "stop",
            "kill",
            "restart",
            "pause",
            "unpause",
            "remove",
            "top",
            "stats",
            "exists",
        )
    }
    | {(Family.EXEC, a) for a in ("exec_start", "exec_inspect", "exec_resize")}
    | {(Family.IMAGES, a) for a in ("remove", "tag")}
    | {(Family.VOLUMES, a) for a in ("inspect", "remove", "exists")}
    | {(Family.NETWORKS, a) for a in ("inspect", "remove", "connect", "disconnect", "exists")}
)

LIST_LIKE: frozenset[tuple[Family, str]] = frozenset(
    {(f, "list") for f in (Family.CONTAINERS, Family.PODS, Family.VOLUMES, Family.NETWORKS)}
    | {(f, "prune") for f in (Family.CONTAINERS, Family.PODS, Family.VOLUMES, Family.NETWORKS, Family.IMAGES)}
    | {(Family.SYSTEM, "events"), (Family.SYSTEM, "df")}
)
