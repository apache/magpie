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
"""Probe 1 reports what `ssh-add -l` returned, and writes no file.

The probe used to capture `ssh-add -l` into `/tmp/ssh-add.out`. Inside
the sandbox `/tmp` is read-only, so the redirection failed, `ssh-add`
never ran, and the redirection's own exit code of 1 was read as "agent
reachable, no identities": a pass for an agent the probe never asked.
"""

from __future__ import annotations

import os
import socket
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "probe-1-ssh-agent.sh"
OLD_OUTPUT = Path("/tmp/ssh-add.out")


class ProbeOneSshAgent(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.addCleanup(self._tmp.cleanup)
        # The probe only checks that SSH_AUTH_SOCK is a socket; the fake
        # ssh-add never connects to it. A sandbox may refuse bind(2), so fall
        # back to the session's own agent socket.
        self.sock_path = self.tmp / "agent.sock"
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        try:
            sock.bind(str(self.sock_path))
        except OSError:
            existing = os.environ.get("SSH_AUTH_SOCK", "")
            if not (existing and Path(existing).is_socket()):
                self.skipTest("cannot bind a unix socket and no SSH_AUTH_SOCK to reuse")
            self.sock_path = Path(existing)

    def fake_ssh_add(self, output: str, rc: int) -> None:
        script = self.bin / "ssh-add"
        script.write_text(f"#!/bin/sh\nprintf '{output}'\nexit {rc}\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)

    def run_probe(self) -> str:
        env = {
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "SSH_AUTH_SOCK": str(self.sock_path),
            "TMPDIR": str(self.tmp),
        }
        result = subprocess.run(["bash", str(PROBE)], env=env, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def test_counts_listed_identities(self) -> None:
        self.fake_ssh_add("4096 SHA256:aaa key-a (RSA)\n4096 SHA256:bbb key-b (RSA)\n", 0)
        self.assertEqual(self.run_probe(), "PROBE: ssh-agent → ✓ (2 identities listed)")

    def test_reports_unreachable_agent_with_its_message(self) -> None:
        self.fake_ssh_add("Could not open a connection to your authentication agent.\n", 2)
        self.assertEqual(
            self.run_probe(),
            "PROBE: ssh-agent → ✗ (agent unreachable: "
            "Could not open a connection to your authentication agent.)",
        )

    def test_writes_nothing_under_tmp(self) -> None:
        self.fake_ssh_add("4096 SHA256:aaa key-a (RSA)\n", 0)
        started = time.time()
        self.run_probe()
        if OLD_OUTPUT.exists():
            self.assertLess(OLD_OUTPUT.stat().st_mtime, started)


if __name__ == "__main__":
    unittest.main()
