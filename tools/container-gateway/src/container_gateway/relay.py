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
from .routes import Family, Route, name_span
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

# Hop-by-hop headers belong to the client <-> gateway connection and must
# not be copied onto the gateway <-> daemon one (RFC 7230 6.1). `Connection`
# is dropped too unless it names the upgrade the relay is about to hijack.
_HOP_BY_HOP = ("Keep-Alive", "TE", "Trailer", "Proxy-Authorization", "Proxy-Connection")

# How many interim (1xx) heads the relay will consume before deciding the
# backend is never going to produce a final one. A real daemon sends at
# most one 100 Continue; the cap keeps a misbehaving or hostile one from
# holding a client connection open indefinitely.
_MAX_INTERIM_HEADS = 8

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
        backend_timeout: float | None = None,
    ) -> None:
        self.connect = connect
        self.ctx = ctx
        self.backend_label = backend_label
        self.json_limit = json_limit
        # Bounds every short request/response round trip the relay makes on
        # its own behalf (label-check inspects, volume/network pre-creates)
        # and the connect + first response head of a forwarded request.
        # Streaming bodies and hijacked pipes are deliberately NOT bounded
        # by this: a long ``logs -f`` or an attached shell is legitimate.
        self.backend_timeout = backend_timeout

    # ------------------------------------------------------------ backend
    async def _connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if self.backend_timeout is None:
            return await self.connect()
        return await asyncio.wait_for(self.connect(), self.backend_timeout)

    async def _read_first_head(self, backend_reader: asyncio.StreamReader) -> Head | None:
        """Read the backend's first response head, bounded by ``backend_timeout``.

        Only the *first* head is bounded here -- a chatty backend sending
        several interim (1xx) heads before its final one is read by the
        unbounded loop in ``_exchange`` below, on the theory that a backend
        that answered at all within the timeout is unlikely to then stall
        indefinitely between interim heads.
        """
        if self.backend_timeout is None:
            return await read_head(backend_reader)
        return await asyncio.wait_for(read_head(backend_reader), self.backend_timeout)

    async def _request_json(
        self, method: str, target: str, payload: Any | None = None
    ) -> tuple[int | None, Any]:
        """One short JSON call the relay makes on its own behalf (never the client's).

        Returns ``(status, parsed body)``. ``status`` is ``None`` when the
        call could not be completed at all -- the connector refused, the
        response was unframable, the connection died mid-body, or the
        round trip timed out -- and the body is ``None`` when it was absent
        or not JSON. Every caller treats an unknown status as a failure,
        which is what makes a timeout here fail closed the same way a
        connection refusal does.
        """
        try:
            reader, writer = await self._connect()
        except OSError as exc:
            log.debug("backend call %s %s could not connect: %s", method, target, exc)
            return None, None
        status: int | None = None

        async def _round_trip() -> tuple[int | None, Any]:
            nonlocal status
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

        try:
            if self.backend_timeout is None:
                return await _round_trip()
            return await asyncio.wait_for(_round_trip(), self.backend_timeout)
        except (HttpError, OSError, ValueError, asyncio.IncompleteReadError) as exc:
            # TimeoutError is a subclass of OSError (since Python 3.11 it is
            # also what ``asyncio.wait_for`` raises), so it is caught here
            # too and folded into the same "call did not complete" outcome.
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
        # Networks first: they are never auto-created, so checking them
        # before the volume pass means a request that is going to be refused
        # leaves no freshly-created volume behind.
        for name in named_networks(body, route.libpod):
            denial = await self._network_denial(name, route.libpod)
            if denial is not None:
                return denial
        for name in named_volumes(body, route.libpod):
            denial = await self._volume_denial(name, route.libpod)
            if denial is not None:
                return denial
        return None

    def _owned(self, status: int | None, info: Any) -> bool:
        """A 2xx inspect payload carrying this project's label. Anything else is not ours."""
        return status is not None and 200 <= status < 300 and has_label(_labels_of(info), self.ctx.slug)

    async def _volume_denial(self, name: str, libpod: bool) -> bytes | None:
        """An unknown volume is created labelled; a foreign one is refused."""
        if not _RESOURCE_NAME_RE.fullmatch(name):
            return _label_denial("volume", name)
        status, info = await self._request_json("GET", _inspect_target(Family.VOLUMES, name, libpod))
        if self._owned(status, info):
            return None
        if status != 404:
            return _label_denial("volume", name)
        return await self._precreate_volume(name, libpod)

    async def _precreate_volume(self, name: str, libpod: bool) -> bytes | None:
        """Create the volume labelled, so the daemon cannot create it unlabelled.

        Fails closed: anything but a successful create refuses the request
        that referenced the volume. A 409 means somebody won the race
        between the inspect above and this create -- possibly another
        project -- so the label test is re-run against whatever now exists
        rather than assuming the winner was us.
        """
        target = "/libpod/volumes/create" if libpod else "/volumes/create"
        label = {LABEL_KEY: self.ctx.slug}
        payload = {"name": name, "labels": label} if libpod else {"Name": name, "Labels": label}
        status, created = await self._request_json("POST", target, payload)
        if status is not None and 200 <= status < 300:
            # A 201 is not proof the volume is ours: docker-compat's create
            # is idempotent and answers 201 with the *existing* volume, so
            # a name another project created between the inspect above and
            # this call comes back looking like a success. Test the labels
            # the daemon actually returned.
            if self._owned(status, created):
                return None
            if _labels_of(created) is None:
                return await self._recheck_volume(name, libpod)
            return _label_denial("volume", name)
        if status == 409:
            log.info("volume %s was created concurrently; re-checking its label", name)
            return await self._recheck_volume(name, libpod)
        log.warning("pre-creating volume %s returned %s; refusing the request", name, status)
        return _denial(f"label-check: volume {name} could not be prepared")

    async def _recheck_volume(self, name: str, libpod: bool) -> bytes | None:
        """Re-inspect a volume whose create response did not settle ownership."""
        again = await self._request_json("GET", _inspect_target(Family.VOLUMES, name, libpod))
        return None if self._owned(*again) else _label_denial("volume", name)

    async def _network_denial(self, name: str, libpod: bool) -> bytes | None:
        """Networks are never auto-created, so an unknown one is refused too."""
        if not _RESOURCE_NAME_RE.fullmatch(name):
            return _label_denial("network", name)
        status, info = await self._request_json("GET", _inspect_target(Family.NETWORKS, name, libpod))
        if status == 404:
            return _denial(f"label-check: network {name} does not exist")
        return None if self._owned(status, info) else _label_denial("network", name)

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
        buffered = self._should_buffer(req)
        raw_body = b""
        if buffered:
            await _continue_if_expected(head, writer)
            raw_body = await read_body(reader, head, self.json_limit)
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

    def _should_buffer(self, req: Request) -> bool:
        """Whether the policy needs the whole body in hand before anything is forwarded.

        The action decides, never the Content-Type: a client that labels a
        build context or a tar archive ``application/json`` would otherwise
        have it buffered (and re-encoded) on its say-so.
        """
        return route_of(req.method, req.path).action in _BUFFERED_ACTIONS

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
            name = allow.label_check
            if not name:
                # `/containers/start` and friends: a verb with no name in
                # front of it. Nothing to inspect, so nothing to authorise.
                log.info("deny %s %s: empty resource name", req.method, req.path)
                return await _refuse(writer, _denial("label-check: empty resource name"))
            ident = await self.resource_id_if_labelled(allow.route, name)
            if ident is None:
                log.info("deny %s %s: label-check on %s", req.method, req.path, name)
                return await _refuse(writer, _denial(f"label-check: {name} does not belong to this project"))
            rewritten = _rewrite_name(req.method, req.path, name, ident)
            if rewritten is None:
                log.info("deny %s %s: target cannot be rewritten to the resolved id", req.method, req.path)
                return await _refuse(writer, _denial("label-check: cannot rewrite request target"))
            req.path = rewritten
        denial = await self._resource_denial(allow)
        if denial is not None:
            log.info("deny %s %s: label-check on a named resource", req.method, req.path)
            return await _refuse(writer, denial)

        try:
            backend_reader, backend_writer = await self._connect()
        except TimeoutError:
            return await _refuse(writer, error_response(502, "container-gateway: backend timed out"))
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
        _strip_hop_by_hop(out_head)
        # The relay answers the client's 100-continue handshake itself (see
        # `_continue_if_expected`), so the daemon must not be asked for a
        # second interim head that nobody is waiting for.
        out_head.remove("Expect")
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
                await _continue_if_expected(head, writer)
                # On a truncated client body this raises HttpError; the
                # `finally` in _forward closes the half-written backend
                # connection rather than leaving the daemon mid-request.
                await pump(reader, backend_writer, head)

        try:
            resp = await self._read_first_head(backend_reader)
        except TimeoutError:
            return await _refuse(writer, error_response(502, "container-gateway: backend timed out"))
        interim = 0
        while resp is not None and _is_interim(resp):
            # 100 Continue and friends are bookkeeping between the gateway
            # and the daemon; the client is sent the final head only.
            interim += 1
            if interim > _MAX_INTERIM_HEADS:
                return await _refuse(
                    writer,
                    error_response(502, "container-gateway: backend sent too many interim responses"),
                )
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
        # Every other 1xx has been consumed by the interim loop above.
        if status not in ("204", "304") and req.method != "HEAD":
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


