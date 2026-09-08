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

"""Tests for the test-coverage half of ``check-workspace-members.py``.

The failure this guards is quiet by construction: the CI pytest matrix and the
workspace sweep are both driven by the presence of ``[tool.pytest.ini_options]``,
so a project can carry a full ``tests/`` directory and never be executed by
anything. There is no red tick to notice — the job is simply never emitted.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "check-workspace-members.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_workspace_members", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def _member(root: Path, name: str, *, ini: bool, tests: bool, skip: bool = False) -> Path:
    d = root / name
    d.mkdir(parents=True)
    body = '[project]\nname = "x"\nversion = "0.1.0"\n'
    if ini:
        body += '\n[tool.pytest.ini_options]\nminversion = "8.0"\n'
    if skip:
        body += '\n[tool.magpie.checks]\nskip = ["pytest"]\n'
    (d / "pyproject.toml").write_text(body, encoding="utf-8")
    if tests:
        (d / "tests").mkdir()
        (d / "tests" / "test_thing.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return d


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    return tmp_path


def test_tests_and_config_present_is_silent(root: Path) -> None:
    m = _member(root, "good", ini=True, tests=True)
    assert mod.check_tests_run([m]) == []


def test_tests_without_config_are_reported(root: Path) -> None:
    """The quiet failure: real tests that nothing ever executes."""
    m = _member(root, "orphaned", ini=False, tests=True)
    problems = mod.check_tests_run([m])
    assert len(problems) == 1
    assert "never run" in problems[0]


def test_config_without_tests_is_reported(root: Path) -> None:
    """The inverse: a green CI job that collected nothing."""
    m = _member(root, "hollow", ini=True, tests=False)
    problems = mod.check_tests_run([m])
    assert len(problems) == 1
    assert "collects nothing" in problems[0]


def test_neither_is_reported(root: Path) -> None:
    m = _member(root, "untested", ini=False, tests=False)
    problems = mod.check_tests_run([m])
    assert len(problems) == 1
    assert "has no tests" in problems[0]


def test_declared_opt_out_is_honoured(root: Path) -> None:
    """A project that genuinely should not be tested says so, rather than
    being silently absent from the matrix."""
    m = _member(root, "config-carrier", ini=False, tests=False, skip=True)
    assert mod.check_tests_run([m]) == []


def test_opt_out_also_silences_the_other_two_shapes(root: Path) -> None:
    assert mod.check_tests_run([_member(root, "a", ini=False, tests=True, skip=True)]) == []
    assert mod.check_tests_run([_member(root, "b", ini=True, tests=False, skip=True)]) == []


def test_alternative_test_naming_is_discovered(root: Path) -> None:
    m = _member(root, "suffixed", ini=True, tests=False)
    (m / "tests").mkdir()
    (m / "tests" / "thing_test.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    assert mod.check_tests_run([m]) == []


def test_vendored_tests_do_not_count_as_the_members_own(root: Path) -> None:
    """A test file inside an installed package or a virtualenv would otherwise
    make an untested member look tested — the exact false negative that makes
    this check worthless."""
    m = _member(root, "vendored", ini=True, tests=False)
    vendored = m / ".venv" / "lib" / "python3.11" / "site-packages" / "dep" / "tests"
    vendored.mkdir(parents=True)
    (vendored / "test_dep.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    problems = mod.check_tests_run([m])
    assert len(problems) == 1
    assert "collects nothing" in problems[0]


def test_every_member_is_reported_not_just_the_first(root: Path) -> None:
    members = [
        _member(root, "one", ini=False, tests=True),
        _member(root, "two", ini=True, tests=False),
        _member(root, "three", ini=False, tests=False),
    ]
    assert len(mod.check_tests_run(members)) == 3
