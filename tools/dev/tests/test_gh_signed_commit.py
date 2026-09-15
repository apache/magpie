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

"""Tests for ``gh-signed-commit.py``.

The three pure pieces are what can go wrong silently in CI: a message split the
wrong way produces a commit whose body is in its subject, a mis-parsed
``git status`` drops a file from the commit without failing, and a payload
missing ``expectedHeadOid`` overwrites a concurrent push. Each is exercised
here; the mutation call itself is not, because asserting that ``gh`` was
invoked would test the mock rather than the code.

The script's filename is hyphenated, which is not an importable module name, so
it is loaded through ``importlib.util``.
"""

from __future__ import annotations

import base64
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "gh-signed-commit.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gh_signed_commit", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


# --- message splitting --------------------------------------------------------


def test_headline_and_body_split_on_the_blank_line() -> None:
    headline, body = mod.split_message("chore: bump\n\nWhy it moved.\n\nGenerated-by: X\n")
    assert headline == "chore: bump"
    assert body == "Why it moved.\n\nGenerated-by: X"


def test_a_subject_only_message_has_an_empty_body() -> None:
    headline, body = mod.split_message("chore: bump\n")
    assert headline == "chore: bump"
    assert body == ""


def test_an_empty_message_is_refused() -> None:
    with pytest.raises(mod.CommitError):
        mod.split_message("\n  \n")


# --- git status parsing -------------------------------------------------------


def _porcelain(*entries: str) -> str:
    return "\0".join(entries) + "\0"


def test_modified_and_added_paths_are_collected(tmp_path: Path) -> None:
    changed, deleted = mod.collect_changes(tmp_path, _porcelain(" M pyproject.toml", "A  new.json"))
    assert changed == ["new.json", "pyproject.toml"]
    assert deleted == []


def test_deletions_are_reported_separately(tmp_path: Path) -> None:
    changed, deleted = mod.collect_changes(tmp_path, _porcelain(" D gone.json", " M kept.json"))
    assert changed == ["kept.json"]
    assert deleted == ["gone.json"]


def test_a_rename_becomes_a_delete_plus_an_add(tmp_path: Path) -> None:
    """The mutation has no rename; losing the source path would leave both files."""
    changed, deleted = mod.collect_changes(tmp_path, _porcelain("R  after.json", "before.json"))
    assert changed == ["after.json"]
    assert deleted == ["before.json"]


def test_a_rename_without_its_source_is_refused(tmp_path: Path) -> None:
    with pytest.raises(mod.CommitError):
        mod.collect_changes(tmp_path, _porcelain("R  after.json"))


def test_paths_containing_spaces_survive(tmp_path: Path) -> None:
    """`-z` output is not quoted, so a space is just a space."""
    changed, _ = mod.collect_changes(tmp_path, _porcelain(" M docs/a file.md"))
    assert changed == ["docs/a file.md"]


# --- payload ------------------------------------------------------------------


def test_payload_pins_the_expected_head_and_encodes_contents() -> None:
    payload = mod.build_payload(
        repo="apache/magpie",
        branch="chore/bump",
        expected_head_oid="deadbeef",
        headline="chore: bump",
        body="Why.",
        additions=[("pyproject.toml", b'version = "0.2.0"\n')],
        deletions=["old.json"],
    )
    variables = payload["variables"]["input"]
    assert variables["expectedHeadOid"] == "deadbeef"
    assert variables["branch"] == {
        "repositoryNameWithOwner": "apache/magpie",
        "branchName": "chore/bump",
    }
    assert variables["message"] == {"headline": "chore: bump", "body": "Why."}
    addition = variables["fileChanges"]["additions"][0]
    assert addition["path"] == "pyproject.toml"
    assert base64.b64decode(addition["contents"]) == b'version = "0.2.0"\n'
    assert variables["fileChanges"]["deletions"] == [{"path": "old.json"}]


def test_payload_omits_empty_change_kinds() -> None:
    payload = mod.build_payload(
        repo="apache/magpie",
        branch="b",
        expected_head_oid="sha",
        headline="h",
        body="",
        additions=[("a.json", b"{}")],
        deletions=[],
    )
    assert "deletions" not in payload["variables"]["input"]["fileChanges"]


def test_an_empty_changeset_is_refused() -> None:
    """A mutation with no file changes creates an empty commit on the branch."""
    with pytest.raises(mod.CommitError):
        mod.build_payload(
            repo="apache/magpie",
            branch="b",
            expected_head_oid="sha",
            headline="h",
            body="",
            additions=[],
            deletions=[],
        )
