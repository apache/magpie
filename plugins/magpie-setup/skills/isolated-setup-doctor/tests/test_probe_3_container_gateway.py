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
"""Probe 3 reports container runtime status, and writes no file.

Inside the sandbox /tmp is read-only. The probe holds any error output in a
variable rather than redirecting to a file under /tmp.
"""

from __future__ import annotations

import json
import socket
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import find_bash, run_probe_script, to_posix

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "probe-3-container-gateway.sh"
OLD_PODMAN_ERR = Path("/tmp/podman-probe.err")
OLD_DOCKER_ERR = Path("/tmp/docker-probe.err")


class ProbeThreeContainerGateway(unittest.TestCase):
    def setUp(self) -> None:
        self.bash = find_bash()
        if not self.bash:
            self.skipTest("bash is not available on this platform")
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def fake_cmd(self, name: str, body: str = "exit 0\n") -> Path:
        script = self.bin / name
        script.write_text(f"#!/bin/sh\n{body}")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def setup_stub_gateway(
        self,
        serving: list[str] | None,
        root: Path | None = None,
        exit_code: int = 2,
        running: bool = True,
    ) -> None:
        # serving=None stands in for `status` printing nothing: exit 2 is a
        # run-directory refusal, exit 1 an import failure on an old python3.
        gw_pkg = (root or self.tmp / "tools" / "container-gateway" / "src") / "container_gateway"
        gw_pkg.mkdir(parents=True, exist_ok=True)
        (gw_pkg / "__init__.py").write_text("", encoding="utf-8")
        if serving is None:
            body = f"import sys\nsys.exit({exit_code})\n"
        else:
            status_payload = json.dumps({"running": running, "serving": serving})
            body = f"import json\nprint({status_payload!r})\n"
        (gw_pkg / "__main__.py").write_text(body, encoding="utf-8")

    def bind_unix_socket(self, name: str) -> Path:
        if not hasattr(socket, "AF_UNIX"):
            self.skipTest("AF_UNIX is not supported on this platform")
        sock_path = self.tmp / name
        sock_path.parent.mkdir(parents=True, exist_ok=True)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        try:
            sock.bind(str(sock_path))
        except OSError as e:
            self.skipTest(f"cannot bind unix socket: {e}")
        return sock_path

    def run_probe(
        self,
        env_overrides: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> str:
        env = {
            "TMPDIR": str(self.tmp),
            "HOME": str(self.tmp),
            **(env_overrides or {}),
        }
        return run_probe_script(PROBE, env, bin_dir=self.bin, cwd=cwd).strip()

    def test_runtimes_not_on_path(self) -> None:
        out = self.run_probe(
            {
                "PATH": str(self.bin),
                "CONTAINER_HOST": "",
                "DOCKER_HOST": "",
            }
        )
        self.assertIn("PROBE: podman-runtime → ⊘ (podman not on PATH)", out)
        self.assertIn("PROBE: docker-runtime → ⊘ (docker not on PATH)", out)

    def test_host_env_unset(self) -> None:
        self.fake_cmd("podman")
        out = self.run_probe({"CONTAINER_HOST": ""})
        self.assertIn(
            "PROBE: podman-runtime → ✗ (CONTAINER_HOST unset — gateway not wired into settings)",
            out,
        )

    def test_relative_socket_url(self) -> None:
        self.fake_cmd("podman")
        out = self.run_probe({"CONTAINER_HOST": "unix://run/podman.sock"})
        self.assertIn(
            "PROBE: podman-runtime → ✗ (CONTAINER_HOST=unix://run/podman.sock is not absolute",
            out,
        )

    def test_gateway_not_running(self) -> None:
        self.setup_stub_gateway([], running=False)
        self.fake_cmd("podman")
        sock = "/var/run/podman.sock"
        out = self.run_probe({"CONTAINER_HOST": f"unix://{sock}"}, cwd=self.tmp)
        self.assertIn(
            f"PROBE: podman-runtime → ✗ (gateway socket missing at {sock} — container gateway not running)",
            out,
        )

    def test_no_gateway_source_is_not_a_pass(self) -> None:
        # Without `status` nothing proves the socket is the gateway's: a raw
        # daemon socket answers `info` just as well.
        sock_path = self.bind_unix_socket("docker.sock")
        posix_sock = to_posix(sock_path)
        self.fake_cmd("docker")
        out = self.run_probe(
            {"DOCKER_HOST": f"unix://{posix_sock}"},
            cwd=self.tmp,
        )
        self.assertIn(
            "PROBE: docker-runtime → ✗ (gateway status unavailable — no gateway source in",
            out,
        )
        self.assertIn(f"a socket exists at {posix_sock}, but nothing confirms", out)
        self.assertNotIn("reaches the container gateway", out)

    def test_status_import_failure_is_not_a_refusal(self) -> None:
        # A gateway source the PATH python3 cannot import gives no status;
        # that is not the gateway refusing its run directory.
        self.setup_stub_gateway(None, exit_code=1)
        self.fake_cmd("docker")
        out = self.run_probe(
            {"DOCKER_HOST": "unix:///var/run/docker.sock"},
            cwd=self.tmp,
        )
        self.assertIn(
            "PROBE: docker-runtime → ✗ (gateway status unavailable — status exited rc=1 without a report",
            out,
        )
        self.assertNotIn("refused", out)

    def test_status_refusal_is_reported(self) -> None:
        # `status` refusing the run directory must not fall back to the
        # socket check, which would trust whatever the socket leads to.
        self.setup_stub_gateway(None)
        sock_path = self.bind_unix_socket(".git/apache-magpie/run/main/docker.sock")
        posix_sock = to_posix(sock_path)
        self.fake_cmd("docker")
        out = self.run_probe(
            {"DOCKER_HOST": f"unix://{posix_sock}"},
            cwd=self.tmp,
        )
        self.assertIn(
            "PROBE: docker-runtime → ✗ (gateway status refused the run directory",
            out,
        )
        self.assertNotIn("reaches the container gateway", out)

    def test_operator_install_source_used(self) -> None:
        self.setup_stub_gateway(
            [], root=self.tmp / ".claude" / "scripts" / "container-gateway" / "src"
        )
        self.fake_cmd("docker")
        workdir = self.tmp / "project"
        workdir.mkdir()
        out = self.run_probe(
            {"DOCKER_HOST": "unix:///var/run/docker.sock"},
            cwd=workdir,
        )
        self.assertIn(
            "PROBE: docker-runtime → ✗ (gateway running without a docker backend",
            out,
        )

    def test_writes_nothing_under_tmp(self) -> None:
        self.setup_stub_gateway(["podman"])
        sock_path = self.bind_unix_socket("podman.sock")
        posix_sock = to_posix(sock_path)
        self.fake_cmd(
            "podman",
            'printf "connect: operation not permitted\\n" >&2\nexit 1\n',
        )
        started = time.time()
        out = self.run_probe(
            {"CONTAINER_HOST": f"unix://{posix_sock}"},
            cwd=self.tmp,
        )
        self.assertIn(
            f"PROBE: podman-runtime → ✗ (connect to {posix_sock} denied — add it to sandbox.network.allowUnixSockets)",
            out,
        )
        if OLD_PODMAN_ERR.exists():
            self.assertLess(OLD_PODMAN_ERR.stat().st_mtime, started)
        if OLD_DOCKER_ERR.exists():
            self.assertLess(OLD_DOCKER_ERR.stat().st_mtime, started)
        self.assertFalse((self.tmp / "podman-probe.err").exists())
        self.assertFalse((self.tmp / "docker-probe.err").exists())

    def test_docker_stdout_does_not_mask_stderr_error(self) -> None:
        self.setup_stub_gateway(["docker"])
        sock_path = self.bind_unix_socket("docker.sock")
        posix_sock = to_posix(sock_path)
        self.fake_cmd(
            "docker",
            'printf "Client: Docker Engine - Community\\n Version: 25.0.0\\n"\n'
            'printf "connect: 502 Bad Gateway\\n" >&2\n'
            "exit 1\n",
        )
        out = self.run_probe(
            {"DOCKER_HOST": f"unix://{posix_sock}"},
            cwd=self.tmp,
        )
        self.assertIn(
            "PROBE: docker-runtime → ✗ (gateway up, backend down: connect: 502 Bad Gateway)",
            out,
        )
        self.assertNotIn("Client:", out)


if __name__ == "__main__":
    unittest.main()
