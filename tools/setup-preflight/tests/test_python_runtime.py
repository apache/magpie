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
"""`python-missing`: uv has no Python the framework's tools require."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from setup_preflight import python_runtime, sections
from setup_preflight.python_runtime import REQUIRED_PYTHON, findings

REPO_ROOT = Path(__file__).resolve().parents[3]


def _runner(returncode: int, calls: list[list[str]] | None = None) -> Any:
    def run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if calls is not None:
            calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, "", "")

    return run


def test_no_finding_when_uv_finds_the_interpreter() -> None:
    calls: list[list[str]] = []
    assert findings(which=lambda _: "/usr/bin/uv", run=_runner(0, calls)) == []
    assert calls == [["/usr/bin/uv", "python", "find", "--no-project", REQUIRED_PYTHON]]


def test_a_missing_interpreter_is_reported_with_its_version() -> None:
    (found,) = findings(which=lambda _: "/usr/bin/uv", run=_runner(2))
    assert (found.scope, found.code, found.section) == ("machine", "python-missing", "python-missing")
    assert found.facts == {"version": REQUIRED_PYTHON}


def test_no_uv_means_nothing_to_ask() -> None:
    assert findings(which=lambda _: None, run=_runner(2)) == []


def test_a_failing_uv_is_not_a_finding() -> None:
    def broken(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("uv", 15)

    assert findings(which=lambda _: "/usr/bin/uv", run=broken) == []


def test_the_required_version_is_the_workspace_interpreter() -> None:
    # The tools run on the workspace's pinned interpreter; the check must ask
    # for the same one, or it passes while every tool fails.
    assert (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip() == REQUIRED_PYTHON


def test_the_finding_has_its_rules() -> None:
    assert "python-missing" in sections.available()
    text = sections.load("python-missing")
    assert "uv python install <facts.version>" in text
    assert python_runtime.__doc__ is not None
