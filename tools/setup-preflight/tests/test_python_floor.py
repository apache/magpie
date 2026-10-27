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
