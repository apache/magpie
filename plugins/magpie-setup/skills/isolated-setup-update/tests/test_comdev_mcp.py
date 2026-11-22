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
"""The comdev MCP refresh commands resolve real directories, safely.

The registered server names (`ponymail`, `apache-projects`) are not the
checkout directories (`mcp/ponymail-mcp`, `mcp/apache-projects-mcp`), so
a command built as `mcp/<server>` fails in every shell. These tests keep
that spelling out of the docs and run the documented self-resolving script
against fake registrations and a real git checkout, under bash and under
zsh with interactive comments off (how a pasted script runs there).

A `git` wrapper on PATH sends only `fetch` to a local upstream, so the
script's origin check still sees the real GitHub URL.
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
REAL_GIT = shutil.which("git")
# git exports these to its hooks (GIT_INDEX_FILE on every commit), so a test run from
# a commit hook would point its scratch repositories at the commit's own index. The
# config ones carry `git -c` values and the whole-user dispatcher's core.hooksPath,
# which would override the empty global and system config below.
REPO_GIT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
)
BASE_ENV = {
    k: v
    for k, v in os.environ.items()
    if k not in REPO_GIT_VARS and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
}
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.org",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.org",
}


def _script() -> str:
    text = COMDEV_MCP.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", text[text.index(SECTION) :], flags=re.S)
    assert len(blocks) == 1, "the section carries exactly one script"
    return blocks[0]


def _git(*args: str, cwd: Path) -> str:
    assert REAL_GIT is not None, "the test class is skipped without git"
    result = subprocess.run(
        [REAL_GIT, *args], cwd=cwd, check=True, capture_output=True, text=True, env={**BASE_ENV, **GIT_ENV}
    )
    return result.stdout.strip()


class DocsTest(unittest.TestCase):
    def test_docs_never_build_the_dir_from_the_server_name(self) -> None:
        for doc in DOCS:
            with self.subTest(doc=doc.name):
                self.assertNotIn("mcp/<server>", doc.read_text(encoding="utf-8"))

    def test_script_reads_no_project_file_and_has_no_comments(self) -> None:
        script = _script()
        self.assertNotIn(".mcp.json", script)
        self.assertIsNone(re.search(r"(^|\s)#", script), "interactive zsh would run a # as a command")
        self.assertNotIn("!", script, "interactive zsh would take a ! for history expansion")


@unittest.skipUnless(shutil.which("jq") and SHELLS and REAL_GIT, "needs jq, git and bash or zsh")
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
            (server / "package-lock.json").write_text("{}\n", encoding="utf-8")
        _git("add", ".", cwd=self.upstream)
        _git("commit", "-q", "-m", "init", cwd=self.upstream)
        self.comdev = self.root / "code" / "comdev"
        _git("clone", "-q", str(self.upstream), str(self.comdev), cwd=self.root)
        _git("remote", "set-url", "origin", COMDEV_URL, cwd=self.comdev)
        self.start = _git("rev-parse", "HEAD", cwd=self.comdev)
        # Upstream moves one commit ahead, so a fetch that silently failed would show 0.
        (self.upstream / "CHANGES").write_text("new\n", encoding="utf-8")
        _git("add", ".", cwd=self.upstream)
        _git("commit", "-q", "-m", "ahead", cwd=self.upstream)
        self.ahead = _git("rev-parse", "HEAD", cwd=self.upstream)

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
        self._fetch_from(self.upstream)
        self.npm_log = self.root / "npm.log"
        self.npm_fail_once = self.root / "npm-fail-once"
        self.npm_rewrites_lock = self.root / "npm-rewrites-lock"
        npm = self.bindir / "npm"
        # Reads stdin like an interactive tool would: without </dev/null it would swallow the loop's input.
        npm.write_text(
            "#!/bin/sh\ncat >/dev/null\n"
            f'if [ -e "{self.npm_fail_once}" ]; then rm "{self.npm_fail_once}"; exit 1; fi\n'
            f'if [ -e "{self.npm_rewrites_lock}" ]; then echo rewritten >> package-lock.json; fi\n'
            f'pwd >> "{self.npm_log}"\n',
            encoding="utf-8",
        )
        npm.chmod(0o755)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fetch_from(self, source: Path) -> None:
        shim = self.bindir / "git"
        shim.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do\n'
            f'  [ "$a" = fetch ] && exec "{REAL_GIT}" -c "url.{source}.insteadOf={COMDEV_URL}" "$@"\n'
            "done\n"
            f'exec "{REAL_GIT}" "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)

    def _register(self, data: object) -> None:
        text = data if isinstance(data, str) else json.dumps(data)
        (self.home / ".claude.json").write_text(text, encoding="utf-8")

    def _run(self, shell: str, refresh: str = "") -> str:
        script = _script()
        if refresh:
            self.assertTrue(script.startswith("(\nrefresh=\n"))
            script = script.replace("(\nrefresh=\n", f"(\nrefresh={refresh}\n", 1)
        if shell == "zsh":
            script = "setopt no_interactive_comments\n" + script
        env = {**BASE_ENV, **GIT_ENV, "HOME": str(self.home), "PATH": f"{self.bindir}:{os.environ['PATH']}"}
        result = subprocess.run([shell, "-c", script], cwd=self.cwd, env=env, capture_output=True, text=True)
        return result.stdout + result.stderr

    def _reset(self) -> None:
        _git("reset", "-q", "--hard", self.start, cwd=self.comdev)
        self.npm_log.unlink(missing_ok=True)

    def _npm_dirs(self) -> list[str]:
        if not self.npm_log.exists():
            return []
        return sorted(os.path.realpath(p) for p in self.npm_log.read_text(encoding="utf-8").splitlines())

    def _both_dirs(self) -> list[str]:
        return sorted([os.path.realpath(self.ponymail), os.path.realpath(self.projects)])

    def _head(self) -> str:
        return _git("rev-parse", "HEAD", cwd=self.comdev)

    def test_reports_each_server_against_the_fetched_commit(self) -> None:
        link = f"https://github.com/apache/comdev/compare/{self.start}...{self.ahead}"
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell)
                self.assertIn(
                    f"ponymail: {self.ponymail} is 1 commit(s) behind apache/comdev main at {self.ahead}; "
                    f"changes: {link}",
                    out,
                )
                self.assertIn(
                    f"apache-projects: {self.projects} is 1 commit(s) behind apache/comdev main", out
                )
                self.assertIn("run this again with refresh=<the commit after 'main at'>", out)
                self.assertEqual(self._npm_dirs(), [], "report mode never installs")
                self.assertEqual(self._head(), self.start, "report mode never merges")

    def test_refresh_fast_forwards_and_installs_both_servers_of_a_shared_checkout(self) -> None:
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self._reset()
                out = self._run(shell, refresh=self.ahead)
                self.assertEqual(out.count("is 1 commit(s) behind"), 2, "both report before anything moves")
                self.assertEqual(self._head(), self.ahead)
                self.assertEqual(self._npm_dirs(), self._both_dirs(), "a stdin-reading npm skips no server")
                self.assertIn("npm install done", out)

    def test_a_failed_npm_install_is_retried_by_the_next_run(self) -> None:
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self._reset()
                self.npm_fail_once.touch()
                out = self._run(shell, refresh=self.ahead)
                self.assertIn("npm install failed in", out)
                self.assertEqual(self._head(), self.ahead)
                self.npm_log.unlink(missing_ok=True)
                out = self._run(shell, refresh=self.ahead)
                self.assertEqual(out.count("is 0 commit(s) behind"), 2)
                self.assertEqual(self._npm_dirs(), self._both_dirs())

    def test_ignores_a_project_mcp_json(self) -> None:
        self._register({})
        hostile = self.root / "hostile"
        (self.cwd / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"ponymail": {"args": [str(hostile / "mcp/ponymail-mcp/index.js")]}}}),
            encoding="utf-8",
        )
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell, refresh=self.ahead)
                self.assertIn("no ponymail or apache-projects registration in ~/.claude.json", out)
                self.assertNotIn(str(hostile), out)

    def test_names_a_missing_registration(self) -> None:
        self._register({"mcpServers": {"other": {"args": ["/x/index.js"]}}})
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.assertIn("no ponymail or apache-projects registration", self._run(shell))

    def test_a_malformed_registration_is_not_reported_as_absent(self) -> None:
        self._register("{not json")
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell)
                self.assertIn("could not parse ~/.claude.json", out)
                self.assertNotIn("no ponymail", out)

    def test_skips_a_checkout_off_main(self) -> None:
        _git("checkout", "-q", "-b", "feature", cwd=self.comdev)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell, refresh=self.ahead)
                self.assertIn("is on 'feature', not main", out)
                self.assertNotIn("commit(s) behind", out)
                self.assertEqual(self._npm_dirs(), [])

    def test_skips_any_origin_but_apache_comdev_on_github(self) -> None:
        lookalikes = [
            "https://github.com/someone/comdev.git",
            "https://notgithub.com/apache/comdev.git",
            "https://notgithub.com/apache/comdev",
            "https://evil.example/github.com/apache/comdev.git",
            "https://evil.example/github.com/apache/comdev",
            "ssh://git@evil.example/github.com/apache/comdev",
            "http://github.com/apache/comdev.git",
            "git@notgithub.com:apache/comdev.git",
            str(self.upstream),
        ]
        for url in lookalikes:
            _git("remote", "set-url", "origin", url, cwd=self.comdev)
            for shell in SHELLS:
                with self.subTest(url=url, shell=shell):
                    out = self._run(shell, refresh=self.ahead)
                    self.assertIn("not apache/comdev; skipped", out)
                    self.assertNotIn("commit(s) behind", out)
                    self.assertEqual(self._npm_dirs(), [])
                    self.assertEqual(self._head(), self.start)

    def test_an_insteadof_rewrite_cannot_pass_the_origin_check(self) -> None:
        _git("config", f"url.{self.upstream}.insteadOf", COMDEV_URL, cwd=self.comdev)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.assertIn("not apache/comdev; skipped", self._run(shell, refresh=self.ahead))
                self.assertEqual(self._head(), self.start)

    def test_a_second_origin_url_cannot_pass_the_origin_check(self) -> None:
        _git("remote", "set-url", "--add", "origin", "https://evil.example/comdev.git", cwd=self.comdev)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.assertIn("not apache/comdev; skipped", self._run(shell, refresh=self.ahead))

    def test_a_failed_fetch_reports_no_count(self) -> None:
        self._fetch_from(self.root / "gone")
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell, refresh=self.ahead)
                self.assertIn("fetch failed in", out)
                self.assertNotIn("commit(s) behind", out)
                self.assertEqual(self._npm_dirs(), [])
                self.assertEqual(self._head(), self.start)

    def test_a_missing_checkout_is_named(self) -> None:
        self._register(
            {"mcpServers": {"ponymail": {"args": [str(self.root / "deleted/mcp/ponymail-mcp/index.js")]}}}
        )
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.assertIn("is not a git checkout", self._run(shell))

    def test_refresh_stops_at_the_reviewed_commit(self) -> None:
        # main moves on after the report; the refresh must not take the unreviewed commit.
        (self.upstream / "LATER").write_text("unreviewed\n", encoding="utf-8")
        _git("add", ".", cwd=self.upstream)
        _git("commit", "-q", "-m", "later", cwd=self.upstream)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self._reset()
                out = self._run(shell, refresh=self.ahead)
                self.assertEqual(self._head(), self.ahead)
                self.assertIn(f"is at {self.ahead}, npm install done", out)
                self.assertEqual(self._npm_dirs(), self._both_dirs())

    def test_refresh_refuses_a_commit_not_on_the_fetched_main(self) -> None:
        _git("checkout", "-q", "-b", "side", self.start, cwd=self.upstream)
        (self.upstream / "SIDE").write_text("side\n", encoding="utf-8")
        _git("add", ".", cwd=self.upstream)
        _git("commit", "-q", "-m", "side", cwd=self.upstream)
        side = _git("rev-parse", "HEAD", cwd=self.upstream)
        _git("checkout", "-q", "main", cwd=self.upstream)
        _git("fetch", "-q", str(self.upstream), "side", cwd=self.comdev)
        for shell in SHELLS:
            with self.subTest(shell=shell, target="side commit"):
                out = self._run(shell, refresh=side)
                self.assertIn("is not on the main just fetched", out)
                self.assertEqual(self._head(), self.start)
                self.assertEqual(self._npm_dirs(), [])
            with self.subTest(shell=shell, target="unknown"):
                out = self._run(shell, refresh="0" * 40)
                self.assertIn("is not on the main just fetched", out)
                self.assertEqual(self._head(), self.start)

    def test_checkout_hooks_never_run(self) -> None:
        marker = self.root / "hook-ran"
        hooks = self.comdev / ".git" / "hooks"
        for hook in ("reference-transaction", "post-merge", "post-checkout"):
            path = hooks / hook
            path.write_text(f'#!/bin/sh\necho {hook} >> "{marker}"\n', encoding="utf-8")
            path.chmod(0o755)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self._reset()
                marker.unlink(missing_ok=True)
                self._run(shell)
                self._run(shell, refresh=self.ahead)
                self.assertEqual(self._head(), self.ahead)
                self.assertFalse(marker.exists(), marker.read_text() if marker.exists() else "")

    def test_only_absolute_index_js_paths_count(self) -> None:
        self._register(
            {
                "mcpServers": {
                    "ponymail": {"args": ["mcp/ponymail-mcp/index.js"]},
                    "apache-projects": {"args": [f"--require={self.projects / 'index.js'}"]},
                }
            }
        )
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.assertIn("no ponymail or apache-projects registration", self._run(shell))

    def test_odd_but_valid_shapes_do_not_hide_a_good_registration(self) -> None:
        self._register(
            {
                "mcpServers": {
                    "ponymail": "not an object",
                    "apache-projects": {"args": "not a list"},
                },
                "projects": {
                    "/a": "not an object",
                    "/b": {"mcpServers": "not an object"},
                    "/c": {"mcpServers": {"ponymail": {"args": [str(self.ponymail / "index.js")]}}},
                },
            }
        )
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell)
                self.assertNotIn("could not parse", out)
                self.assertIn(f"ponymail: {self.ponymail} is 1 commit(s) behind", out)

    def test_a_lockfile_rewritten_by_the_first_install_does_not_block_the_second(self) -> None:
        self.npm_rewrites_lock.touch()
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self._reset()
                out = self._run(shell, refresh=self.ahead)
                self.assertNotIn("local changes", out)
                self.assertEqual(self._npm_dirs(), self._both_dirs())

    def test_refresh_refuses_a_checkout_with_local_changes(self) -> None:
        changes = {
            "modified": lambda: (self.ponymail / "package-lock.json").write_text(
                '{"x": 1}\n', encoding="utf-8"
            ),
            "untracked": lambda: (self.ponymail / ".npmrc").write_text("x\n", encoding="utf-8"),
        }
        for kind, make in changes.items():
            for shell in SHELLS:
                with self.subTest(kind=kind, shell=shell):
                    self._reset()
                    _git("clean", "-q", "-fd", cwd=self.comdev)
                    make()
                    out = self._run(shell, refresh=self.ahead)
                    self.assertEqual(out.count("has local changes"), 2)
                    self.assertEqual(self._head(), self.start)
                    self.assertEqual(self._npm_dirs(), [])

    def test_refresh_refuses_a_checkout_already_past_the_commit(self) -> None:
        (self.upstream / "LATER").write_text("later\n", encoding="utf-8")
        _git("add", ".", cwd=self.upstream)
        _git("commit", "-q", "-m", "later", cwd=self.upstream)
        later = _git("rev-parse", "HEAD", cwd=self.upstream)
        _git("fetch", "-q", str(self.upstream), "main", cwd=self.comdev)
        _git("reset", "-q", "--hard", later, cwd=self.comdev)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                out = self._run(shell, refresh=self.ahead)
                self.assertIn(f"has commits that {self.ahead} lacks", out)
                self.assertNotIn("npm install done", out)
                self.assertEqual(self._head(), later)
                self.assertEqual(self._npm_dirs(), [])

    def test_refresh_takes_only_a_full_commit_hash(self) -> None:
        for value in ("main", "origin/main", self.ahead[:12], "-x", self.ahead.upper()):
            for shell in SHELLS:
                with self.subTest(value=value, shell=shell):
                    out = self._run(shell, refresh=value)
                    self.assertIn("refresh= takes the full 40-character commit", out)
                    self.assertEqual(self._head(), self.start)
                    self.assertEqual(self._npm_dirs(), [])

    @unittest.skipUnless("zsh" in SHELLS, "needs zsh")
    def test_pasted_into_interactive_zsh_it_reports_and_refreshes(self) -> None:
        # A real paste: interactive zsh reading the script, with history expansion and no
        # interactive comments, as the operator's terminal has by default.
        env = {**BASE_ENV, **GIT_ENV, "HOME": str(self.home), "PATH": f"{self.bindir}:{os.environ['PATH']}"}
        for refresh in ("", self.ahead):
            with self.subTest(refresh=refresh or "report"):
                script = _script().replace("(\nrefresh=\n", f"(\nrefresh={refresh}\n", 1)
                result = subprocess.run(
                    ["zsh", "-f", "-i"],
                    input=script + "exit\n",
                    cwd=self.cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    # Without a session of its own, interactive zsh takes over the terminal
                    # pytest runs in and, from a background worker, stops waiting for it.
                    start_new_session=True,
                )
                out = result.stdout + result.stderr
                self.assertNotIn("event not found", out)
                self.assertNotIn("command not found", out)
                self.assertIn(f"ponymail: {self.ponymail} is 1 commit(s) behind", out)
        self.assertEqual(self._head(), self.ahead)
        self.assertEqual(self._npm_dirs(), self._both_dirs())

    def test_a_non_object_document_is_not_a_parse_error(self) -> None:
        self._register([1, 2, 3])
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.assertIn("no ponymail or apache-projects registration", self._run(shell))


if __name__ == "__main__":
    unittest.main()
