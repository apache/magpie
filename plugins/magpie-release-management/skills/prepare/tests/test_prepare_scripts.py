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

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import category_x
import next_dev_version
import prev_tag

LS_REMOTE = """\
aaa\trefs/tags/2.10.2
bbb\trefs/tags/2.10.3
ccc\trefs/tags/2.10.3^{}
ddd\trefs/tags/2.11.0rc1
eee\trefs/tags/1.10.15
fff\trefs/tags/providers-amazon/9.0.0
ggg\trefs/tags/3.0.0
"""


class PrevTagTest(unittest.TestCase):
    def find(self, version: str, train: str | None = None, prefix: str = "", text: str = LS_REMOTE) -> dict:
        return prev_tag.find_previous(prev_tag.tag_names(text), version, train, prefix)

    def test_latest_final_below_version_in_same_major(self) -> None:
        out = self.find("2.11.0")
        self.assertEqual(out["previous_tag"], "2.10.3")
        self.assertEqual(out["skipped_prerelease_tags"], ["2.11.0rc1"])

    def test_numeric_ordering(self) -> None:
        out = self.find("2.11.0", text="2.9.0\n2.10.0\n")
        self.assertEqual(out["previous_tag"], "2.10.0")

    def test_narrow_train(self) -> None:
        self.assertEqual(self.find("2.10.4", train="2.10.x")["previous_tag"], "2.10.3")
        self.assertIsNone(self.find("2.12.0", train="2.12.x")["previous_tag"])

    def test_v_prefix_and_namespace(self) -> None:
        self.assertEqual(self.find("1.1.0", text="v1.0.0\nv1.0.1\n")["previous_tag"], "v1.0.1")
        out = self.find("9.1.0", prefix="providers-amazon/")
        self.assertEqual(out["previous_tag"], "providers-amazon/9.0.0")

    def test_first_release_has_none(self) -> None:
        self.assertIsNone(self.find("1.0.0", text="")["previous_tag"])

    def test_bad_train_rejected(self) -> None:
        with self.assertRaises(prev_tag.InputError):
            self.find("2.11.0", train="two")


class CategoryXTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def file(self, text: str) -> str:
        path = Path(self.tmp.name) / "setup.cfg"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_artifact_of_maven_coordinate_matches(self) -> None:
        local = self.file("[options]\ninstall_requires =\n    cc-by-nc-widget>=1.2.0\n")
        out = category_x.scan(["com.example:gpl-licensed-lib", "org.acme:cc-by-nc-widget"], [("setup.cfg", local)])
        self.assertTrue(out["category_x_hit"])
        self.assertEqual(out["category_x_violations"], [{"identifier": "org.acme:cc-by-nc-widget", "found_in": "setup.cfg"}])
        self.assertEqual(out["first_match_lines"][0]["line"], 3)
        self.assertEqual(out["handoff_reason"], category_x.HANDOFF)

    def test_separator_and_case_normalisation(self) -> None:
        local = self.file('dependencies = ["Bad_Lib==1.0"]\n')
        self.assertTrue(category_x.scan(["bad-lib"], [("pyproject.toml", local)])["category_x_hit"])

    def test_no_partial_token_match(self) -> None:
        local = self.file('dependencies = ["bad-lib-extras", "notbad-lib"]\n')
        out = category_x.scan(["bad-lib"], [("pyproject.toml", local)])
        self.assertFalse(out["category_x_hit"])
        self.assertEqual(out["files_scanned"], ["pyproject.toml"])


class NextDevVersionTest(unittest.TestCase):
    CONFIGURED = ["setup.cfg", "airflow/__init__.py", "pyproject.toml", "pom.xml", "Cargo.toml", "VERSION"]

    def test_formats(self) -> None:
        out = next_dev_version.next_versions("2.11.0", self.CONFIGURED)
        got = {f["file"]: (f["format"], f["next_dev_version"]) for f in out["files"]}
        self.assertEqual(got["setup.cfg"], ("python", "2.12.0.dev0"))
        self.assertEqual(got["airflow/__init__.py"], ("python", "2.12.0.dev0"))
        self.assertEqual(got["pom.xml"], ("maven", "2.12.0-SNAPSHOT"))
        self.assertEqual(got["Cargo.toml"], ("cargo", None))
        self.assertEqual(got["VERSION"], ("unknown", None))
        self.assertEqual(out["not_configured"], [])
        self.assertTrue(out["needs_rm_confirmation"])

    def test_unconfigured_py_file_is_not_python(self) -> None:
        out = next_dev_version.next_versions(
            "2.11.0", ["setup.cfg", "airflow/__init__.py"], ["setup.cfg", "airflow/version.py"]
        )
        stray = out["files"][1]
        self.assertEqual((stray["configured"], stray["format"], stray["next_dev_version"]), (False, "unknown", None))
        self.assertTrue(stray["needs_rm_confirmation"])
        self.assertEqual(out["not_configured"], ["airflow/version.py"])
        self.assertTrue(out["needs_rm_confirmation"])

    def test_configured_py_file_is_python(self) -> None:
        out = next_dev_version.next_versions("2.11.0", ["./airflow/__init__.py"], ["airflow/__init__.py"])
        self.assertEqual(out["files"][0]["format"], "python")
        self.assertFalse(out["needs_rm_confirmation"])

    def test_patch_release_still_bumps_minor(self) -> None:
        out = next_dev_version.next_versions("2.10.3", ["setup.cfg"])
        self.assertEqual(out["files"][0]["next_dev_version"], "2.11.0.dev0")
        self.assertFalse(out["needs_rm_confirmation"])

    def test_bad_version(self) -> None:
        with self.assertRaises(ValueError):
            next_dev_version.next_versions("main", ["setup.cfg"])

    def test_config_table_row(self) -> None:
        text = "| Key | Value |\n|---|---|\n| `version_manifest_files` | `setup.cfg`, `foo/__init__.py` |\n"
        self.assertEqual(next_dev_version.configured_files(text), ["setup.cfg", "foo/__init__.py"])

    def test_config_key_line(self) -> None:
        text = "version_manifest_files: setup.cfg, airflow/__init__.py\n"
        self.assertEqual(next_dev_version.configured_files(text), ["setup.cfg", "airflow/__init__.py"])

    def test_config_without_key_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            next_dev_version.configured_files("| `release_branch_base` | `main` |\n")


if __name__ == "__main__":
    unittest.main()
