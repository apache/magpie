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

"""Just enough HTTP/1.1 to relay the Docker API over unix streams.

Principle enforced throughout this module: anything the gateway cannot frame
identically to the daemon is refused with :class:`HttpError`, never forwarded
as best-effort. That covers request-smuggling shapes (bare CR/LF/NUL inside a
header, a request line the policy layer would parse differently than the
daemon, duplicate or ambiguous Content-Length/Transfer-Encoding) as well as
plain transport failures (``ValueError`` from ``int()``,
``asyncio.IncompleteReadError``, ``asyncio.LimitOverrunError``) -- every one
of those is caught at the boundary and re-raised as ``HttpError`` so the relay
has exactly one exception type to catch and answer with ``error_response``.
"""

from __future__ import annotations

import asyncio
import json
import re
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

# Control characters (excluding the CR/LF that terminate a line, which are
# handled structurally by the line-splitting itself) that must never appear
# inside a header name, header value, or start line. Includes CR/LF/NUL so
# that a value smuggled *inside* a single already-split line -- a bare LF or
# CR not paired as "\r\n", or an embedded NUL -- is caught explicitly, not
# just control characters in general.
_CTL = frozenset(chr(c) for c in (*range(0x00, 0x20), 0x7F))

_METHOD_RE = re.compile(r"[A-Z]+")
_VERSION_RE = re.compile(r"HTTP/1\.[01]")
_STATUS_RE = re.compile(r"[1-5][0-9]{2}")
_CONTENT_LENGTH_RE = re.compile(r"[0-9]{1,18}")
_CHUNK_SIZE_RE = re.compile(rb"[0-9A-Fa-f]{1,8}")


class HttpError(Exception):
    pass


def _check_no_control_chars(s: str, what: str) -> None:
    if any(c in _CTL for c in s):
        raise HttpError(f"control character in {what}: {s!r}")


def _check_header_name(name: str) -> None:
    if not name:
        raise HttpError("empty header name")
    _check_no_control_chars(name, "header name")
    if any(c.isspace() for c in name):
        raise HttpError(f"whitespace in header name: {name!r}")


def _check_header_value(value: str) -> None:
    _check_no_control_chars(value, "header value")
    try:
        value.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise HttpError(f"non-latin-1 header value: {value!r}") from exc


def _validate_head_start_line(line: str) -> None:
    """Validate a request- or status-line the way the daemon would parse it.

    ``read_head`` parses both requests (sent to the daemon) and responses
    (received back from it), so this accepts either shape. The shape is
    detected from the *first* token: if it looks like an HTTP version, this
    is a status line (``HTTP/1.x SP status [SP reason]``), whose reason
    phrase is free-form -- it may be empty or contain further spaces
    (``404 Not Found``, `` 500 Internal Server Error``) -- so it is split
    with ``maxsplit=2`` rather than demanding exactly three tokens. Anything
    else is a request line (``METHOD SP target SP HTTP/1.x``), which keeps
    the strict exactly-three-tokens rule: a request target legitimately
    never contains an unencoded space, so a fourth token there is always a
    smuggling shape, not a value the gateway should tolerate. Control
    characters are rejected in either shape, over the whole line up front,
    so a tab or bogus extra space cannot silently shift which token is
    which.
    """
    _check_no_control_chars(line, "start line")
    head_token = line.split(" ", 1)[0]
    if _VERSION_RE.fullmatch(head_token):
        parts = line.split(" ", 2)
        if len(parts) < 2 or not _STATUS_RE.fullmatch(parts[1]):
            raise HttpError(f"bad status line: {line!r}")
        return
    parts = line.split(" ")
    if len(parts) != 3 or not _METHOD_RE.fullmatch(parts[0]) or not _VERSION_RE.fullmatch(parts[2]):
        raise HttpError(f"bad start line: {line!r}")


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
        _check_header_name(name)
        _check_header_value(value)
        self.remove(name)
        self.headers.append((name, value))

    def remove(self, name: str) -> None:
        name = name.lower()
        self.headers = [(k, v) for k, v in self.headers if k.lower() != name]

    @property
    def content_length(self) -> int | None:
        v = self.get("content-length")
        if v is None or not _CONTENT_LENGTH_RE.fullmatch(v):
            return None
        return int(v)

    @property
    def chunked(self) -> bool:
        v = self.get("transfer-encoding")
        return v is not None and v.casefold() == "chunked"

    @property
    def upgrade(self) -> bool:
        return self.get("upgrade") is not None or "upgrade" in (self.get("connection") or "").lower()

    def validate_framing(self) -> None:
        """Reject the request-smuggling shapes RFC 7230 §3.3.3 permits refusing.

        Called by ``read_head`` before it hands a ``Head`` back to a caller, so
        every parsed head -- request or response -- has already been checked
        by the time policy code sees it. Synthesised heads (``error_response``)
        are not run through this automatically; nothing this module builds
        itself needs it.
        """
        cls = [v for k, v in self.headers if k.lower() == "content-length"]
        tes = [v for k, v in self.headers if k.lower() == "transfer-encoding"]
        if len(cls) > 1:
            raise HttpError("duplicate Content-Length")
        if len(tes) > 1:
            raise HttpError("duplicate Transfer-Encoding")
        if cls and not _CONTENT_LENGTH_RE.fullmatch(cls[0]):
            raise HttpError(f"bad Content-Length: {cls[0]!r}")
        if tes and tes[0].casefold() != "chunked":
            raise HttpError(f"bad Transfer-Encoding: {tes[0]!r}")
        if cls and tes:
            raise HttpError("Content-Length and Transfer-Encoding both present")

    def encode(self) -> bytes:
        # Defence in depth: re-check the start line and headers even though
        # `set()` and `read_head` already validate on the way in, so a `Head`
        # built by setting `.start_line`/appending to `.headers` directly
        # (bypassing both) still cannot smuggle a control character or a
        # non-latin-1 value out onto the wire.
        _check_no_control_chars(self.start_line, "start line")
        for k, v in self.headers:
            _check_header_name(k)
            _check_header_value(v)
        lines = [self.start_line, *[f"{k}: {v}" for k, v in self.headers], "", ""]
        try:
            return "\r\n".join(lines).encode("latin-1")
        except UnicodeEncodeError as exc:
            raise HttpError(f"non-latin-1 start line: {self.start_line!r}") from exc


