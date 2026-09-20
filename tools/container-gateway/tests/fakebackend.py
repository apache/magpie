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

"""A tiny Docker-shaped daemon for the relay tests, over in-process socket pairs.

The fake never listens on a path: the sandbox this suite runs under denies
``bind()`` on a unix-domain socket anywhere (see ``test_http._socket_pair``),
so ``connect()`` builds a ``socket.socketpair()``, drives ``_handle`` on the
server end and hands the client end back. That is exactly the shape of the
connector ``Relay`` takes, so the relay talks to this fake through the same
code path it uses for a real daemon socket in production.
"""

from __future__ import annotations

import asyncio
import json
import socket
from dataclasses import dataclass, field
from typing import Any

from container_gateway.http import Head, error_response, parse_request_line, read_body, read_head
from container_gateway.labels import LABEL_KEY

_BODY_LIMIT = 10_000_000


@dataclass
class FakeBackend:
    """Daemon state plus a log of everything the relay actually forwarded."""

    containers: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> inspect payload
    images: dict[str, dict[str, Any]] = field(default_factory=dict)  # name -> inspect payload
    volumes: dict[str, dict[str, Any]] = field(default_factory=dict)  # name -> inspect payload
    networks: dict[str, dict[str, Any]] = field(default_factory=dict)  # name -> inspect payload
    execs: dict[str, str] = field(default_factory=dict)  # exec id -> container id
    seen: list[tuple[str, str, Any]] = field(default_factory=list)  # method, raw target, JSON body
    heads: list[Head] = field(default_factory=list)  # every request head as received
    bodies: list[bytes] = field(default_factory=list)  # every request body, unparsed
    transports: list[asyncio.BaseTransport] = field(default_factory=list)
    # Knobs for the failure paths the volume pre-create has to survive.
    volume_create_status: int | None = None  # force this status instead of creating
    volume_create_conflict: str | None = None  # 409, and the volume now belongs to this slug
    volume_create_idempotent: str | None = None  # 201, but the volume belongs to this slug
    volume_create_bare: bool = False  # 201 whose body carries no label map
    interim_heads: int = 0  # how many 100 Continue heads to emit before the real one

    # ------------------------------------------------------------- fixtures
    def add_container(self, cid: str, name: str, labels: dict[str, str]) -> None:
        self.containers[cid] = {"Id": cid, "Name": f"/{name}", "Config": {"Labels": dict(labels)}}

    def add_image(self, name: str, image_id: str, labels: dict[str, str]) -> None:
        self.images[name] = {"Id": image_id, "RepoTags": [name], "Labels": dict(labels)}

    def add_volume(self, name: str, labels: dict[str, str]) -> None:
        self.volumes[name] = {"Name": name, "Labels": dict(labels)}

    def add_network(self, name: str, labels: dict[str, str]) -> None:
        self.networks[name] = {"Name": name, "Id": f"net{name}", "Labels": dict(labels)}

    def _lookup(self, ref: str) -> dict[str, Any] | None:
        if ref in self.containers:
            return self.containers[ref]
        return next((c for c in self.containers.values() if c["Name"] == f"/{ref}"), None)

    # ------------------------------------------------------------ transport
    async def connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """One fresh connection to the fake: the connector ``Relay`` is built with."""
        loop = asyncio.get_running_loop()
        server_sock, client_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader, self._handle)
        transport, _ = await loop.connect_accepted_socket(lambda: protocol, server_sock)
        self.transports.append(transport)
        return await asyncio.open_connection(sock=client_sock)

    async def start(self) -> None:
        """No-op: nothing is bound, connections are made on demand."""

    async def stop(self) -> None:
        for transport in self.transports:
            transport.close()
        self.transports.clear()

    # -------------------------------------------------------------- serving
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while (head := await read_head(reader)) is not None:
                method, path, query = parse_request_line(head.start_line)
                body = await read_body(reader, head, _BODY_LIMIT)
                is_json = (head.get("content-type") or "").startswith("application/json")
                parsed = _try_json(body) if body and is_json else None
                self.seen.append((method, head.start_line.split(" ")[1], parsed))
                self.heads.append(head)
                self.bodies.append(body)
                await self._respond(method, path, query, parsed, reader, writer)
                if head.upgrade:
                    return
        finally:
            writer.close()

    async def _respond(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
        body: Any,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        parts = [p for p in path.split("/") if p]
        if parts and parts[0].startswith("v1."):
            # Only a *leading* segment is the API version: a resource may
            # legally be named "v1.45", and the daemon would not mistake it
            # for one either.
            parts = parts[1:]
        if parts == ["_ping"]:
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
        elif parts[:1] == ["containers"] and parts[-1] == "json" and len(parts) == 3:
            container = self._lookup(parts[1])
            writer.write(_json(200, container) if container else error_response(404, "no such container"))
        elif parts == ["containers", "json"]:
            listing = [{"Id": i, "Labels": c["Config"]["Labels"]} for i, c in self.containers.items()]
            writer.write(_json(200, listing))
        elif parts[:1] == ["exec"] and parts[-1] == "json":
            cid = self.execs.get(parts[1])
            writer.write(_json(200, {"ID": parts[1], "ContainerID": cid}) if cid else _no_exec())
        elif parts[:1] == ["exec"] and parts[-1] == "start":
            writer.write(_json(200, {"started": parts[1]}))
        elif parts[:1] == ["exec"] and parts[-1] == "remove":
            writer.write(b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n")
        elif parts[:1] == ["containers"] and parts[-1] == "logs":
            writer.write(
                b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"
                b"Content-Type: application/vnd.docker.raw-stream\r\n\r\n"
            )
            for piece in (b"line1\n", b"line2\n"):
                writer.write(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
                await writer.drain()
            writer.write(b"0\r\n\r\n")
        elif parts[:1] == ["containers"] and parts[-1] == "attach":
            writer.write(b"HTTP/1.1 101 UPGRADED\r\nConnection: Upgrade\r\nUpgrade: tcp\r\n\r\n")
            await writer.drain()
            data = await reader.read(64)
            writer.write(b"echo:" + data)
        elif parts[:1] == ["containers"] and parts[-1] == "archive":
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        elif parts == ["containers", "create"]:
            for _ in range(self.interim_heads):
                writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
                await writer.drain()
            writer.write(_json(201, {"Id": "newid", "Warnings": []}))
        elif parts == ["volumes", "create"]:
            name = str((body or {}).get("Name") or (body or {}).get("name") or "")
            labels = (body or {}).get("Labels") or (body or {}).get("labels") or {}
            if self.volume_create_conflict is not None:
                self.add_volume(name, {LABEL_KEY: self.volume_create_conflict})
                writer.write(error_response(409, "volume already exists"))
            elif self.volume_create_status is not None:
                writer.write(error_response(self.volume_create_status, "volume create failed"))
            else:
                # docker-compat's create is idempotent: an existing volume
                # comes back as a 201 carrying its own labels.
                owner = self.volume_create_idempotent
                self.add_volume(name, {LABEL_KEY: owner} if owner else labels)
                payload = dict(self.volumes[name])
                if self.volume_create_bare:
                    payload.pop("Labels")
                writer.write(_json(201, payload))
        elif parts[:1] == ["volumes"] and method == "GET" and len(parts) == 2:
            volume = self.volumes.get(parts[1])
            writer.write(_json(200, volume) if volume else error_response(404, "no such volume"))
        elif parts[:1] == ["images"] and parts[-1] == "json":
            image = self.images.get("/".join(parts[1:-1]))
            writer.write(_json(200, image) if image else error_response(404, "no such image"))
        elif parts[:1] == ["images"] and method == "DELETE":
            writer.write(_json(200, [{"Deleted": "/".join(parts[1:])}]))
        elif parts[:1] == ["networks"] and method == "GET" and len(parts) == 2:
            network = self.networks.get(parts[1])
            writer.write(_json(200, network) if network else error_response(404, "no such network"))
        elif parts[:1] == ["containers"] and method == "POST":
            writer.write(b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n")
        elif parts == ["build"]:
            writer.write(_json(200, {"stream": "ok", "labels": query.get("labels")}))
        else:
            writer.write(error_response(404, f"fake: {method} {path}"))
        await writer.drain()


async def socket_pair() -> tuple[
    tuple[asyncio.StreamReader, asyncio.StreamWriter],
    tuple[asyncio.StreamReader, asyncio.StreamWriter],
]:
    """Two already-connected endpoints, for driving ``Relay.handle`` directly.

    Same reason as ``connect()`` above: a pre-connected ``socket.socketpair()``
    handed to ``loop.connect_accepted_socket()`` never calls ``bind()``, which
    the sandbox refuses.
    """
    loop = asyncio.get_running_loop()
    sock_a, sock_b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    async def wrap(sock: socket.socket) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await loop.connect_accepted_socket(lambda: protocol, sock)
        return reader, asyncio.StreamWriter(transport, protocol, reader, loop)

    return await wrap(sock_a), await wrap(sock_b)


def _try_json(body: bytes) -> Any:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _no_exec() -> bytes:
    return error_response(404, "no such exec")


def _json(status: int, payload: Any) -> bytes:
    body = json.dumps(payload).encode()
    reason = {200: "OK", 201: "Created"}[status]
    head = Head(
        f"HTTP/1.1 {status} {reason}",
        [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
    )
    return head.encode() + body
