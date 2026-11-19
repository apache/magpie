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
that spelling out of the docs and run the documented self-resolving script
against fake registrations and a real git checkout, under bash and zsh.
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
COMDEV_URL = "https://github.com/apache/comdev.git"
SHELLS = [s for s in ("bash", "zsh") if shutil.which(s)]


def _script() -> str:
    text = COMDEV_MCP.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", text[text.index(SECTION) :], flags=re.S)
    assert len(blocks) == 1, "the section carries exactly one script"
    return blocks[0]


GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.org",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.org",
}


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env={**os.environ, **GIT_ENV}
    )
    return result.stdout.strip()


class NoServerNamePathTest(unittest.TestCase):
    def test_docs_never_build_the_dir_from_the_server_name(self) -> None:
        for doc in DOCS:
            with self.subTest(doc=doc.name):
                self.assertNotIn("mcp/<server>", doc.read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("jq") and SHELLS, "needs jq and bash or zsh")
class SelfResolvingScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="comdev mcp ")  # a space, on purpose
        self.root = Path(self._tmp.name)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        _git("init", "-q", "-b", "main", cwd=self.upstream)
        for name in ("ponymail-mcp", "apache-projects-mcp"):
            server = self.upstream / "mcp" / name
            server.mkdir(parents=True)
            (server / "index.js").write_text("// stub\n", encoding="utf-8")
        _git("add", ".", cwd=self.upstream)
        _git("commit", "-q", "-m", "init", cwd=self.upstream)
        self.comdev = self.root / "code" / "comdev"
        _git("clone", "-q", str(self.upstream), str(self.comdev), cwd=self.root)
        self.start = _git("rev-parse", "HEAD", cwd=self.comdev)
        # The script checks origin is apache/comdev; fetch still reaches the local upstream.
        _git("remote", "set-url", "origin", COMDEV_URL, cwd=self.comdev)
        _git("config", f"url.{self.upstream}.insteadOf", COMDEV_URL, cwd=self.comdev)
        # Upstream moves one commit ahead, so a fetch that silently failed shows up as 0.
        (self.upstream / "CHANGES").write_text("new\n", encoding="utf-8")
        _git("add", ".", cwd=self.upstream)
        _git("commit", "-q", "-m", "ahead", cwd=self.upstream)
        self.home = self.root / "home"
        self.home.mkdir()
        self.cwd = self.root / "elsewhere"
        self.cwd.mkdir()
        self.ponymail = self.comdev / "mcp" / "ponymail-mcp"
        self.projects = self.comdev / "mcp" / "apache-projects-mcp"
        self._register(
            {
                "mcpServers": {"ponymail": {"command": "node", "args": [str(self.ponymail / "index.js")]}},
                "projects": {
                    "/no-servers": {},
                    "/null-servers": {"mcpServers": None},
                    "/tracker": {
                        "mcpServers": {
                            "apache-projects": {
                                "command": "node",
                                "args": [{"not": "a string"}, "--flag", str(self.projects / "index.js")],
                            }
                        }
                    },
                },
            }
        )
        self.bindir = self.root / "bin"
        self.bindir.mkdir()
        self.npm_log = self.root / "npm.log"
        npm = self.bindir / "npm"
        npm.write_text(f'#!/bin/sh\npwd >> "{self.npm_log}"\n', encoding="utf-8")
        npm.chmod(0o755)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _register(self, data: dict) -> None:
        (self.home / ".claude.json").write_text(json.dumps(data), encoding="utf-8")

    def _run(self, shell: str, refresh: bool = False) -> str:
        script = _script()
        if refresh:
            script = script.replace("refresh=no", "refresh=yes", 1)
        env = {**os.environ, **GIT_ENV, "HOME": str(self.home), "PATH": f"{self.bindir}:{os.environ['PATH']}"}
        result = subprocess.run(
            [shell, "-c", script], cwd=self.cwd, env=env, check=True, capture_output=True, text=True
        )
        return result.stdout

    def _npm_dirs(self) -> list[str]:
        if not self.npm_log.exists():
            return []
        return sorted(os.path.realpath(p) for p in self.npm_log.read_text(encoding="utf-8").splitlines())

    def test_reports_each_server_dir_behind_count_and_compare_link(self) -> None:
        head = self.start
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell)
                link = f"https://github.com/apache/comdev/compare/{head}...main"
                self.assertIn(f"ponymail: {self.ponymail} is 1 commit(s) behind; changes: {link}", out)
                self.assertIn(f"apache-projects: {self.projects} is 1 commit(s) behind; changes: {link}", out)
                self.assertEqual(self._npm_dirs(), [], "check mode never installs")
                self.assertEqual(_git("rev-parse", "HEAD", cwd=self.comdev), head, "check mode never merges")

    def test_refresh_fast_forwards_once_and_installs_both_servers(self) -> None:
        for shell in SHELLS:
            with self.subTest(shell=shell):
                _git("reset", "-q", "--hard", self.start, cwd=self.comdev)
                self.npm_log.unlink(missing_ok=True)
                self._run(shell, refresh=True)
                self.assertEqual(
                    _git("rev-parse", "HEAD", cwd=self.comdev), _git("rev-parse", "HEAD", cwd=self.upstream)
                )
                self.assertEqual(
                    self._npm_dirs(), sorted([os.path.realpath(self.ponymail), os.path.realpath(self.projects)])
                )
                self.assertIn("is 0 commit(s) behind", self._run(shell))

    def test_reads_mcp_json_in_the_current_directory(self) -> None:
        self._register({})
        (self.cwd / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"ponymail": {"args": [str(self.ponymail / "index.js")]}}}), encoding="utf-8"
        )
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell)
                self.assertIn(f"ponymail: {self.ponymail} is 1 commit(s) behind", out)
                self.assertNotIn("apache-projects", out)

    def test_names_a_missing_registration(self) -> None:
        self._register({"mcpServers": {"other": {"args": ["/x/index.js"]}}})
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.assertIn("no ponymail or apache-projects registration", self._run(shell))

    def test_skips_a_checkout_off_main(self) -> None:
        _git("checkout", "-q", "-b", "feature", cwd=self.comdev)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell, refresh=True)
                self.assertIn("is on 'feature', not main", out)
                self.assertNotIn("commit(s) behind", out)
                self.assertEqual(self._npm_dirs(), [])

    def test_skips_a_foreign_origin(self) -> None:
        _git("remote", "set-url", "origin", "https://github.com/someone/comdev.git", cwd=self.comdev)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell, refresh=True)
                self.assertIn("not apache/comdev; skipped", out)
                self.assertNotIn("commit(s) behind", out)
                self.assertEqual(self._npm_dirs(), [])

    def test_a_failed_fetch_reports_no_count(self) -> None:
        _git("config", "--unset-all", f"url.{self.upstream}.insteadOf", cwd=self.comdev)
        _git("config", f"url.{self.root / 'gone'}.insteadOf", COMDEV_URL, cwd=self.comdev)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell, refresh=True)
                self.assertIn("fetch failed in", out)
                self.assertNotIn("commit(s) behind", out)
                self.assertEqual(self._npm_dirs(), [])

    def test_a_missing_checkout_is_named(self) -> None:
        self._register({"mcpServers": {"ponymail": {"args": [str(self.root / "deleted/mcp/ponymail-mcp/index.js")]}}})
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.assertIn("is not a git checkout", self._run(shell))


if __name__ == "__main__":
    unittest.main()