async def read_head(reader: asyncio.StreamReader, limit: int = 65536) -> Head | None:
    """Read and validate one HTTP head (request or response).

    ``limit`` is enforced against the fully-buffered head (``len(raw) >
    limit``) independently of the ``asyncio.StreamReader``'s own internal
    buffer limit (set at construction, default 64 KiB): a `limit` larger
    than the reader's own cannot be honoured -- ``readuntil`` will raise
    ``asyncio.LimitOverrunError`` (wrapped below as ``HttpError``) before
    this function's own check ever runs. Callers that want *this* function's
    limit to be the one that fires must construct the reader with a
    correspondingly larger internal limit.
    """
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
    _validate_head_start_line(first)
    headers: list[tuple[str, str]] = []
    for line in rest.split("\r\n"):
        if not line:
            continue
        if line[0] in " \t":
            raise HttpError(f"obsolete line folding: {line!r}")
        k, sep, v = line.partition(":")
        if not sep:
            raise HttpError(f"bad header line: {line!r}")
        name, value = k.strip(), v.strip()
        _check_header_name(name)
        _check_header_value(value)
        headers.append((name, value))
    head = Head(first, headers)
    head.validate_framing()
    return head


def parse_request_line(line: str) -> tuple[str, str, dict[str, list[str]]]:
    _check_no_control_chars(line, "request line")
    parts = line.split(" ")
    if len(parts) != 3 or not _METHOD_RE.fullmatch(parts[0]) or not _VERSION_RE.fullmatch(parts[2]):
        raise HttpError(f"bad request line: {line!r}")
    target = parts[1]
    if not target or "\\" in target:
        raise HttpError(f"bad request target: {line!r}")
    url = urlsplit(target)
    return parts[0], url.path or "/", parse_qs(url.query, keep_blank_values=True)


async def _read_chunked(reader: asyncio.StreamReader, sink: asyncio.StreamWriter | None, limit: int) -> bytes:
    out = bytearray()
    while True:
        try:
            size_line = await reader.readuntil(b"\r\n")
        except asyncio.IncompleteReadError as exc:
            raise HttpError("truncated chunk size") from exc
        except asyncio.LimitOverrunError as exc:
            raise HttpError("chunk size line too large") from exc
        size_token = size_line.split(b";", 1)[0].split(b"\r", 1)[0]
        if not _CHUNK_SIZE_RE.fullmatch(size_token):
            raise HttpError(f"bad chunk size: {size_token!r}")
        size = int(size_token, 16)
        if sink is None and len(out) + size > limit:
            raise HttpError("body too large")
        chunk = b""
        if size:
            try:
                chunk = await reader.readexactly(size + 2)
            except asyncio.IncompleteReadError as exc:
                raise HttpError("truncated chunk data") from exc
            if chunk[-2:] != b"\r\n":
                raise HttpError("bad chunk terminator")
        if sink is not None:
            sink.write(size_line + chunk)
            await sink.drain()
        else:
            out += chunk[:-2] if chunk else b""
        if size == 0:
            # trailers, if any, end with an empty line
            while True:
                try:
                    line = await reader.readuntil(b"\r\n")
                except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
                    raise HttpError("bad chunk trailer") from exc
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
    if not n:
        return b""
    try:
        return await reader.readexactly(n)
    except asyncio.IncompleteReadError as exc:
        raise HttpError("body truncated") from exc


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
            raise HttpError("body truncated")
        n -= len(chunk)
        writer.write(chunk)
        await writer.drain()


def _try_write_eof(writer: asyncio.StreamWriter) -> None:
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
        _try_write_eof(writer)


async def pipe(
    a_reader: asyncio.StreamReader,
    b_writer: asyncio.StreamWriter,
    b_reader: asyncio.StreamReader,
    a_writer: asyncio.StreamWriter,
) -> None:
    """Relay both directions until each reaches EOF; a real failure tears both down.

    Each direction's ``_copy`` half-closes its own target writer and returns
    normally on EOF, so one side finishing does not cut off the other: ``pipe``
    waits for *both* to finish. Only an exception (not a clean EOF) triggers
    cancelling the still-running direction early. Either way, the cancelled or
    finished tasks are always awaited (never leaked/dropped), and a real
    exception from either direction surfaces as ``HttpError`` so the relay can
    log and close instead of silently swallowing it.
    """
    tasks = [asyncio.create_task(_copy(a_reader, b_writer)), asyncio.create_task(_copy(b_reader, a_writer))]
    results: list[object] = []
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    finally:
        for t in tasks:
            t.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for w in (a_writer, b_writer):
            w.close()
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
            raise HttpError(f"pipe direction failed: {result}") from result


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
