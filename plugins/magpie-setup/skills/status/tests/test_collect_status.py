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
"""Where the status dashboard says personal config lives.

The `git_common_dir` vectors are the same as in
`tools/setup-preflight/tests/test_layers.py`.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import collect_status as cs


class GitCommonDirVectors(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_vector_dot_git_directory_is_the_common_dir(self) -> None:
        (self.tmp / ".git").mkdir()
        self.assertEqual(cs.git_common_dir(self.tmp), self.tmp / ".git")

    def test_vector_worktree_file_with_relative_commondir(self) -> None:
        main = self.tmp / "main"
        wt_gitdir = main / ".git" / "worktrees" / "wt"
        wt_gitdir.mkdir(parents=True)
        (wt_gitdir / "commondir").write_text("../..\n")
        wt = self.tmp / "wt"
        wt.mkdir()
        (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
        self.assertEqual(cs.git_common_dir(wt), main / ".git")

    def test_vector_worktree_file_with_relative_gitdir(self) -> None:
        main = self.tmp / "main"
        wt_gitdir = main / ".git" / "worktrees" / "wt"
        wt_gitdir.mkdir(parents=True)
        (wt_gitdir / "commondir").write_text("../..\n")
        wt = main / "nested" / "wt"
        wt.mkdir(parents=True)
        (wt / ".git").write_text("gitdir: ../../.git/worktrees/wt\n")
        self.assertEqual(cs.git_common_dir(wt), main / ".git")

    def test_vector_worktree_file_with_absolute_commondir(self) -> None:
        common = self.tmp / "elsewhere.git"
        wt_gitdir = common / "worktrees" / "wt"
        wt_gitdir.mkdir(parents=True)
        (wt_gitdir / "commondir").write_text(f"{common}\n")
        wt = self.tmp / "wt"
        wt.mkdir()
        (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
        self.assertEqual(cs.git_common_dir(wt), common)

    def test_vector_gitdir_file_without_commondir_is_its_own_common_dir(self) -> None:
        module = self.tmp / "super" / ".git" / "modules" / "sub"
        module.mkdir(parents=True)
        sub = self.tmp / "super" / "sub"
        sub.mkdir()
        (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
        self.assertEqual(cs.git_common_dir(sub), module)

    def test_vector_not_a_repository(self) -> None:
        self.assertIsNone(cs.git_common_dir(self.tmp))

    def test_vector_malformed_dot_git_file(self) -> None:
        (self.tmp / ".git").write_text("not a gitdir line\n")
        self.assertIsNone(cs.git_common_dir(self.tmp))

    def test_vector_dangling_gitdir(self) -> None:
        (self.tmp / ".git").write_text(f"gitdir: {self.tmp / 'gone'}\n")
        self.assertIsNone(cs.git_common_dir(self.tmp))


class PersonalLayerStatus(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / ".git").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_unadopted_repo_reports_the_git_dir_home(self) -> None:
        status = cs.personal_layer_status(self.tmp)
        self.assertEqual(status["location"], "git-dir")
        self.assertEqual(status["path"], str(self.tmp / ".git" / "apache-magpie"))
        self.assertFalse(status["present"])
        self.assertFalse(status["legacy_in_tree"])
        self.assertFalse((self.tmp / ".git" / "apache-magpie").exists())

    def test_unadopted_repo_flags_a_legacy_in_tree_dir(self) -> None:
        (self.tmp / ".apache-magpie-local").mkdir()
        self.assertTrue(cs.personal_layer_status(self.tmp)["legacy_in_tree"])

    def test_adopted_repo_reports_the_in_tree_dir(self) -> None:
        (self.tmp / ".apache-magpie.lock").write_text("method: local\n")
        (self.tmp / ".apache-magpie-local").mkdir()
        (self.tmp / ".apache-magpie-local" / "x.md").write_text("x")
        status = cs.personal_layer_status(self.tmp)
        self.assertEqual(status["location"], "in-tree")
        self.assertTrue(status["present"])
        self.assertEqual(status["skill_count"], 1)
        self.assertFalse(status["legacy_in_tree"])

    def test_gitignore_check_applies_only_to_an_adopted_repo(self) -> None:
        self.assertIsNone(cs.gitignore_coverage(self.tmp, [])["local_overrides_ignored"])
        (self.tmp / ".apache-magpie.lock").write_text("method: local\n")
        self.assertFalse(cs.gitignore_coverage(self.tmp, [])["local_overrides_ignored"])
        (self.tmp / ".gitignore").write_text("/.apache-magpie-local/\n")
        self.assertTrue(cs.gitignore_coverage(self.tmp, [])["local_overrides_ignored"])

    def test_not_a_git_repo_has_no_personal_layer(self) -> None:
        (self.tmp / ".git").rmdir()
        status = cs.personal_layer_status(self.tmp)
        self.assertEqual(status["location"], "none")
        self.assertIsNone(status["path"])


if __name__ == "__main__":
    unittest.main()
