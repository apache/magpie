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

"""Shared fixtures: a project tree in whatever setup state a test needs."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from setup_preflight.layers import personal_dir


def pytest_configure(config: pytest.Config) -> None:
    """The checker supports Python 3.11+ only; a run on anything older tests nothing it ships for."""
    # A bare pytest on an older interpreter does not consult requires-python.
    if sys.version_info < (3, 11):  # noqa: UP036
        raise pytest.UsageError(
            f"setup-preflight tests need Python 3.11 or later, not {sys.version.split()[0]} ({sys.executable})"
        )


@pytest.fixture(autouse=True)
def isolated_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A home of its own, so the user's real Claude Code settings never decide a test."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A git repository (a bare `.git/` directory is all the layers read)."""
    (tmp_path / ".git").mkdir()
    return tmp_path


def personal(root: Path) -> Path:
    """This project's personal config layer, which must exist as a location."""
    home = personal_dir(root)
    assert home is not None, "the fixture project is a git repository"
    return home


def write_lock(root: Path, body: str) -> None:
    (root / ".apache-magpie.lock").write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


def write_stamp(root: Path, payload: dict[str, object]) -> None:
    """The stamp, in whichever personal layer this project uses."""
    local = personal(root)
    local.mkdir(parents=True, exist_ok=True)
    (local / "reconciled.json").write_text(json.dumps(payload), encoding="utf-8")
