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


def _block_pythonpath(cwd: Path, home: Path) -> str:
    """What the shared block's PYTHONPATH expands to when run in `cwd`, with no git on PATH."""
    line = next(ln for ln in BLOCK.read_text(encoding="utf-8").splitlines() if ln.startswith("PYTHONPATH="))
    assignment = line.rstrip(" \\")
    # Only the directory of this interpreter, which the block needs to pick its directory.
    bin_dir = Path(sys.executable).parent
    assert (bin_dir / "python3").exists()
    done = subprocess.run(
        ["/bin/sh", "-c", f'{assignment}; printf %s "$PYTHONPATH"'],
        cwd=cwd,
        env={"PATH": str(bin_dir), "HOME": str(home)},
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def test_a_planted_vcs_dir_is_never_on_the_path(tmp_path: Path) -> None:
    """An archive or a Subversion checkout can carry `.svn/` (`wc.db` included) or `.git/`; neither counts."""
    home = tmp_path / "home"
    project = tmp_path / "project"
    expected = str(home / ".cache" / "apache-magpie" / "preflight")
    (project / ".svn" / "apache-magpie" / "setup_preflight").mkdir(parents=True)
    (project / ".git" / "apache-magpie" / "setup_preflight").mkdir(parents=True)
    assert _block_pythonpath(project, home) == expected
    (project / ".svn" / "wc.db").write_bytes(b"")
    (project / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    assert _block_pythonpath(project, home) == expected
