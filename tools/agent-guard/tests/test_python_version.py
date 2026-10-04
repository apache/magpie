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

"""Tests for the re-exec under a 3.11+ interpreter when ``python3`` is older."""

from __future__ import annotations

import os
import shutil
import sys

import pytest

import agent_guard


class _Exec(Exception):
    pass


def _fake_execv(path: str, argv: list[str]) -> None:
    raise _Exec(path, argv)


@pytest.fixture
def old_python(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    environ: dict[str, str] = {}
    monkeypatch.setattr(sys, "version_info", (3, 10, 17))
    monkeypatch.setattr(os, "environ", environ)
    monkeypatch.setattr(os, "execv", _fake_execv)
    return environ


def test_supported_python_is_a_no_op() -> None:
    assert agent_guard._reexec_under_supported_python() is None


def test_reexecs_under_newest_versioned_interpreter(
    old_python: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    available = {"python3.11": "/usr/bin/python3.11", "python3.13": "/usr/bin/python3.13"}
    monkeypatch.setattr(shutil, "which", available.get)
    monkeypatch.setattr(sys, "argv", ["agent-guard", "--gemini"])
    with pytest.raises(_Exec) as exc:
        agent_guard._reexec_under_supported_python()
    path, argv = exc.value.args
    assert path == "/usr/bin/python3.13"
    assert argv == [path, os.path.abspath(agent_guard.__file__), "--gemini"]
    assert old_python[agent_guard._REEXEC_VAR] == "1"


@pytest.mark.parametrize(
    ("environ", "which"),
    [
        pytest.param({}, lambda _: None, id="no-newer-interpreter"),
        pytest.param({agent_guard._REEXEC_VAR: "1"}, lambda _: "/usr/bin/python3.13", id="already-reexeced"),
    ],
)
def test_exits_with_actionable_message(
    old_python: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    environ: dict[str, str],
    which: object,
) -> None:
    old_python.update(environ)
    monkeypatch.setattr(shutil, "which", which)
    with pytest.raises(SystemExit) as exc:
        agent_guard._reexec_under_supported_python()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "needs Python 3.11+" in err
    assert "3.10.17" in err
