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

"""Framing: heads, bodies, chunked transfer, pumping and piping.

No ``pytest-asyncio`` in the ``magpie-dev`` dependency group (stdlib +
mypy/pytest/ruff only), so each async scenario is a plain ``def`` test
that drives its coroutine through the ``run()`` helper below instead of
an ``@pytest.mark.asyncio``-marked ``async def``.
"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Coroutine
from typing import Any, TypeVar

import pytest

from container_gateway.http import (
    Head,
    HttpError,
    error_response,
    parse_request_line,
    pipe,
    pump,
    read_body,
    read_head,
)

_T = TypeVar("_T")


def run(coro: Coroutine[Any, Any, _T]) -> _T:
    """Drive a coroutine to completion without pytest-asyncio."""
    return asyncio.run(coro)


def reader_of(data: bytes) -> asyncio.StreamReader:
    r = asyncio.StreamReader()
    r.feed_data(data)
    r.feed_eof()
    return r


class _FakeWriter:
    """A minimal duck-typed stand-in for the ``asyncio.StreamWriter`` calls this
    module makes (``write``/``drain``/``close``/``can_write_eof``/``write_eof``).

    Used where a test is about ``pump``/``pipe``'s error handling rather than
    about genuine byte-for-byte transport behaviour (I6/I8) -- a real socket
    would work too but adds setup unrelated to what the test is checking.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self.written = bytearray()
        self._fail = fail

    def write(self, data: bytes) -> None:
        if self._fail:
            raise OSError("broken pipe")
        self.written += data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    def can_write_eof(self) -> bool:
        return False

    def write_eof(self) -> None:
        return None


async def _socket_pair() -> tuple[
    tuple[asyncio.StreamReader, asyncio.StreamWriter],
    tuple[asyncio.StreamReader, asyncio.StreamWriter],
]:
    """A real two-endpoint pair of already-connected unix sockets.

    Unlike an in-memory loopback (the original version of this helper), each
    side is a genuine independent socket endpoint: writing on one side's
    writer is observed -- with real half-close semantics -- only on the
    *other* side's reader. That means two independent consumers (e.g.
    ``pipe()``'s own opposite-direction copy task and a test reading
    directly) can never race for the same shared buffer, which an in-memory
    stand-in whose writer fed its own reader could.

    Built from ``socket.socketpair()`` (an anonymous, already-connected pair
    with no filesystem path) rather than ``asyncio.start_unix_server`` bound
    to a path under ``tmp_path``: the sandbox this suite runs under denies
    ``bind()`` on a unix-domain socket path even inside the project/tmp tree,
    but a pre-connected pair handed to ``loop.connect_accepted_socket()``
    never calls ``bind()`` or ``connect()`` at all.
    """
    loop = asyncio.get_running_loop()
    sock_a, sock_b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    async def wrap(sock: socket.socket) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await loop.connect_accepted_socket(lambda: protocol, sock)
        writer = asyncio.StreamWriter(transport, protocol, reader, loop)
        return reader, writer

    return await wrap(sock_a), await wrap(sock_b)


def test_read_head_and_helpers() -> None:
    async def scenario() -> None:
        raw = (
            b"POST /v1.45/containers/create?name=x HTTP/1.1\r\n"
            b"Host: docker\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"
        )
        r = reader_of(raw)
        head = await read_head(r)
        assert head is not None
        assert head.start_line == "POST /v1.45/containers/create?name=x HTTP/1.1"
        assert head.get("content-type") == "application/json"
        assert head.content_length == 2 and not head.chunked and not head.upgrade
        head.set("Content-Length", "4")
        head.remove("host")
        assert head.encode() == (
            b"POST /v1.45/containers/create?name=x HTTP/1.1\r\n"
            b"Content-Type: application/json\r\nContent-Length: 4\r\n\r\n"
        )
        assert await r.read() == b"{}"

    run(scenario())


def test_read_head_eof_and_oversize() -> None:
    async def scenario() -> None:
        assert await read_head(reader_of(b"")) is None

        # M1: `read_head`'s own `limit=` is enforced separately from the
        # `asyncio.StreamReader`'s internal buffer limit (default 64 KiB). Give
        # the reader a generous internal limit so it is *this* function's
        # `len(raw) > limit` check that fires, not `readuntil`'s own overrun.
        big_reader = asyncio.StreamReader(limit=4096)
        big_reader.feed_data(b"GET / HTTP/1.1\r\n" + b"X: " + b"a" * 300 + b"\r\n\r\n")
        big_reader.feed_eof()
        with pytest.raises(HttpError):
            await read_head(big_reader, limit=100)

        # The StreamReader's own internal limit still surfaces as HttpError too.
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET / HTTP/1.1\r\n" + b"X: " + b"a" * 70000 + b"\r\n\r\n"))

    run(scenario())


