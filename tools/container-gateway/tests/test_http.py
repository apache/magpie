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
from collections.abc import Coroutine
from typing import Any, TypeVar

import pytest

from container_gateway.http import (
    HttpError,
    error_response,
    parse_request_line,
    pipe,
    pump,
    read_body,
    read_head,
)

_T = TypeVar("_T")


def run(coro: Coroutine[Any, _T, _T]) -> _T:
    """Drive a coroutine to completion without pytest-asyncio."""
    return asyncio.run(coro)


def reader_of(data: bytes) -> asyncio.StreamReader:
    r = asyncio.StreamReader()
    r.feed_data(data)
    r.feed_eof()
    return r


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
        sink_r, sink_w = await _pair()
        await pump(src, sink_w, head)
        sink_w.close()
        assert await sink_r.read() == b"3\r\nabc\r\n0\r\n\r\n"

    run(scenario())


def test_pipe_is_bidirectional() -> None:
    async def scenario() -> None:
        a_r, a_w = await _pair()
        b_r, b_w = await _pair()
        task = asyncio.create_task(pipe(a_r, b_w, b_r, a_w))
        await asyncio.sleep(0)
        a_w_peer = a_w  # writing into a's writer is read by a_r in this in-memory pair
        a_w_peer.write(b"ping")
        await a_w_peer.drain()
        assert await b_r.read(4) == b"ping"
        a_w_peer.close()
        await asyncio.wait_for(task, 2)

    run(scenario())


def test_error_response_shape() -> None:
    raw = error_response(403, "container-gateway: nope")
    head, _, body = raw.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 403 Forbidden")
    assert b"Content-Type: application/json" in head
    assert json.loads(body) == {"message": "container-gateway: nope"}


async def _pair() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """An in-memory reader/writer pair: bytes written to the writer are read from the reader.

    ``write``/``close`` hand off to the reader via ``call_soon`` rather than feeding it
    synchronously in-line. A synchronous feed lets ``pipe()``'s own opposite-direction copy
    task -- which starts reading the *same* reader the test also reads directly -- win the
    race for freshly arrived bytes before the test's own ``read()`` call has had a chance to
    register as the waiter, so the test observes an empty read instead of the forwarded
    payload. Deferring by one loop tick gives whichever caller reaches ``read()`` first (here,
    the test) the chance to register before the reader has any data to hand out, which is what
    ``pipe`` (unmodified) requires to terminate deterministically in this test.
    """
    reader = asyncio.StreamReader()
    loop = asyncio.get_running_loop()

    class _Transport(asyncio.Transport):
        def __init__(self) -> None:
            super().__init__()
            self._closing = False

        def write(self, data: bytes) -> None:
            if self._closing:
                return
            loop.call_soon(reader.feed_data, data)

        def close(self) -> None:
            if self._closing:
                return
            self._closing = True
            loop.call_soon(reader.feed_eof)

        def is_closing(self) -> bool:
            return self._closing

    protocol = asyncio.StreamReaderProtocol(reader)
    writer = asyncio.StreamWriter(_Transport(), protocol, reader, loop)
    return reader, writer
