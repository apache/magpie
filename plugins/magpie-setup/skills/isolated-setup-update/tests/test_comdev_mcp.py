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
"""The comdev MCP refresh commands resolve real directories.

The registered server names (`ponymail`, `apache-projects`) are not the
checkout directories (`mcp/ponymail-mcp`, `mcp/apache-projects-mcp`), so
a command built as `mcp/<server>` fails in every shell. These tests keep
that spelling out of the docs and run the documented self-resolving check
against a fake registration and a real git checkout.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parents[3]
COMDEV_MCP = SKILL_DIR / "comdev-mcp.md"
DOCS = [
    COMDEV_MCP,
    REPO_ROOT / "plugins" / "magpie-setup" / "skills" / "setup" / "update.md",
    REPO_ROOT / "docs" / "setup" / "secure-agent-setup.md",
]
SECTION = "## When the registration cannot be read"


def _section_bash_blocks() -> list[str]:
    text = COMDEV_MCP.read_text(encoding="utf-8")
    section = text[text.index(SECTION) :]
    return re.findall(r"```bash\n(.*?)```", section, flags=re.S)


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull},
    )


class NoServerNamePathTest(unittest.TestCase):
    def test_docs_never_build_the_dir_from_the_server_name(self) -> None:
        for doc in DOCS:
            with self.subTest(doc=doc.name):
                self.assertNotIn("mcp/<server>", doc.read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("jq") and shutil.which("bash"), "needs jq and bash")
class SelfResolvingCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        upstream = self.root / "upstream"
        upstream.mkdir()
        _git("init", "-q", "-b", "main", cwd=upstream)
        for name in ("ponymail-mcp", "apache-projects-mcp"):
            server = upstream / "mcp" / name
            server.mkdir(parents=True)
            (server / "index.js").write_text("// stub\n", encoding="utf-8")
        _git("add", ".", cwd=upstream)
        _git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "init", cwd=upstream)
        self.comdev = self.root / "code" / "comdev"
        _git("clone", "-q", str(upstream), str(self.comdev), cwd=self.root)
        self.home = self.root / "home"
        self.home.mkdir()
        registration = {
            "mcpServers": {
                "ponymail": {"command": "node", "args": [str(self.comdev / "mcp/ponymail-mcp/index.js")]}
            },
            "projects": {
                "/elsewhere": {},
                "/tracker": {
                    "mcpServers": {
                        "apache-projects": {
                            "command": "node",
                            "args": [str(self.comdev / "mcp/apache-projects-mcp/index.js")],
                        }
                    }
                },
            },
        }
        (self.home / ".claude.json").write_text(json.dumps(registration), encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, script: str) -> str:
        env = {
            **os.environ,
            "HOME": str(self.home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        result = subprocess.run(
            ["bash", "-c", script], cwd=self.root, env=env, check=True, capture_output=True, text=True
        )
        return result.stdout

    def test_check_reports_each_server_dir_from_any_cwd(self) -> None:
        check, _refresh = _section_bash_blocks()
        out = self._run(check)
        self.assertIn(f"ponymail: {self.comdev / 'mcp/ponymail-mcp'} is 0 commit(s) behind", out)
        self.assertIn(
            f"apache-projects: {self.comdev / 'mcp/apache-projects-mcp'} is 0 commit(s) behind", out
        )

    def test_check_names_an_unregistered_server(self) -> None:
        (self.home / ".claude.json").write_text("{}", encoding="utf-8")
        check, _refresh = _section_bash_blocks()
        out = self._run(check)
        self.assertIn("ponymail: not registered", out)
        self.assertIn("apache-projects: not registered", out)

    def test_refresh_targets_the_server_dirs(self) -> None:
        _check, refresh = _section_bash_blocks()
        # Stub npm so the test needs no Node toolchain; it records where it ran.
        bindir = self.root / "bin"
        bindir.mkdir()
        log = self.root / "npm.log"
        npm = bindir / "npm"
        npm.write_text(f'#!/bin/sh\npwd >> "{log}"\n', encoding="utf-8")
        npm.chmod(0o755)
        self._run(f'PATH="{bindir}:$PATH"\n{refresh}')
        ran_in = log.read_text(encoding="utf-8").split()
        self.assertEqual(
            [os.path.realpath(p) for p in ran_in],
            [
                os.path.realpath(self.comdev / "mcp/ponymail-mcp"),
                os.path.realpath(self.comdev / "mcp/apache-projects-mcp"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
