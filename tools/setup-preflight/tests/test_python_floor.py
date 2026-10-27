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

"""The checker runs on Python 3.11+ only, and says so on anything older."""

from __future__ import annotations

import ast
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import setup_preflight

MAIN = Path(setup_preflight.__file__).with_name("__main__.py")


def test_an_old_python_is_refused_before_the_checker_loads(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 9, 6, "final", 0))
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("setup_preflight", run_name="__main__")
    assert excinfo.value.code == 3
    assert "needs Python 3.11 or later; this is 3.9" in capsys.readouterr().err


def test_the_entry_point_parses_on_an_old_grammar() -> None:
    """An old `python3` must reach the refusal, not stop on a SyntaxError."""
    ast.parse(MAIN.read_text(encoding="utf-8"), feature_version=(3, 6))


BLOCK = Path(__file__).resolve().parents[2] / "dev" / "preflight-block.md"


def _block_pythonpath(cwd: Path) -> str:
    """What the shared block's PYTHONPATH expands to when run in `cwd`, with no git on PATH."""
    line = next(ln for ln in BLOCK.read_text(encoding="utf-8").splitlines() if ln.startswith("PYTHONPATH="))
    assignment = line.rstrip(" \\")
    done = subprocess.run(
        ["/bin/sh", "-c", f'{assignment}; printf %s "$PYTHONPATH"'],
        cwd=cwd,
        env={"PATH": "/nonexistent"},
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def test_a_planted_svn_dir_without_a_working_copy_is_not_on_the_path(tmp_path: Path) -> None:
    """An archive can carry `.svn/apache-magpie/`; only a real working copy (`wc.db`) counts."""
    (tmp_path / ".svn" / "apache-magpie" / "setup_preflight").mkdir(parents=True)
    assert _block_pythonpath(tmp_path) == "/apache-magpie"
    (tmp_path / ".svn" / "wc.db").write_bytes(b"")
    assert _block_pythonpath(tmp_path) == ".svn/apache-magpie"
