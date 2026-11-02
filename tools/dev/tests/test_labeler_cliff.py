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
"""Tests for ``labeler-cliff.py``."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "labeler-cliff.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("labeler_cliff", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.mark.parametrize(
    ("glob", "path", "expected"),
    [
        ("tools/**", "tools/osv/README.md", True),
        ("tools/**", "toolsx/a", False),
        ("*.md", "README.md", True),
        ("*.md", "docs/a.md", False),
        ("**/README.md", "README.md", True),
        ("**/README.md", "tools/osv/README.md", True),
        (".asf.yaml", ".asf.yaml", True),
        ("tools/spec-loop/specs/**", "tools/spec-loop/specs/a.md", True),
    ],
)
def test_glob_match_follows_minimatch(glob: str, path: str, expected: bool) -> None:
    assert mod.glob_match(glob, path) is expected


def test_excluded_tree_needs_a_file_outside_the_exclusion() -> None:
    rules = {"family:tools": ["plugins/magpie-agent-guard/**", "tools/**", "!tools/spec-loop/specs/**"]}
    assert mod.matched_labels(rules, {}, {}, ["tools/spec-loop/specs/a.md"]) == set()
    assert mod.matched_labels(rules, {}, {}, ["tools/osv/osv.py"]) == {"family:tools"}
    assert mod.matched_labels(rules, {}, {}, ["plugins/magpie-agent-guard/x"]) == {"family:tools"}


def test_tool_excludes_do_not_count_as_touching_the_tool() -> None:
    caps = {"substrate:framework-dev": ["spec-loop"]}
    excludes = {"spec-loop": ("specs/**", ".last-sync")}
    assert mod.matched_labels({}, caps, excludes, ["tools/spec-loop/.last-sync"]) == set()
    assert mod.matched_labels({}, caps, excludes, ["tools/spec-loop/loop.sh"]) == {"substrate:framework-dev"}


def _run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], files: list[str], *args: str
) -> str:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(files) + "\n"))
    assert mod.main(list(args)) == 0
    return capsys.readouterr().out.strip()


def test_dev_only_change_is_under_the_limit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, capsys, [".asf.yaml"]) == ""
    assert _run(monkeypatch, capsys, [".asf.yaml"], "--count") == "1"


def test_sweep_across_every_tool_is_cross_family(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = mod._generator().REPO_ROOT
    sweep = sorted(p.relative_to(root).as_posix() for p in (root / "tools").glob("*/README.md"))
    assert _run(monkeypatch, capsys, sweep) == "family:cross-family"
    # Labels the pull request already has do not count as new.
    assert _run(monkeypatch, capsys, sweep, "--labels", "family:cross-family") == ""
