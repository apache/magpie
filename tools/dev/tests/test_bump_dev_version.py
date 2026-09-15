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

"""Tests for ``bump-dev-version.py``.

The failure this guards is silent: a bump that does not actually move the
string leaves every adopter's ``claude plugin update`` answering "already at
the latest version" while they sit behind ``main``. So the tests care about the
version string being *different* and *well-formed*, and about the two cases
where guessing would be worse than stopping — a released version with no dev
suffix, and a malformed stamp.

The script's filename is hyphenated, which is not an importable module name, so
it is loaded through ``importlib.util``.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "bump-dev-version.py"

PYPROJECT = """\
[project]
name = "apache-magpie"
version = "0.2.0.dev202609141352"
requires-python = ">=3.11"

[tool.uv]
# A pin that must not be mistaken for the project version.
constraint-dependencies = ["ruff>=0.16.2"]
"""


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bump_dev_version", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


# --- reading ------------------------------------------------------------------


def test_reads_the_project_version() -> None:
    assert mod.read_version(PYPROJECT) == "0.2.0.dev202609141352"


def test_a_file_without_a_version_is_refused() -> None:
    with pytest.raises(mod.BumpError):
        mod.read_version("[project]\nname = 'x'\n")


# --- stamping -----------------------------------------------------------------


def test_the_stamp_replaces_the_previous_one() -> None:
    assert mod.next_version("0.2.0.dev202609141352", "202609151058") == "0.2.0.dev202609151058"


def test_a_release_version_is_refused_rather_than_guessed() -> None:
    """Stamping 0.2.0 would advertise a dev build of a version already released."""
    with pytest.raises(mod.BumpError, match="release"):
        mod.next_version("0.2.0", "202609151058")


@pytest.mark.parametrize("bad", ["2026-09-15", "20260915", "20260915105812", "", "abcdefghijkl"])
def test_a_malformed_stamp_is_refused(bad: str) -> None:
    with pytest.raises(mod.BumpError):
        mod.next_version("0.2.0.dev202609141352", bad)


def test_the_stamp_is_utc_not_local() -> None:
    """A local-time stamp sorts wrong against a bump made in another timezone."""
    moment = dt.datetime(2026, 9, 15, 10, 58, tzinfo=dt.UTC)
    assert mod.utc_stamp(moment) == "202609151058"


# --- rewriting ----------------------------------------------------------------


def test_only_the_version_line_changes() -> None:
    updated = mod.replace_version(PYPROJECT, "0.2.0.dev202609141352", "0.2.0.dev202609151058")
    assert 'version = "0.2.0.dev202609151058"' in updated
    # The dependency pin below it is untouched.
    assert 'constraint-dependencies = ["ruff>=0.16.2"]' in updated
    assert updated.count("version = ") == 1


def test_end_to_end_rewrites_the_file(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(PYPROJECT, encoding="utf-8")
    assert mod.main(["--pyproject", str(path), "--stamp", "202609151058"]) == 0
    assert 'version = "0.2.0.dev202609151058"' in path.read_text(encoding="utf-8")


def test_bumping_to_the_same_stamp_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(PYPROJECT, encoding="utf-8")
    assert mod.main(["--pyproject", str(path), "--stamp", "202609141352"]) == 0
    assert path.read_text(encoding="utf-8") == PYPROJECT
