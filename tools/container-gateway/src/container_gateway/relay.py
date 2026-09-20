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
"""Relay one client connection to the backend under the policy in decisions.py.

Two rules hold everywhere in this module:

*Nothing is forwarded that the policy has not seen.* Every path out of
``_one``/``_forward`` either returns before the backend connection is
opened, or forwards exactly the request ``decide()`` approved -- the start
line is rebuilt from the parsed method and ``Request.raw_target()``, never
copied from the client's own start line, so a target the policy read
differently than the daemon would cannot survive the trip.

*A failed label check answers 403, never 404.* The client is inside the
sandbox and the daemon is root-equivalent on the host; answering 404 for
"exists but belongs to another project" and 403 for "yours" would turn the
gateway into an existence oracle for every other project's containers. The
same reasoning makes every indeterminate backend answer (unreachable,
unparsable, an error status) deny rather than pass: the check fails
closed.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .decisions import Allow, Request, decide
from .http import Head, HttpError, error_response, parse_request_line, pipe, pump, read_body, read_head
from .labels import LABEL_KEY, has_label
from .policy import Deny, PolicyContext, named_networks, named_volumes
from .routes import Family, Route
from .routes import route as route_of

log = logging.getLogger("container-gateway")

# Actions whose request body is JSON the policy must see. Everything else
# (build contexts, archives, image loads) streams through after URL checks.
_BUFFERED_ACTIONS = frozenset(
    {
        "create",
        "exec",
        "exec_start",
        "exec_resize",
        "update",
        "rename",
        "connect",
        "disconnect",
        "pull",
        "commit",
        "wait",
    }
)

# A resource identifier read back out of a daemon inspect payload, before it
# is spliced into the forwarded request target. Digests (``sha256:...``) and
# fully-qualified image references are legal here; a path separator, a space
# or a percent sign is not -- those would change how the daemon parses the
# request line the gateway just rebuilt.
_IDENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,254}")

# A volume / network name taken out of a create body, before it is spliced
# into an inspect URL. Narrower than `_IDENT_RE` (this one is entirely
# client-controlled, and `decide()` does not validate body-borne resource
# names the way it validates the request path).
_RESOURCE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}")

Connector = Callable[[], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]]
Handler = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


def unix_connector(path: Path) -> Connector:
    """The production connector: a fresh unix-socket connection per backend call."""
    return functools.partial(asyncio.open_unix_connection, str(path))


class Relay:
    def __init__(
        self,
        connect: Connector,
        ctx: PolicyContext,
        *,
        backend_label: str = "",
        json_limit: int = 8 * 1024 * 1024,
    ) -> None:
        self.connect = connect
        self.ctx = ctx
        self.backend_label = backend_label
        self.json_limit = json_limit

    # ------------------------------------------------------------ backend
    async def _connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await self.connect()

    async def _request_json(
        self, method: str, target: str, payload: Any | None = None
    ) -> tuple[int | None, Any]:
        """One short JSON call the relay makes on its own behalf (never the client's).

        Returns ``(status, parsed body)``. ``status`` is ``None`` when the
        call could not be completed at all -- the connector refused, the
        response was unframable, the connection died mid-body -- and the
        body is ``None`` when it was absent or not JSON. Every caller treats
        an unknown status as a failure.
        """
        try:
            reader, writer = await self._connect()
        except OSError as exc:
            log.debug("backend call %s %s could not connect: %s", method, target, exc)
            return None, None
        status: int | None = None
        try:
            head = Head(f"{method} {target} HTTP/1.1", [("Host", "docker"), ("Connection", "close")])
            body = b""
            if payload is not None:
                body = json.dumps(payload).encode()
                head.set("Content-Type", "application/json")
                head.set("Content-Length", str(len(body)))
            writer.write(head.encode() + body)
            await writer.drain()
            resp = await read_head(reader)
            if resp is None:
                return None, None
            status = int(resp.start_line.split(" ")[1])
            framed = resp.content_length is not None or resp.chunked
            raw = await read_body(reader, resp, self.json_limit) if framed else await reader.read()
            return status, (json.loads(raw) if raw else None)
        except (HttpError, OSError, ValueError, asyncio.IncompleteReadError) as exc:
            log.debug("backend call %s %s failed: %s", method, target, exc)
            return status, None
        finally:
            writer.close()

    async def _get_json(self, target: str) -> Any | None:
        status, payload = await self._request_json("GET", target)
        return payload if status is not None and 200 <= status < 300 else None

    async def resource_id_if_labelled(self, route: Route, name: str) -> str | None:
        """The resource's ID when it carries this project's label, else ``None``.

        ``None`` covers "no such resource" and "someone else's resource"
        alike -- the caller answers 403 either way.
        """
        if route.family is Family.EXEC:
            info = await self._get_json(_inspect_target(Family.EXEC, name, route.libpod))
            cid = info.get("ContainerID") if isinstance(info, dict) else None
            if not isinstance(cid, str) or not _IDENT_RE.fullmatch(cid):
                return None
            owner = await self._get_json(_inspect_target(Family.CONTAINERS, cid, route.libpod))
            return name if has_label(_labels_of(owner), self.ctx.slug) else None
        info = await self._get_json(_inspect_target(route.family, name, route.libpod))
        if not isinstance(info, dict) or not has_label(_labels_of(info), self.ctx.slug):
            return None
        ident = str(info.get("Id") or info.get("ID") or info.get("Name") or name)
        return ident if _IDENT_RE.fullmatch(ident) else name

    async def _resource_denial(self, allow: Allow) -> bytes | None:
        """403 payload for a named volume / network this project does not own.

        Only container and pod create bodies reference resources by name
        without naming them in the path, so only those need this second
        pass; ``label_check`` covers every act-by-name route.
        """
        route = allow.route
        if (route.family, route.action) not in ((Family.CONTAINERS, "create"), (Family.PODS, "create")):
            return None
        body = allow.request.body
        if not isinstance(body, dict):
            return None
        for name in named_volumes(body, route.libpod):
            denial = await self._volume_denial(name, route.libpod)
            if denial is not None:
                return denial
        for name in named_networks(body, route.libpod):
            denial = await self._network_denial(name, route.libpod)
            if denial is not None:
                return denial
        return None

    async def _volume_denial(self, name: str, libpod: bool) -> bytes | None:
        """An unknown volume is created labelled; a foreign one is refused."""
        if not _RESOURCE_NAME_RE.fullmatch(name):
            return _label_denial("volume", name)
        status, info = await self._request_json("GET", _inspect_target(Family.VOLUMES, name, libpod))
        if status == 404:
            await self._precreate_volume(name, libpod)
            return None
        if status is not None and 200 <= status < 300 and has_label(_labels_of(info), self.ctx.slug):
            return None
        return _label_denial("volume", name)

    async def _precreate_volume(self, name: str, libpod: bool) -> None:
        """Create the volume with this project's label before the daemon creates it without one."""
        target = "/libpod/volumes/create" if libpod else "/volumes/create"
        label = {LABEL_KEY: self.ctx.slug}
        payload = {"name": name, "labels": label} if libpod else {"Name": name, "Labels": label}
        status, _ = await self._request_json("POST", target, payload)
        if status is None or not (200 <= status < 300 or status == 409):
            log.warning(
                "pre-creating volume %s returned %s; the daemon may create it unlabelled", name, status
            )

    async def _network_denial(self, name: str, libpod: bool) -> bytes | None:
        """Networks are never auto-created, so an unknown one is refused too."""
        if not _RESOURCE_NAME_RE.fullmatch(name):
            return _label_denial("network", name)
        status, info = await self._request_json("GET", _inspect_target(Family.NETWORKS, name, libpod))
        if status == 404:
            return _denial(f"label-check: network {name} does not exist")
        if status is not None and 200 <= status < 300 and has_label(_labels_of(info), self.ctx.slug):
            return None
        return _label_denial("network", name)

    # ------------------------------------------------------------- client
    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Serve one client connection: keep-alive requests until close, upgrade or error."""
        try:
            while True:
                head = await read_head(reader)
                if head is None or not await self._one(head, reader, writer):
                    return
        except HttpError as exc:
            log.info("framing error from the client: %s", exc)
            with contextlib.suppress(OSError, RuntimeError):
                writer.write(error_response(400, f"container-gateway: {exc}"))
        except (OSError, asyncio.IncompleteReadError, ConnectionError) as exc:
            log.debug("client connection dropped: %s", exc)
        finally:
            writer.close()

    async def _one(self, head: Head, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        """Serve one request. Returns False when the connection must not be reused."""
        method, path, query = parse_request_line(head.start_line)
        req = Request(method, path, query, {k.lower(): v for k, v in head.headers}, None)
        buffered = self._should_buffer(req, head)
        raw_body = await read_body(reader, head, self.json_limit) if buffered else b""
        if buffered and raw_body and _content_type(head) == "application/json":
            try:
                req.body = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                raise HttpError(f"invalid JSON body: {exc}") from exc

        verdict = decide(req, self.ctx)
        if isinstance(verdict, Deny):
            log.info("deny %s %s: %s", method, path, verdict.reason)
            return await _refuse(writer, error_response(verdict.status, verdict.message))
        return await self._forward(verdict, head, raw_body, buffered, reader, writer)

    def _should_buffer(self, req: Request, head: Head) -> bool:
        """Whether the policy needs the whole body in hand before anything is forwarded."""
        if route_of(req.method, req.path).action in _BUFFERED_ACTIONS:
            return True
        length = head.content_length
        return _content_type(head) == "application/json" and length is not None and length <= self.json_limit

    async def _forward(
        self,
        allow: Allow,
        head: Head,
        raw_body: bytes,
        buffered: bool,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> bool:
        req = allow.request
        if allow.label_check is not None:
            ident = await self.resource_id_if_labelled(allow.route, allow.label_check)
            if ident is None:
                name = allow.label_check
                log.info("deny %s %s: label-check on %s", req.method, req.path, name)
                return await _refuse(writer, _denial(f"label-check: {name} does not belong to this project"))
            req.path = _rewrite_name(req.path, allow.label_check, ident)
        denial = await self._resource_denial(allow)
        if denial is not None:
            log.info("deny %s %s: label-check on a named resource", req.method, req.path)
            return await _refuse(writer, denial)

        try:
            backend_reader, backend_writer = await self._connect()
        except OSError as exc:
            where = f" {self.backend_label}" if self.backend_label else ""
            return await _refuse(
                writer, error_response(502, f"container-gateway: backend{where} is unreachable ({exc})")
            )
        try:
            return await self._exchange(
                req, head, raw_body, buffered, reader, writer, backend_reader, backend_writer
            )
        finally:
            backend_writer.close()

    async def _exchange(
        self,
        req: Request,
        head: Head,
        raw_body: bytes,
        buffered: bool,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        backend_reader: asyncio.StreamReader,
        backend_writer: asyncio.StreamWriter,
    ) -> bool:
        """Write the approved request to the backend and relay the response back."""
        out_head = Head(f"{req.method} {req.raw_target()} HTTP/1.1", list(head.headers))
        out_head.set("Host", "docker")
        if buffered:
            body = json.dumps(req.body).encode() if req.body is not None else raw_body
            out_head.remove("Transfer-Encoding")
            out_head.set("Content-Length", str(len(body)))
            backend_writer.write(out_head.encode() + body)
            await backend_writer.drain()
        else:
            backend_writer.write(out_head.encode())
            await backend_writer.drain()
            if head.chunked or head.content_length:
                # On a truncated client body this raises HttpError; the
                # `finally` in _forward closes the half-written backend
                # connection rather than leaving the daemon mid-request.
                await pump(reader, backend_writer, head)

        resp = await read_head(backend_reader)
        if resp is None:
            return await _refuse(
                writer, error_response(502, "container-gateway: backend closed without a response")
            )
        writer.write(resp.encode())
        await writer.drain()

        status = resp.start_line.split(" ")[1]
        if status == "101" or resp.upgrade:
            try:
                await pipe(reader, backend_writer, backend_reader, writer)
            except HttpError as exc:
                log.debug("hijacked connection ended: %s", exc)
            return False
        if not (status.startswith("1") or status in ("204", "304") or req.method == "HEAD"):
            # Neither Content-Length nor chunked means the body is delimited
            # by EOF, so nothing can follow it on this connection.
            eof_framed = resp.content_length is None and not resp.chunked
            try:
                await pump(backend_reader, writer, resp)
            except HttpError as exc:
                log.info("backend response body truncated: %s", exc)
                return False
            if eof_framed:
                return False
        return (resp.get("connection") or "").lower() != "close"


def _inspect_target(family: Family, name: str, libpod: bool) -> str:
    """Where the backend exposes ``name``'s inspect payload.

    libpod spells every family the same way; the compat API drops the
    ``/json`` verb for volumes and networks (``/volumes/<name>/json`` is a
    404 there, which would read as "not this project's" and deny a request
    that should have been allowed).
    """
    if libpod:
        return f"/libpod/{family.value}/{name}/json"
    if family in (Family.VOLUMES, Family.NETWORKS):
        return f"/{family.value}/{name}"
    return f"/{family.value}/{name}/json"


def _labels_of(inspect: Any) -> dict[str, str] | None:
    """The label map of an inspect payload, in each of the three places it lives."""
    if not isinstance(inspect, dict):
        return None
    config = inspect.get("Config")
    labels = (config or {}).get("Labels") if isinstance(config, dict) else None
    labels = labels or inspect.get("Labels") or inspect.get("labels")
    return labels if isinstance(labels, dict) else None


def _rewrite_name(path: str, name: str, ident: str) -> str:
    """Point the forwarded path at the resolved ID instead of the client's name.

    Closes the window between the label check and the forwarded request in
    which the client could rename the resource or recreate it under another
    project's ownership.
    """
    if ident == name:
        return path
    needle = f"/{name}/"
    if needle in path:
        return path.replace(needle, f"/{ident}/", 1)
    if path.endswith(f"/{name}"):
        return f"{path[: -len(name)]}{ident}"
    return path


def _content_type(head: Head) -> str:
    return (head.get("content-type") or "").split(";")[0].strip().lower()


def _denial(reason: str) -> bytes:
    return error_response(403, Deny(reason).message)


def _label_denial(kind: str, name: str) -> bytes:
    return _denial(f"label-check: {kind} {name} does not belong to this project")


async def _refuse(writer: asyncio.StreamWriter, payload: bytes) -> bool:
    """Answer the client without ever having opened a backend connection."""
    writer.write(payload)
    await writer.drain()
    return False


async def serve_unix(path: Path, handler: Handler) -> asyncio.AbstractServer:
    """Bind ``path`` with mode 0600 and serve ``handler`` on it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    old_umask = os.umask(0o177)
    try:
        server = await asyncio.start_unix_server(handler, path=str(path))
    finally:
        os.umask(old_umask)
    os.chmod(path, 0o600)
    return server