def _rewrite_name(method: str, path: str, name: str, ident: str) -> str | None:
    """Point the forwarded path at the resolved ID instead of the client's name.

    Closes the window between the label check and the forwarded request in
    which the client could rename the resource or recreate it under another
    project's ownership. The ID is spliced over exactly the segments
    ``routes.name_span`` reports, never over the first textual occurrence of
    the name: a container legally named ``containers``, ``libpod`` or
    ``v1.45`` appears earlier in its own request target than the position
    the daemon acts on. Returns ``None`` -- and the caller refuses the
    request -- when the span is missing or does not spell the name the
    policy checked: the route and the policy disagreeing about which
    segments are the name is exactly the situation in which forwarding the
    client's own name would act on something nobody authorised.
    """
    if ident == name:
        return path
    span = name_span(method, path)
    if span is None:
        return None
    start, end = span
    segments = [s for s in path.split("/") if s]
    if "/".join(segments[start:end]) != name:
        return None
    segments[start:end] = [ident]
    return "/" + "/".join(segments)


async def _continue_if_expected(head: Head, writer: asyncio.StreamWriter) -> None:
    """Answer a client's ``Expect: 100-continue`` before its body is read.

    The relay -- not the daemon -- is this client's HTTP peer, and nothing
    downstream reads the body until the relay has read it, so the handshake
    has to be completed here or the client waits for an interim head that
    never arrives (curl sends ``Expect`` by default for bodies over 1 KiB,
    which is every real build context or archive upload). Sending 100 and
    then a final status -- including a 403 for a request the policy refuses
    -- is exactly what RFC 7231 5.1.1 allows.
    """
    if "100-continue" in (head.get("expect") or "").lower():
        writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
        await writer.drain()


def _strip_hop_by_hop(head: Head) -> None:
    """Drop the headers that belong to the client's own connection, not the daemon's."""
    connection = (head.get("connection") or "").lower()
    for name in _HOP_BY_HOP:
        head.remove(name)
    if "upgrade" not in connection:
        head.remove("Connection")


def _is_interim(head: Head) -> bool:
    """A 1xx response head the relay consumes itself -- everything but the 101 hijack."""
    status = head.start_line.split(" ")[1]
    return status.startswith("1") and status != "101"


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
    """Bind ``path`` with mode 0600 and serve ``handler`` on it.

    The caller (the daemon) guarantees ``path.parent`` already exists as a
    checked, owned, non-symlinked directory -- this function does not
    create it, so it never has to decide what to do about a parent that
    does not yet exist or is something other than a plain directory. It
    also does not unlink a pre-existing ``path`` itself: the daemon does
    that (via ``check_socket_type`` first, then the unlink) only once the
    pid-file lock is held, so nothing here silently removes a file the
    caller had not already decided was safe to remove.
    """
    old_umask = os.umask(0o177)
    try:
        server = await asyncio.start_unix_server(handler, path=str(path))
    finally:
        os.umask(old_umask)
    os.chmod(path, 0o600)
    return server