def test_parse_request_line() -> None:
    m, p, q = parse_request_line("GET /v1.45/containers/json?all=1&filters=%7B%7D HTTP/1.1")
    assert (m, p) == ("GET", "/v1.45/containers/json")
    assert q == {"all": ["1"], "filters": ["{}"]}
    with pytest.raises(HttpError):
        parse_request_line("nonsense")


def test_read_body_content_length_and_chunked() -> None:
    async def scenario() -> None:
        head = await read_head(reader_of(b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\n"))
        assert head is not None
        assert await read_body(reader_of(b"hello"), head, 100) == b"hello"
        chead = await read_head(reader_of(b"POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"))
        assert chead is not None
        assert await read_body(reader_of(b"3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n"), chead, 100) == b"abcde"
        with pytest.raises(HttpError):
            await read_body(reader_of(b"hello"), head, 2)

    run(scenario())


def test_pump_streams_chunked_verbatim() -> None:
    async def scenario() -> None:
        head = await read_head(reader_of(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"))
        assert head is not None
        src = reader_of(b"3\r\nabc\r\n0\r\n\r\n")
        (verify_r, verify_w), (_sink_r, sink_w) = await _socket_pair()
        await pump(src, sink_w, head)
        sink_w.close()
        assert await verify_r.read() == b"3\r\nabc\r\n0\r\n\r\n"
        verify_w.close()

    run(scenario())


def test_pipe_is_bidirectional() -> None:
    async def scenario() -> None:
        (peer_a_r, peer_a_w), (pipe_a_r, pipe_a_w) = await _socket_pair()
        (peer_b_r, peer_b_w), (pipe_b_r, pipe_b_w) = await _socket_pair()
        task = asyncio.create_task(pipe(pipe_a_r, pipe_b_w, pipe_b_r, pipe_a_w))

        peer_a_w.write(b"ping")
        await peer_a_w.drain()
        assert await peer_b_r.readexactly(4) == b"ping"

        # I7: half-close the a->b direction; b->a must keep working independently.
        peer_a_w.write_eof()

        peer_b_w.write(b"pong!")
        await peer_b_w.drain()
        assert await peer_a_r.readexactly(5) == b"pong!"

        peer_b_w.write_eof()
        await asyncio.wait_for(task, 2)  # both directions reached EOF -> normal completion

        peer_a_w.close()
        peer_b_w.close()

    run(scenario())


def test_i8_pipe_surfaces_a_copy_failure_as_http_error() -> None:
    async def scenario() -> None:
        a_r = reader_of(b"boom")
        b_r = reader_of(b"")
        with pytest.raises(HttpError):
            await pipe(a_r, _FakeWriter(fail=True), b_r, _FakeWriter())  # type: ignore[arg-type]

    run(scenario())


def test_error_response_shape() -> None:
    raw = error_response(403, "container-gateway: nope")
    head, _, body = raw.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 403 Forbidden")
    assert b"Content-Type: application/json" in head
    assert json.loads(body) == {"message": "container-gateway: nope"}


def test_c1_control_chars_in_headers_rejected() -> None:
    async def scenario() -> None:
        # `X: y\nContent-Length: 9` -- a bare LF smuggling a second header past a
        # policy that only saw one, forwarded verbatim to the daemon otherwise.
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET / HTTP/1.1\r\nX: y\nContent-Length: 9\r\n\r\n"))
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET / HTTP/1.1\r\nX: a\n\nb\r\n\r\n"))
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET / HTTP/1.1\r\nX: a\x00b\r\n\r\n"))
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET / HTTP/1.1\r\nX Y: z\r\n\r\n"))

    run(scenario())


def test_c1_head_set_and_encode_reject_control_chars() -> None:
    head = Head("GET / HTTP/1.1", [])
    with pytest.raises(HttpError):
        head.set("X", "a\r\nb")
    with pytest.raises(HttpError):
        head.set("X Y", "z")
    with pytest.raises(HttpError):
        head.set("", "z")
    # Bypass `set()`'s own validation to exercise `encode()`'s defence-in-depth check.
    head.headers.append(("X", "a\nb"))
    with pytest.raises(HttpError):
        head.encode()


def test_m3_head_set_rejects_non_latin1_values() -> None:
    head = Head("GET / HTTP/1.1", [])
    with pytest.raises(HttpError):
        head.set("X-Test", "中")  # CJK codepoint, not representable in latin-1


def test_m2_obs_fold_rejected() -> None:
    async def scenario() -> None:
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET / HTTP/1.1\r\nX: a\r\n b\r\n\r\n"))

    run(scenario())


def test_c2_read_head_rejects_bad_start_lines() -> None:
    async def scenario() -> None:
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET /v1.45/containers/\njson HTTP/1.1\r\nHost: x\r\n\r\n"))
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET /v1.45/containers/json\tx HTTP/1.1\r\n\r\n"))
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET  /v1.45/containers/json HTTP/1.1\r\n\r\n"))
        with pytest.raises(HttpError):
            await read_head(reader_of(b"GET /v1.45/containers/json HTTP/2\r\n\r\n"))

    run(scenario())


def test_c2_parse_request_line_rejects_smuggling_shapes() -> None:
    with pytest.raises(HttpError):
        parse_request_line("GET /v1.45/containers/\njson HTTP/1.1")
    with pytest.raises(HttpError):
        parse_request_line("GET /v1.45/containers/json\tx HTTP/1.1")
    with pytest.raises(HttpError):
        parse_request_line("GET  /v1.45/containers/json HTTP/1.1")
    with pytest.raises(HttpError):
        parse_request_line("GET /v1.45/containers/json HTTP/2")
    with pytest.raises(HttpError):
        parse_request_line(r"GET /v1.45\..\json HTTP/1.1")


def test_c3_duplicate_and_malformed_framing_headers_rejected() -> None:
    async def scenario() -> None:
        cases = [
            b"GET / HTTP/1.1\r\nContent-Length: 5\r\nContent-Length: 5\r\n\r\n",
            b"GET / HTTP/1.1\r\nTransfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\n\r\n",
            b"GET / HTTP/1.1\r\nContent-Length: 5, 5\r\n\r\n",
            b"GET / HTTP/1.1\r\nContent-Length: -5\r\n\r\n",
            b"GET / HTTP/1.1\r\nContent-Length: +5\r\n\r\n",
            b"GET / HTTP/1.1\r\nContent-Length: 0x10\r\n\r\n",
            b"GET / HTTP/1.1\r\nContent-Length: \xb2\r\n\r\n",
            b"GET / HTTP/1.1\r\nTransfer-Encoding: xchunkedy\r\n\r\n",
            b"GET / HTTP/1.1\r\nTransfer-Encoding: chunked, gzip\r\n\r\n",
            b"GET / HTTP/1.1\r\nContent-Length: 5\r\nTransfer-Encoding: chunked\r\n\r\n",
        ]
        for raw in cases:
            with pytest.raises(HttpError):
                await read_head(reader_of(raw))

    run(scenario())


def test_i3_bad_chunk_size_grammar_rejected() -> None:
    async def scenario() -> None:
        head = await read_head(reader_of(b"POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"))
        assert head is not None
        bad_bodies = (
            b"0x10\r\naaaaaaaaaaaaaaaa\r\n0\r\n\r\n",
            b"1_0\r\na\r\n0\r\n\r\n",
            b"-1\r\n0\r\n\r\n",
            b"\r\n0\r\n\r\n",
            b" 3\r\nabc\r\n0\r\n\r\n",
        )
        for bad in bad_bodies:
            with pytest.raises(HttpError):
                await read_body(reader_of(bad), head, 1000)

    run(scenario())


def test_i4_chunk_size_checked_against_limit_before_reading() -> None:
    async def scenario() -> None:
        head = await read_head(reader_of(b"POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"))
        assert head is not None
        # Declares far more than `limit` and never supplies that many bytes; if the
        # limit were enforced only after `readexactly`, this would raise a truncation
        # error instead of the limit error the check-before-read ordering produces.
        with pytest.raises(HttpError, match="too large"):
            await read_body(reader_of(b"FFFFFF\r\n"), head, 100)

    run(scenario())


def test_i5_bad_chunk_terminator_rejected() -> None:
    async def scenario() -> None:
        head = await read_head(reader_of(b"POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"))
        assert head is not None
        with pytest.raises(HttpError):
            await read_body(reader_of(b"3\r\nabcXX0\r\n\r\n"), head, 100)

    run(scenario())


def test_i6_pump_raises_on_early_eof() -> None:
    async def scenario() -> None:
        head = await read_head(reader_of(b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n"))
        assert head is not None
        with pytest.raises(HttpError, match="truncated"):
            await pump(reader_of(b"short"), _FakeWriter(), head)  # type: ignore[arg-type]

        chead = await read_head(reader_of(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"))
        assert chead is not None
        with pytest.raises(HttpError):
            await pump(reader_of(b"3\r\nab"), _FakeWriter(), chead)  # type: ignore[arg-type]

    run(scenario())


def test_all_framing_failures_surface_as_http_error() -> None:
    async def scenario() -> None:
        head = await read_head(reader_of(b"POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"))
        assert head is not None
        with pytest.raises(HttpError):
            await read_body(reader_of(b"zz\r\n"), head, 100)  # non-hex chunk size
        with pytest.raises(HttpError):
            await read_body(reader_of(b"5\r\nab"), head, 100)  # early EOF mid-chunk

    run(scenario())
