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
"""Probe 5 reports whether user.signingkey is readable, and writes no file.

Inside the sandbox /tmp is read-only. The probe holds any error output in a
variable rather than redirecting to a file under /tmp.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import find_bash, run_probe_script, to_posix

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "probe-5-signing-key.sh"
OLD_OUTPUT = Path("/tmp/signing-key.err")


class ProbeFiveSigningKey(unittest.TestCase):
    def setUp(self) -> None:
        self.bash = find_bash()
        if not self.bash:
            self.skipTest("bash is not available on this platform")
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def fake_git(self, answers: dict[str, str]) -> None:
        script = self.bin / "git"
        lines = ["#!/bin/sh"]
        for key, val in answers.items():
            lines.append(f'if [ "$*" = "config --get {key}" ]; then printf "%s\\n" "{val}"; exit 0; fi')
        lines.append("exit 1\n")
        script.write_text("\n".join(lines))
        script.chmod(script.stat().st_mode | stat.S_IXUSR)

    def run_probe(self, env_overrides: dict[str, str] | None = None) -> str:
        env = {
            "TMPDIR": str(self.tmp),
            "HOME": str(self.tmp),
            **(env_overrides or {}),
        }
        return run_probe_script(PROBE, env, bin_dir=self.bin).strip()

    def test_gpg_format_not_ssh(self) -> None:
        self.fake_git({"gpg.format": "openpgp"})
        self.assertEqual(self.run_probe(), "PROBE: signing-key → ⊘ (gpg.format is not ssh)")

    def test_signingkey_unset(self) -> None:
        self.fake_git({"gpg.format": "ssh", "user.signingkey": ""})
        self.assertEqual(
            self.run_probe(), "PROBE: signing-key → ⊘ (gpg.format=ssh but user.signingkey unset)"
        )

    def test_literal_key(self) -> None:
        self.fake_git({"gpg.format": "ssh", "user.signingkey": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5..."})
        self.assertEqual(
            self.run_probe(),
            "PROBE: signing-key → ✓ (user.signingkey is a literal key, nothing to read)",
        )

    def test_readable_key_file(self) -> None:
        key_file = self.tmp / "id_ed25519.pub"
        key_file.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5...")
        key_arg = to_posix(key_file) if os.name == "nt" else str(key_file)
        self.fake_git({"gpg.format": "ssh", "user.signingkey": key_arg})
        self.assertEqual(
            self.run_probe(),
            f"PROBE: signing-key → ✓ ({key_arg} readable inside sandbox)",
        )

    def test_unreadable_key_file(self) -> None:
        key_file = self.tmp / "missing_key.pub"
        key_arg = to_posix(key_file) if os.name == "nt" else str(key_file)
        self.fake_git({"gpg.format": "ssh", "user.signingkey": key_arg})
        out = self.run_probe()
        self.assertTrue(out.startswith(f"PROBE: signing-key → ✗ ({key_arg} not readable inside sandbox:"))

    def test_writes_nothing_under_tmp(self) -> None:
        key_file = self.tmp / "missing_key.pub"
        key_arg = to_posix(key_file) if os.name == "nt" else str(key_file)
        self.fake_git({"gpg.format": "ssh", "user.signingkey": key_arg})
        started = time.time()
        self.run_probe()
        if OLD_OUTPUT.exists():
            self.assertLess(OLD_OUTPUT.stat().st_mtime, started)
        self.assertFalse((self.tmp / "signing-key.err").exists())


if __name__ == "__main__":
    unittest.main()
