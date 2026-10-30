# SPDX-License-Identifier: Apache-2.0
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
"""Exercise CLI startup against proxy.py without opening listening sockets."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import proxy
import pytest
from proxy.http.proxy import HttpProxyPlugin

import egress_gateway
import egress_gateway.cli as cli
from egress_gateway.allowlist import EgressAllowlistPlugin, host_allowed


@pytest.fixture
def isolated_proxy_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    user_proxy_dir = Path.home() / ".proxy"
    real_makedirs = os.makedirs

    def guarded_makedirs(name: str | os.PathLike[str], mode: int = 0o777, exist_ok: bool = False) -> None:
        path = Path(name).absolute()
        if path == user_proxy_dir or user_proxy_dir in path.parents:
            raise AssertionError("CLI tests must not create directories in the user's .proxy directory")
        real_makedirs(name, mode=mode, exist_ok=exist_ok)

    monkeypatch.setattr(os, "makedirs", guarded_makedirs)
    return ["--data-dir", str(tmp_path / "data"), "--cache-dir", str(tmp_path / "cache")]


@pytest.fixture
def lifecycle(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, proxy.Proxy]]:
    events: list[tuple[str, proxy.Proxy]] = []

    def wait() -> None:
        events.append(("wait", events[0][1]))

    monkeypatch.setattr(proxy.Proxy, "setup", lambda gateway: events.append(("setup", gateway)))
    monkeypatch.setattr(proxy.Proxy, "shutdown", lambda gateway: events.append(("shutdown", gateway)))
    monkeypatch.setattr(proxy, "sleep_loop", wait)
    return events


def test_main_starts_proxy_with_defaults(
    isolated_proxy_args: list[str], lifecycle: list[tuple[str, proxy.Proxy]]
) -> None:
    assert cli.main(isolated_proxy_args) == 0

    gateway = lifecycle[0][1]
    assert lifecycle == [("setup", gateway), ("wait", gateway), ("shutdown", gateway)]
    assert str(gateway.flags.hostname) == "127.0.0.1"
    assert gateway.flags.port == 8899
    assert gateway.flags.log_level == "INFO"
    assert gateway.flags.plugins[b"HttpProxyBasePlugin"] == [EgressAllowlistPlugin]
    assert gateway.flags.plugins[b"HttpProtocolHandlerPlugin"] == [HttpProxyPlugin]
    assert gateway.flags.plugins[b"HttpWebServerBasePlugin"] == []
    assert gateway.flags.plugins[b"ReverseProxyBasePlugin"] == []


@pytest.mark.parametrize("explicit_argv", [True, False])
def test_main_forwards_custom_and_passthrough_arguments(
    explicit_argv: bool,
    tmp_path: Path,
    isolated_proxy_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    lifecycle: list[tuple[str, proxy.Proxy]],
) -> None:
    argv = [
        "--host",
        "127.0.0.2",
        "--port",
        "9001",
        "--log-level",
        "DEBUG",
        "--num-workers",
        "1",
        "--num-acceptors",
        "2",
        *isolated_proxy_args,
    ]
    process_argv = ["caller", "--port", "1"] if explicit_argv else ["egress-gateway", *argv]
    monkeypatch.setattr(sys, "argv", process_argv)

    assert cli.main(argv if explicit_argv else None) == 0

    gateway = lifecycle[0][1]
    assert str(gateway.flags.hostname) == "127.0.0.2"
    assert gateway.flags.port == 9001
    assert gateway.flags.log_level == "DEBUG"
    assert gateway.flags.num_workers == 1
    assert gateway.flags.num_acceptors == 2
    assert gateway.flags.proxy_py_data_dir == str(tmp_path / "data")
    assert gateway.flags.cache_dir == str(tmp_path / "cache")
    assert gateway.flags.plugins[b"HttpProxyBasePlugin"] == [EgressAllowlistPlugin]
    assert sys.argv is process_argv


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(RuntimeError("wait failed"), id="runtime-error"),
        pytest.param(SystemExit(0), id="signal-exit"),
        pytest.param(KeyboardInterrupt(), id="keyboard-interrupt"),
    ],
)
def test_main_shuts_down_when_waiting_raises(
    error: BaseException,
    isolated_proxy_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    lifecycle: list[tuple[str, proxy.Proxy]],
) -> None:
    def fail_wait() -> None:
        lifecycle.append(("wait", lifecycle[0][1]))
        raise error

    monkeypatch.setattr(proxy, "sleep_loop", fail_wait)

    with pytest.raises(type(error)) as exc:
        cli.main(isolated_proxy_args)

    assert exc.value is error
    if isinstance(error, SystemExit):
        assert error.code == 0

    gateway = lifecycle[0][1]
    assert lifecycle == [("setup", gateway), ("wait", gateway), ("shutdown", gateway)]


def test_help_does_not_import_proxy() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\nsys.modules['proxy'] = None\n"
            + "from egress_gateway.cli import main\nmain(['--help'])\n",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "--port" in result.stdout


def test_package_preserves_host_allowed_export() -> None:
    assert egress_gateway.__all__ == ["host_allowed"]
    assert egress_gateway.host_allowed is host_allowed
    namespace: dict[str, object] = {}
    exec("from egress_gateway import *", namespace)
    assert namespace["host_allowed"] is host_allowed
    assert not hasattr(egress_gateway, "unknown_attribute")
