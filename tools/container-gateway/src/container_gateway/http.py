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

"""Just enough HTTP/1.1 to relay the Docker API over unix streams."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

_REASONS = {
    200: "OK",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    500: "Internal Server Error",
    502: "Bad Gateway",
}


class HttpError(Exception):
    pass


@dataclass
class Head:
    start_line: str
    headers: list[tuple[str, str]] = field(default_factory=list)

    def get(self, name: str) -> str | None:
        name = name.lower()
        for k, v in self.headers:
            if k.lower() == name:
                return v
        return None

    def set(self, name: str, value: str) -> None:
        self.remove(name)
        self.headers.append((name, value))

    def remove(self, name: str) -> None:
        name = name.lower()
        self.headers = [(k, v) for k, v in self.headers if k.lower() != name]

    @property
    def content_length(self) -> int | None:
        v = self.get("content-length")
        return int(v) if v is not None and v.isdigit() else None

    @property
    def chunked(self) -> bool:
        return "chunked" in (self.get("transfer-encoding") or "").lower()

    @property
    def upgrade(self) -> bool:
        return self.get("upgrade") is not None or "upgrade" in (self.get("connection") or "").lower()

    def encode(self) -> bytes:
        lines = [self.start_line, *[f"{k}: {v}" for k, v in self.headers], "", ""]
        return "\r\n".join(lines).encode("latin-1")


async def read_head(reader: asyncio.StreamReader, limit: int = 65536) -> Head | None:
    try:
        raw = await reader.readuntil(b"\r\n\r\n")
    except asyncio.IncompleteReadError as exc:
        if not exc.partial.strip():
            return None
        raise HttpError("truncated head") from exc
    except asyncio.LimitOverrunError as exc:
        raise HttpError("head too large") from exc
    if len(raw) > limit:
        raise HttpError("head too large")
    text = raw.decode("latin-1")
    first, _, rest = text.partition("\r\n")
    headers: list[tuple[str, str]] = []
    for line in rest.split("\r\n"):
        if not line:
            continue
        k, sep, v = line.partition(":")
        if not sep:
            raise HttpError(f"bad header line: {line!r}")
        headers.append((k.strip(), v.strip()))
    return Head(first, headers)


def parse_request_line(line: str) -> tuple[str, str, dict[str, list[str]]]:
    parts = line.split(" ")
    if len(parts) != 3 or not parts[2].startswith("HTTP/"):
        raise HttpError(f"bad request line: {line!r}")
    url = urlsplit(parts[1])
    return parts[0].upper(), url.path or "/", parse_qs(url.query, keep_blank_values=True)


async def _read_chunked(reader: asyncio.StreamReader, sink: asyncio.StreamWriter | None, limit: int) -> bytes:
    out = bytearray()
    while True:
        size_line = await reader.readuntil(b"\r\n")
        size = int(size_line.split(b";", 1)[0].strip() or b"0", 16)
        chunk = await reader.readexactly(size + 2) if size else b""
        if sink is not None:
            sink.write(size_line + chunk)
            await sink.drain()
        else:
            out += chunk[:-2]
            if len(out) > limit:
                raise HttpError("body too large")
        if size == 0:
            # trailers, if any, end with an empty line
            while True:
                line = await reader.readuntil(b"\r\n")
                if sink is not None:
                    sink.write(line)
                if line == b"\r\n":
                    break
            if sink is not None:
                await sink.drain()
            return bytes(out)


async def read_body(reader: asyncio.StreamReader, head: Head, limit: int) -> bytes:
    if head.chunked:
        return await _read_chunked(reader, None, limit)
    n = head.content_length or 0
    if n > limit:
        raise HttpError("body too large")
    return await reader.readexactly(n) if n else b""


async def pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, head: Head) -> None:
    """Stream a body from ``reader`` to ``writer`` exactly as framed by ``head``."""
    if head.chunked:
        await _read_chunked(reader, writer, 0)
        return
    n = head.content_length
    if n is None:
        while chunk := await reader.read(65536):
            writer.write(chunk)
            await writer.drain()
        return
    while n > 0:
        chunk = await reader.read(min(65536, n))
        if not chunk:
            break
        n -= len(chunk)
        writer.write(chunk)
        await writer.drain()


def _suppress_close(writer: asyncio.StreamWriter) -> None:
    try:
        if writer.can_write_eof():
            writer.write_eof()
    except (OSError, RuntimeError, NotImplementedError):
        pass


async def _copy(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while chunk := await reader.read(65536):
            writer.write(chunk)
            await writer.drain()
    finally:
        _suppress_close(writer)


async def pipe(
    a_reader: asyncio.StreamReader,
    b_writer: asyncio.StreamWriter,
    b_reader: asyncio.StreamReader,
    a_writer: asyncio.StreamWriter,
) -> None:
    """Copy a to b and b to a until either direction closes, then close both."""
    tasks = [asyncio.create_task(_copy(a_reader, b_writer)), asyncio.create_task(_copy(b_reader, a_writer))]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        for w in (a_writer, b_writer):
            w.close()


def error_response(status: int, message: str) -> bytes:
    body = json.dumps({"message": message}).encode()
    head = Head(
        f"HTTP/1.1 {status} {_REASONS.get(status, 'Error')}",
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("Connection", "close"),
        ],
    )
    return head.encode() + body
