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

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from pr_management.stack_review import stack_chain

# The tests build throwaway repositories; location-redirecting git variables
# inherited from a hook would point `git` at the outer repository instead.
for _var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX"):
    os.environ.pop(_var, None)
# A contributor's global and system config (a hooks path, signing, templates)
# must not run against the throwaway repositories.
os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"

PREFIX = "magpie-stack/test"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@unittest.skipIf(shutil.which("git") is None, "git not installed")
class ChainTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "Tester")
        _git(self.repo, "config", "commit.gpgsign", "false")
        self.base = _commit(self.repo, "pkg/compat.py", "def shim():\n    return 1\n", "initial")
        _commit(self.repo, "pkg/user.py", "from pkg.compat import shim\nvalue = shim()\n", "add user")
        _git(self.repo, "update-ref", f"refs/{PREFIX}/trunk", "HEAD")
        _git(self.repo, "checkout", "-q", "-b", "stack")
        self._cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def _layer(self, position: int, path: str, content: str, message: str) -> str:
        sha = _commit(self.repo, path, content, message)
        _git(self.repo, "update-ref", f"refs/{PREFIX}/{position}", sha)
        return sha

    def test_linear_chain_reports_own_commits_and_no_trunk_drift(self) -> None:
        self._layer(1, "pkg/user.py", "value = 1\n", "layer 1: drop the shim call")
        self._layer(2, "pkg/compat.py", "", "layer 2: remove the shim")
        report = stack_chain.chain(PREFIX, 2)
        self.assertTrue(report["linear"])
        self.assertEqual(report["behind_trunk_commits"], 0)
        self.assertEqual(report["trunk_touches_stack_files"], [])
        layers = report["layers"]
        self.assertEqual(
            [
                (layer["position"], layer["contains_below"], layer["own_commits"], layer["merge_commits"])
                for layer in layers
            ],
            [(1, True, 1, 0), (2, True, 1, 0)],
        )
        self.assertEqual(layers[1]["commit_headlines"], ["layer 2: remove the shim"])

    def test_stale_base_breaks_linearity_but_trunk_drift_is_only_counted(self) -> None:
        head1 = self._layer(1, "pkg/user.py", "value = 1\n", "layer 1")
        self._layer(2, "pkg/compat.py", "", "layer 2")
        # Amend layer 1 without cascading: layer 2 no longer contains layer 1's head.
        _git(self.repo, "checkout", "-q", head1)
        new_head1 = _commit(self.repo, "pkg/user.py", "value = 2\n", "layer 1 amended")
        _git(self.repo, "update-ref", f"refs/{PREFIX}/1", new_head1)
        # The trunk moved on in a file the stack also edits.
        _git(self.repo, "checkout", "-q", "main")
        _commit(self.repo, "pkg/compat.py", "def shim():\n    return 2\n", "trunk moves")
        _git(self.repo, "update-ref", f"refs/{PREFIX}/trunk", "HEAD")
        report = stack_chain.chain(PREFIX, 2)
        self.assertFalse(report["linear"])
        self.assertTrue(report["layers"][0]["contains_below"])
        self.assertFalse(report["layers"][1]["contains_below"])
        self.assertEqual(report["behind_trunk_commits"], 1)
        self.assertEqual(report["trunk_touches_stack_files"], ["pkg/compat.py"])

    def test_seams_report_dependents_at_own_head_later_heads_and_new_trunk_uses(self) -> None:
        # Layer 1 removes the shim while pkg/user.py still imports it: not green alone.
        self._layer(1, "pkg/compat.py", "", "layer 1: remove shim")
        # Layer 2 fixes the dependent.
        self._layer(2, "pkg/user.py", "value = 1\n", "layer 2: fix user")
        # Meanwhile the trunk gained a new use of the removed name.
        _git(self.repo, "checkout", "-q", "main")
        _commit(self.repo, "pkg/other.py", "from pkg.compat import shim\n", "trunk adds a use")
        _git(self.repo, "update-ref", f"refs/{PREFIX}/trunk", "HEAD")
        report = stack_chain.seams(PREFIX, 2)
        hits = report["layers"][0]["hits"]["shim"]
        self.assertEqual(hits["removed_in"], "pkg/compat.py")
        self.assertEqual(len(hits["at_own_head"]), 2)  # import + call in pkg/user.py
        self.assertEqual(hits["at_later_heads"], {})
        self.assertEqual([h.split(":")[0] for h in hits["new_on_trunk"]], ["pkg/other.py"])
        self.assertEqual(report["layers"][1]["hits"], {})

    def test_removed_definitions_ignore_renames_within_the_same_diff(self) -> None:
        diff = "diff --git a/m.py b/m.py\n--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,2 @@\n-def old_name():\n+def old_name_v2():\n-MAX_SIZE = 3\n+MAX_SIZE = 4\n-def tiny():\n"
        removed, deleted = stack_chain.removed_definitions(diff)
        self.assertEqual(removed, {"old_name": "m.py", "tiny": "m.py"})
        self.assertEqual(deleted, [])
        deleted_diff = "diff --git a/pkg/legacy_mod.py b/pkg/legacy_mod.py\ndeleted file mode 100644\n"
        self.assertEqual(stack_chain.removed_definitions(deleted_diff), ({}, ["pkg/legacy_mod.py"]))
        self.assertEqual(stack_chain.module_name("pkg/legacy_mod/__init__.py"), "legacy_mod")

    def test_chain_reports_commit_messages_and_a_stable_heads_digest(self) -> None:
        head1 = self._layer(
            1,
            "pkg/user.py",
            "value = 1\n",
            "layer 1: drop the shim call\n\nThe call is dead on 3.11+.\nKept the import for layer 2.",
        )
        head2 = self._layer(2, "pkg/compat.py", "", "layer 2: remove the shim")
        report = stack_chain.chain(PREFIX, 2)
        msgs = report["layers"][0]["commit_messages"]
        self.assertEqual(msgs[0]["headline"], "layer 1: drop the shim call")
        self.assertEqual(msgs[0]["body"], "The call is dead on 3.11+.\nKept the import for layer 2.")
        self.assertEqual(msgs[0]["sha"], head1)
        self.assertEqual(report["layers"][1]["commit_messages"][0]["body"], "")
        self.assertEqual(report["heads_digest"], stack_chain.heads_digest({1: head1, 2: head2}))
        self.assertEqual(len(report["heads_digest"]), 16)
        # The digest hashes "<k>:<sha>\n" lines in position order, so ordering of the dict does not matter.
        self.assertEqual(stack_chain.heads_digest({2: head2, 1: head1}), report["heads_digest"])
        self.assertNotEqual(stack_chain.heads_digest({1: head2, 2: head1}), report["heads_digest"])

    def test_seams_list_removed_names_even_without_hits(self) -> None:
        self._layer(1, "pkg/user.py", "value = 1\n", "layer 1")
        self._layer(2, "pkg/compat.py", "", "layer 2: remove shim")
        report = stack_chain.seams(PREFIX, 2)
        self.assertEqual(report["layers"][1]["removed_names"], ["shim"])
        self.assertEqual(report["layers"][1]["hits"], {})

    def test_floors_report_declared_runtime_floors_and_where_they_move(self) -> None:
        _commit(self.repo, "pkg/pyproject.toml", 'requires-python = ">=3.10"\n', "manifest")
        _commit(self.repo, "svc/go.mod", "module example.com/svc\n\ngo 1.22\n", "go module")
        _git(self.repo, "update-ref", f"refs/{PREFIX}/trunk", "HEAD")
        self._layer(1, "pkg/user.py", "value = 1\n", "layer 1")
        self._layer(2, "pkg/pyproject.toml", 'requires-python = ">=3.11"\n', "layer 2: bump floor")
        report = stack_chain.floors(PREFIX, 2)
        self.assertEqual(report["trunk"], {"pkg/pyproject.toml": ">=3.10", "svc/go.mod": "1.22"})
        self.assertEqual(report["layers"][0]["floors"]["pkg/pyproject.toml"], ">=3.10")
        self.assertEqual(report["layers"][1]["floors"]["pkg/pyproject.toml"], ">=3.11")
        self.assertEqual(
            report["floor_changes"],
            [
                {
                    "position": 2,
                    "moved": {"pkg/pyproject.toml": {"from": ">=3.10", "to": ">=3.11"}},
                    "added_manifests": {},
                    "removed_manifests": {},
                }
            ],
        )

    def test_floors_read_pep723_script_headers(self) -> None:
        _commit(
            self.repo,
            "scripts/check.py",
            '# /// script\n# requires-python = ">=3.10"\n# ///\nprint(1)\n',
            "script",
        )
        _git(self.repo, "update-ref", f"refs/{PREFIX}/trunk", "HEAD")
        self._layer(
            1,
            "scripts/check.py",
            '# /// script\n# requires-python = ">=3.11"\n# ///\nprint(1)\n',
            "layer 1: bump header",
        )
        report = stack_chain.floors(PREFIX, 1)
        self.assertEqual(report["trunk"]["scripts/check.py"], ">=3.10")
        self.assertEqual(
            report["floor_changes"][0]["moved"], {"scripts/check.py": {"from": ">=3.10", "to": ">=3.11"}}
        )

    def test_floors_separate_new_manifests_from_moves_and_repo_flag_sets_cwd(self) -> None:
        self._layer(1, "svc/go.mod", "module example.com/svc\n\ngo 1.25.0\n", "layer 1: new go module")
        report = stack_chain.floors(PREFIX, 1)
        self.assertEqual(
            report["floor_changes"],
            [
                {
                    "position": 1,
                    "moved": {},
                    "added_manifests": {"svc/go.mod": "1.25.0"},
                    "removed_manifests": {},
                }
            ],
        )
        os.chdir(self._cwd)  # run from elsewhere: --repo must point the scripts at the clone
        self.addCleanup(setattr, stack_chain, "REPO", None)
        out = io.StringIO()
        with redirect_stdout(out):
            stack_chain.main(["--repo", str(self.repo), "chain", "--prefix", PREFIX, "--size", "1"])
        self.assertEqual(json.loads(out.getvalue())["layers"][0]["own_commits"], 1)

    def test_fetch_and_cleanup_commands(self) -> None:
        cmd = stack_chain.fetch_command(
            "https://example.invalid/o/r.git", "magpie-stack/7", "main", {2: 12, 1: 11}
        )
        self.assertEqual(
            cmd,
            "git fetch --no-tags https://example.invalid/o/r.git +refs/heads/main:refs/magpie-stack/7/trunk "
            "+refs/pull/11/head:refs/magpie-stack/7/1 +refs/pull/12/head:refs/magpie-stack/7/2",
        )
        self.assertEqual(
            stack_chain.cleanup_command("magpie-stack/7", 2),
            "git update-ref -d refs/magpie-stack/7/trunk && git update-ref -d refs/magpie-stack/7/1 && git update-ref -d refs/magpie-stack/7/2",
        )

    def test_chain_fails_loudly_when_refs_are_missing(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            stack_chain.chain(PREFIX, 3)
        self.assertIn("missing refs", str(ctx.exception))

    def test_from_skips_a_merged_bottom_layer(self) -> None:
        # Layer 1 was squash-merged into the trunk and layer 2 rebased onto it;
        # only layer 2 is fetched. Analysing from position 2 must not report
        # the squash commit as trunk drift or layer 2 as missing its base.
        _git(self.repo, "checkout", "-q", "main")
        _commit(self.repo, "pkg/user.py", "value = 1\n", "layer 1 (squash-merged)")
        _git(self.repo, "update-ref", f"refs/{PREFIX}/trunk", "HEAD")
        self._layer(2, "pkg/compat.py", "", "layer 2: remove the shim")
        report = stack_chain.chain(PREFIX, 2, start=2)
        self.assertTrue(report["linear"])
        self.assertEqual(report["behind_trunk_commits"], 0)
        self.assertEqual(report["trunk_touches_stack_files"], [])
        self.assertEqual([layer["position"] for layer in report["layers"]], [2])
        self.assertEqual(report["layers"][0]["own_commits"], 1)
        self.assertEqual(
            [layer["position"] for layer in stack_chain.seams(PREFIX, 2, start=2)["layers"]], [2]
        )
        self.assertEqual(stack_chain.floors(PREFIX, 2, start=2)["floor_changes"], [])
        with self.assertRaises(SystemExit):
            stack_chain.chain(PREFIX, 2, start=3)

    def test_new_on_trunk_compares_full_hit_sets_before_capping(self) -> None:
        uses = [f"from pkg.compat import shim  # use {i:02d}\n" for i in range(20)]
        _commit(self.repo, "pkg/many.py", "".join(uses), "twenty uses")
        merge_base = _git(self.repo, "rev-parse", "HEAD")
        # The trunk drops the first use. Capping each side at 12 before comparing
        # would report "use 12" as new; nothing is.
        _commit(self.repo, "pkg/many.py", "".join(uses[1:]), "drop one use")
        trunk = _git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(stack_chain.new_on_trunk("shim", merge_base, trunk), [])

    def test_grep_matches_names_literally(self) -> None:
        _commit(self.repo, "web/app.js", "const get$ = 1;\nexport const getter = get$;\n", "js")
        hits = stack_chain.grep_at("HEAD", "get$")
        self.assertEqual([h.split(":")[0] for h in hits], ["web/app.js", "web/app.js"])

    def test_non_utf8_files_do_not_end_the_run(self) -> None:
        target = self.repo / "data" / "latin1.properties"
        target.parent.mkdir(parents=True)
        target.write_bytes("name=\xe9t\xe9 \xe0 Z\xfcrich\n".encode("latin-1"))
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "latin-1 file")
        self._layer(1, "pkg/compat.py", "", "layer 1: remove shim")
        report = stack_chain.seams(PREFIX, 1)
        self.assertIn("shim", report["layers"][0]["hits"])

    def test_constants_are_only_extracted_from_source_files(self) -> None:
        diff = (
            "diff --git a/Makefile b/Makefile\n--- a/Makefile\n+++ b/Makefile\n@@ -1 +0,0 @@\n-PATH=/usr/bin\n"
            "diff --git a/pkg/settings.py b/pkg/settings.py\n--- a/pkg/settings.py\n+++ b/pkg/settings.py\n"
            "@@ -1 +0,0 @@\n-TIMEOUT = 30\n"
        )
        self.assertEqual(stack_chain.removed_definitions(diff), ({"TIMEOUT": "pkg/settings.py"}, []))

    def test_fetch_command_quotes_the_trunk_and_digest_runs_without_refs(self) -> None:
        cmd = stack_chain.fetch_command(
            "https://example.invalid/o/r.git", "magpie-stack/7", "main;`id`", {1: 11}
        )
        self.assertIn("'+refs/heads/main;`id`:refs/magpie-stack/7/trunk'", cmd)
        out = io.StringIO()
        with redirect_stdout(out):
            stack_chain.main(["digest", "--head", f"2={'a' * 40}", "--head", f"3={'b' * 40}"])
        self.assertEqual(out.getvalue().strip(), stack_chain.heads_digest({2: "a" * 40, 3: "b" * 40}))
        with self.assertRaises(SystemExit):
            stack_chain.main(["seams", "--prefix", PREFIX, "--size", "2", "--layers", "3,x"])


if __name__ == "__main__":
    unittest.main()
