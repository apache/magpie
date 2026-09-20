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

"""The relay end to end against the fake backend.

No ``pytest-asyncio`` in the ``magpie-dev`` dependency group, so each
scenario is a plain ``def`` test driving its coroutine through ``run()``,
exactly as ``test_http.py`` does. The relay is driven directly over a
``socket.socketpair()`` rather than through a bound gateway socket: the
sandbox refuses ``bind()`` on a unix-domain path, and ``serve_unix`` (the
only piece that binds) gets its own smoke test below.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import pytest

from container_gateway.labels import LABEL_KEY
from container_gateway.policy import PolicyContext
from container_gateway.relay import Relay, serve_unix

from .fakebackend import FakeBackend, socket_pair

_T = TypeVar("_T")


def run(coro: Coroutine[Any, Any, _T]) -> _T:
    """Drive a coroutine to completion without pytest-asyncio."""
    return asyncio.run(coro)


def stack(root: Path) -> tuple[FakeBackend, Relay]:
    """A fake daemon holding one owned and one foreign resource of each kind."""
    backend = FakeBackend()
    backend.add_container("aaa111", "mine", {LABEL_KEY: "-p"})
    backend.add_container("bbb222", "theirs", {LABEL_KEY: "-q"})
    backend.execs["ex1"] = "aaa111"
    backend.execs["ex2"] = "bbb222"
    backend.add_volume("myvol", {LABEL_KEY: "-p"})
    backend.add_volume("theirvol", {LABEL_KEY: "-q"})
    backend.add_network("mynet", {LABEL_KEY: "-p"})
    backend.add_network("theirnet", {LABEL_KEY: "-q"})
    ctx = PolicyContext("-p", root, (root,), {"HTTP_PROXY": "http://h:1"}, "inject-if-available")
    return backend, Relay(backend.connect, ctx, backend_label=str(root / "d.sock"))


async def call(relay: Relay, raw: bytes) -> tuple[int, bytes, bytes]:
    """Send one request over a fresh client connection; return status, head, body."""
    (reader, writer), server = await socket_pair()
    served = asyncio.create_task(relay.handle(*server))
    writer.write(raw)
    await writer.drain()
    writer.write_eof()
    data = await asyncio.wait_for(reader.read(), 5)
    await asyncio.wait_for(served, 5)
    writer.close()
    head, _, body = data.partition(b"\r\n\r\n")
    return int(head.split(b" ")[1]), head, body


async def call_raw(relay: Relay, raw: bytes) -> bytes:
    """Like ``call``, but returns every byte the relay wrote, interim heads included."""
    (reader, writer), server = await socket_pair()
    served = asyncio.create_task(relay.handle(*server))
    writer.write(raw)
    await writer.drain()
    writer.write_eof()
    data = await asyncio.wait_for(reader.read(), 5)
    await asyncio.wait_for(served, 5)
    writer.close()
    return data


def dechunk(body: bytes) -> bytes:
    out, rest = b"", body
    while rest:
        size, _, rest = rest.partition(b"\r\n")
        n = int(size, 16)
        if n == 0:
            break
        out, rest = out + rest[:n], rest[n + 2 :]
    return out


def create_request(payload: dict[str, Any], extra: bytes = b"") -> bytes:
    body = json.dumps(payload).encode()
    head = (
        b"POST /v1.45/containers/create HTTP/1.1\r\nHost: x\r\n"
        + extra
        + b"Content-Type: application/json\r\nContent-Length: %d\r\n\r\n" % len(body)
    )
    return head + body


def test_ping_passes_through(tmp_path: Path) -> None:
    async def scenario() -> None:
        _, relay = stack(tmp_path)
        status, _, body = await call(relay, b"GET /_ping HTTP/1.1\r\nHost: x\r\n\r\n")
        assert (status, body) == (200, b"OK")

    run(scenario())


def test_serve_unix_binds_owner_only(tmp_path: Path) -> None:
    async def scenario() -> None:
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            writer.close()

        sock = tmp_path / "gw.sock"
        try:
            server = await serve_unix(sock, handler)
        except PermissionError:
            pytest.skip("sandbox denies unix bind; runs in CI")
        try:
            assert sock.stat().st_mode & 0o777 == 0o600
        finally:
            server.close()
            await server.wait_closed()

    run(scenario())


def test_denied_is_403_json_and_never_reaches_backend(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        raw = b"POST /v1.45/auth HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{}"
        status, head, body = await call(relay, raw)
        assert status == 403 and b"application/json" in head
        assert json.loads(body)["message"].startswith("container-gateway: denied-endpoint")
        assert backend.seen == []

    run(scenario())


def test_list_is_filtered_by_label(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        status, _, _ = await call(relay, b"GET /v1.45/containers/json HTTP/1.1\r\nHost: x\r\n\r\n")
        assert status == 200
        _, target, _ = backend.seen[-1]
        assert "filters=" in target and "org.apache.magpie.project%3D-p" in target

    run(scenario())


def test_create_body_is_rewritten_and_length_fixed(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        status, _, _ = await call(relay, create_request({"Image": "alpine", "Env": ["A=1"]}))
        assert status == 201
        _, _, sent = backend.seen[-1]
        assert sent is not None and sent["Labels"][LABEL_KEY] == "-p"
        assert "HTTP_PROXY=http://h:1" in sent["Env"]

    run(scenario())


def test_act_by_name_resolves_to_id_when_labelled(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        raw = b"POST /v1.45/containers/mine/start HTTP/1.1\r\nHost: x\r\n\r\n"
        status, _, _ = await call(relay, raw)
        assert status == 204
        assert backend.seen[-1][:2] == ("POST", "/v1.45/containers/aaa111/start")

    run(scenario())


def test_act_by_name_on_foreign_container_is_403_not_404(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        raw = b"POST /v1.45/containers/theirs/start HTTP/1.1\r\nHost: x\r\n\r\n"
        status, _, body = await call(relay, raw)
        assert status == 403 and b"label-check" in body
        assert all(t != "/v1.45/containers/bbb222/start" for _, t, _ in backend.seen)
        ghost = b"POST /v1.45/containers/ghost/start HTTP/1.1\r\nHost: x\r\n\r\n"
        status, _, _ = await call(relay, ghost)
        assert status == 403

    run(scenario())


def test_exec_start_checks_owning_container(tmp_path: Path) -> None:
    async def scenario() -> None:
        _, relay = stack(tmp_path)
        prefix = b"HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"
        ok, _, _ = await call(relay, b"POST /v1.45/exec/ex1/start " + prefix)
        bad, _, _ = await call(relay, b"POST /v1.45/exec/ex2/start " + prefix)
        assert ok != 403 and bad == 403

    run(scenario())


def test_chunked_logs_stream_through(tmp_path: Path) -> None:
    async def scenario() -> None:
        _, relay = stack(tmp_path)
        raw = b"GET /v1.45/containers/mine/logs?stdout=1 HTTP/1.1\r\nHost: x\r\n\r\n"
        status, head, body = await call(relay, raw)
        assert status == 200 and b"chunked" in head.lower()
        assert dechunk(body) == b"line1\nline2\n"

    run(scenario())


def test_attach_hijack_pipes_both_ways(tmp_path: Path) -> None:
    async def scenario() -> None:
        _, relay = stack(tmp_path)
        (reader, writer), server = await socket_pair()
        served = asyncio.create_task(relay.handle(*server))
        writer.write(
            b"POST /v1.45/containers/mine/attach?stream=1&stdin=1 HTTP/1.1\r\n"
            b"Host: x\r\nConnection: Upgrade\r\nUpgrade: tcp\r\n\r\n"
        )
        await writer.drain()
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
        assert head.startswith(b"HTTP/1.1 101")
        writer.write(b"hello")
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(10), 5) == b"echo:hello"
        writer.close()
        await asyncio.wait_for(served, 5)

    run(scenario())


def test_backend_down_is_502(tmp_path: Path) -> None:
    async def scenario() -> None:
        async def refused() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
            raise OSError("connection refused")

        ctx = PolicyContext("-p", tmp_path, (tmp_path,), None, "off")
        relay = Relay(refused, ctx, backend_label=str(tmp_path / "missing.sock"))
        status, _, body = await call(relay, b"GET /_ping HTTP/1.1\r\nHost: x\r\n\r\n")
        assert status == 502 and b"backend" in body

    run(scenario())


def test_named_volume_owned_by_the_project_passes(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        payload = {"Image": "alpine", "HostConfig": {"Binds": ["myvol:/data"]}}
        status, _, _ = await call(relay, create_request(payload))
        assert status == 201
        assert ("GET", "/volumes/myvol", None) in backend.seen
        assert backend.seen[-1][1] == "/v1.45/containers/create"

    run(scenario())


def test_foreign_named_volume_is_403(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        payload = {"Image": "alpine", "HostConfig": {"Binds": ["theirvol:/data"]}}
        status, _, body = await call(relay, create_request(payload))
        assert status == 403
        assert "label-check: volume theirvol" in json.loads(body)["message"]
        assert all(t != "/v1.45/containers/create" for _, t, _ in backend.seen)

    run(scenario())


def test_missing_named_volume_is_precreated_with_the_label(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        payload = {"Image": "alpine", "HostConfig": {"Binds": ["newvol:/data"]}}
        status, _, _ = await call(relay, create_request(payload))
        assert status == 201
        created = [b for method, t, b in backend.seen if (method, t) == ("POST", "/volumes/create")]
        assert created == [{"Name": "newvol", "Labels": {LABEL_KEY: "-p"}}]
        assert backend.volumes["newvol"]["Labels"][LABEL_KEY] == "-p"
        assert backend.seen[-1][1] == "/v1.45/containers/create"

    run(scenario())


def test_foreign_named_network_is_403(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        payload = {"Image": "alpine", "HostConfig": {"NetworkMode": "theirnet"}}
        status, _, body = await call(relay, create_request(payload))
        assert status == 403
        assert "label-check: network theirnet does not belong" in json.loads(body)["message"]
        assert all(t != "/v1.45/containers/create" for _, t, _ in backend.seen)

    run(scenario())


def test_missing_named_network_is_403(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        payload = {"Image": "alpine", "HostConfig": {"NetworkMode": "ghostnet"}}
        status, _, body = await call(relay, create_request(payload))
        assert status == 403
        assert "label-check: network ghostnet does not exist" in json.loads(body)["message"]
        assert all(t != "/v1.45/containers/create" for _, t, _ in backend.seen)

    run(scenario())


def test_owned_named_network_passes(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        payload = {"Image": "alpine", "HostConfig": {"NetworkMode": "mynet"}}
        status, _, _ = await call(relay, create_request(payload))
        assert status == 201
        assert ("GET", "/networks/mynet", None) in backend.seen

    run(scenario())


# --- Fix round 1 additions below ---


def test_id_rewrite_is_segment_exact(tmp_path: Path) -> None:
    """A container legally named after a path element must not shift the rewrite."""

    async def scenario() -> None:
        for name, cid in (("containers", "ccc333"), ("v1.45", "ddd444"), ("libpod", "eee555")):
            backend, relay = stack(tmp_path)
            backend.add_container(cid, name, {LABEL_KEY: "-p"})
            raw = f"POST /v1.45/containers/{name}/start HTTP/1.1\r\nHost: x\r\n\r\n".encode()
            status, _, _ = await call(relay, raw)
            assert status == 204
            assert backend.seen[-1][:2] == ("POST", f"/v1.45/containers/{cid}/start")

    run(scenario())


def test_id_rewrite_spans_a_multi_segment_image_name(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        backend.add_image("quay.io/podman/hello:latest", "sha256:dead", {LABEL_KEY: "-p"})
        raw = b"DELETE /v1.45/images/quay.io/podman/hello:latest HTTP/1.1\r\nHost: x\r\n\r\n"
        status, _, _ = await call(relay, raw)
        assert status == 200
        assert backend.seen[-1][:2] == ("DELETE", "/v1.45/images/sha256:dead")

    run(scenario())


def test_foreign_multi_segment_image_is_403(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        backend.add_image("quay.io/podman/hello:latest", "sha256:dead", {LABEL_KEY: "-q"})
        raw = b"DELETE /v1.45/images/quay.io/podman/hello:latest HTTP/1.1\r\nHost: x\r\n\r\n"
        status, _, body = await call(relay, raw)
        assert status == 403 and b"label-check" in body
        assert all(method != "DELETE" for method, _, _ in backend.seen)

    run(scenario())


def test_volume_precreate_conflict_rechecks_the_label(tmp_path: Path) -> None:
    """Another project winning the create race must not hand us its volume."""

    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        backend.volume_create_conflict = "-q"
        payload = {"Image": "alpine", "HostConfig": {"Binds": ["racevol:/data"]}}
        status, _, body = await call(relay, create_request(payload))
        assert status == 403
        assert "label-check: volume racevol" in json.loads(body)["message"]
        assert all(t != "/v1.45/containers/create" for _, t, _ in backend.seen)

    run(scenario())


def test_volume_precreate_conflict_won_by_this_project_passes(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        backend.volume_create_conflict = "-p"
        payload = {"Image": "alpine", "HostConfig": {"Binds": ["racevol:/data"]}}
        status, _, _ = await call(relay, create_request(payload))
        assert status == 201
        assert backend.seen[-1][1] == "/v1.45/containers/create"

    run(scenario())


def test_volume_precreate_failure_is_403(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        backend.volume_create_status = 500
        payload = {"Image": "alpine", "HostConfig": {"Binds": ["newvol:/data"]}}
        status, _, body = await call(relay, create_request(payload))
        assert status == 403
        assert "label-check: volume newvol could not be prepared" in json.loads(body)["message"]
        assert all(t != "/v1.45/containers/create" for _, t, _ in backend.seen)

    run(scenario())


def test_anonymous_volume_mount_needs_no_check(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        payload = {"Image": "alpine", "HostConfig": {"Mounts": [{"Type": "volume", "Target": "/d"}]}}
        status, _, _ = await call(relay, create_request(payload))
        assert status == 201
        assert [t for _, t, _ in backend.seen] == ["/v1.45/containers/create"]

    run(scenario())


def test_interim_head_from_the_backend_is_consumed(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        backend.interim_continue = True
        data = await call_raw(relay, create_request({"Image": "alpine"}))
        assert data.startswith(b"HTTP/1.1 201 Created")
        assert b"100 Continue" not in data
        assert json.loads(data.partition(b"\r\n\r\n")[2])["Id"] == "newid"

    run(scenario())


def test_expect_continue_is_answered_by_the_relay_and_stripped(tmp_path: Path) -> None:
    """The client's HTTP peer is the relay, so the relay completes the handshake."""

    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        raw = create_request({"Image": "alpine"}, extra=b"Expect: 100-continue\r\n")
        data = await call_raw(relay, raw)
        assert data.startswith(b"HTTP/1.1 100 Continue\r\n\r\n")
        assert b"HTTP/1.1 201 Created" in data
        assert backend.heads[-1].get("expect") is None

    run(scenario())


