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

"""Tests for ``estimate-skill-tokens.py``.

The point is the definition: a skill's always-on cost is ``name`` +
``description`` + ``when_to_use`` (see ``docs/mode-economics.md``), so a
change to any of the three moves the figure and a change to the body does not.

The script's filename is hyphenated, so it is loaded through ``importlib.util``.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "estimate-skill-tokens.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("estimate_skill_tokens", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    """A miniature repo, cd'd into — the script resolves paths relative to cwd."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "docs" / "setup").mkdir(parents=True)
    prev = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(prev)


def _skill(repo: Path, name: str, *, description: str, when_to_use: str = "", body: str = "") -> None:
    d = repo / "skills" / name
    d.mkdir()
    wtu = f"when_to_use: >-\n  {when_to_use}\n" if when_to_use else ""
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n{wtu}family: demo\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_when_to_use_counts_toward_always_on(repo: Path) -> None:
    """The listing line is `name: description - when_to_use`."""
    fm = "name: abcd\ndescription: " + "d" * 40 + "\nwhen_to_use: >-\n  " + "w" * 30
    assert mod.always_on_chars(fm) == 4 + 2 + 40 + 3 + 30


def test_missing_when_to_use_adds_no_separator(repo: Path) -> None:
    assert mod.always_on_chars("name: abcd\ndescription: " + "d" * 40) == 4 + 2 + 40


def test_measure_sums_per_family_and_ignores_the_body(repo: Path) -> None:
    _skill(repo, "aaaa", description="d" * 40, when_to_use="w" * 30, body="x" * 10_000)
    _skill(repo, "bbbb", description="d" * 40)
    count, tokens = mod.measure()["demo"]
    assert count == 2
    assert tokens == ((4 + 2 + 40 + 3 + 30) + (4 + 2 + 40)) / mod.CHARS_PER_TOKEN


def test_check_flags_a_table_that_left_out_when_to_use(repo: Path) -> None:
    """A table published with name + description only must fail the check."""
    _skill(repo, "aaaa", description="d" * 400, when_to_use="w" * 2000)
    marketplace = repo / "docs" / "setup" / "marketplace.md"
    marketplace.write_text("| `magpie-demo` | 1 | ~0.1k |\n", encoding="utf-8")
    errors: list[str] = []
    mod.check(errors)
    assert len(errors) == 1 and "measured ~0.6k" in errors[0]

    marketplace.write_text("| `magpie-demo` | 1 | ~0.6k |\n", encoding="utf-8")
    errors = []
    mod.check(errors)
    assert errors == []