def test_expect_continue_on_a_streamed_body_is_answered_too(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        blob = b"tar-bytes" * 4
        raw = (
            b"PUT /v1.45/containers/mine/archive?path=/tmp HTTP/1.1\r\nHost: x\r\n"
            b"Expect: 100-continue\r\nContent-Length: %d\r\n\r\n" % len(blob)
        ) + blob
        data = await call_raw(relay, raw)
        assert data.startswith(b"HTTP/1.1 100 Continue\r\n\r\n")
        assert b"HTTP/1.1 200 OK" in data
        assert backend.bodies[-1] == blob
        assert backend.heads[-1].get("expect") is None

    run(scenario())


def test_hop_by_hop_headers_are_stripped(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        raw = (
            b"GET /_ping HTTP/1.1\r\nHost: x\r\nKeep-Alive: timeout=5\r\n"
            b"Connection: keep-alive\r\nTE: trailers\r\nProxy-Connection: on\r\n\r\n"
        )
        status, _, _ = await call(relay, raw)
        assert status == 200
        sent = backend.heads[-1]
        assert [sent.get(h) for h in ("keep-alive", "connection", "te", "proxy-connection")] == [None] * 4
        assert sent.get("host") == "docker"

    run(scenario())


def test_upgrade_connection_header_survives(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        (reader, writer), server = await socket_pair()
        served = asyncio.create_task(relay.handle(*server))
        writer.write(
            b"POST /v1.45/containers/mine/attach?stream=1 HTTP/1.1\r\n"
            b"Host: x\r\nConnection: Upgrade\r\nUpgrade: tcp\r\n\r\n"
        )
        await writer.drain()
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
        assert head.startswith(b"HTTP/1.1 101")
        assert backend.heads[-1].get("connection") == "Upgrade"
        writer.close()
        await asyncio.wait_for(served, 5)

    run(scenario())


def test_network_is_checked_before_any_volume_is_created(tmp_path: Path) -> None:
    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        payload = {
            "Image": "alpine",
            "HostConfig": {"NetworkMode": "theirnet", "Binds": ["newvol:/data"]},
        }
        status, _, _ = await call(relay, create_request(payload))
        assert status == 403
        assert all(t != "/volumes/create" for _, t, _ in backend.seen)
        assert "newvol" not in backend.volumes

    run(scenario())


def test_archive_body_streams_verbatim(tmp_path: Path) -> None:
    """Buffering follows the action, not a Content-Type the client chose."""

    async def scenario() -> None:
        backend, relay = stack(tmp_path)
        blob = b"\x00tar-bytes-not-json\xff" * 8
        raw = (
            b"PUT /v1.45/containers/mine/archive?path=/tmp HTTP/1.1\r\nHost: x\r\n"
            b"Content-Type: application/json\r\nContent-Length: %d\r\n\r\n" % len(blob)
        ) + blob
        status, _, _ = await call(relay, raw)
        assert status == 200
        assert backend.bodies[-1] == blob
        assert backend.seen[-1][:2] == ("PUT", "/v1.45/containers/aaa111/archive?path=%2Ftmp")

    run(scenario())
