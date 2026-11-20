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

"""Tests for the packaged-tool probe's discovery and command shape."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "start-packaged-tools.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("start_packaged_tools", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def _tool(root: Path, rel: str, text: str) -> None:
    path = root / "plugins" / "magpie-x" / "tools" / rel / "pyproject.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discover_follows_a_symlinked_tool(tmp_path: Path) -> None:
    _tool(tmp_path, "a", '[project]\nname = "a"\n')
    real = tmp_path / "real-b"
    real.mkdir()
    (real / "pyproject.toml").write_text('[project]\nname = "b"\n', encoding="utf-8")
    link = tmp_path / "plugins" / "magpie-x" / "tools" / "b"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    assert [tool.path.as_posix() for tool in mod.discover(tmp_path)] == ["tools/a", "tools/b"]


def test_discover_reads_scripts_and_nested_tools(tmp_path: Path) -> None:
    _tool(tmp_path, "a", '[project]\nname = "a"\n\n[project.scripts]\na = "a:main"\n')
    _tool(
        tmp_path,
        "b/c",
        '[project]\nname = "b"\n\n[tool.hatch.build.targets.wheel]\npackages = ["src/b"]\n',
    )
    assert [
        (tool.plugin, tool.path.as_posix(), tool.scripts, tool.modules) for tool in mod.discover(tmp_path)
    ] == [
        ("magpie-x", "tools/a", ("a",), ("a",)),
        ("magpie-x", "tools/b/c", (), ("b",)),
    ]


def test_modules_fall_back_to_the_project_name() -> None:
    assert mod.modules_of({"project": {"name": "security-tracker-stats-dashboard"}}) == (
        "security_tracker_stats_dashboard",
    )


def test_probes_ask_a_script_for_help(tmp_path: Path) -> None:
    tool = mod.PackagedTool("magpie-x", Path("tools/a"), ("a",), ())
    ((label, command),) = mod.probes(tool, tmp_path)
    assert label == "a --help"
    assert command[-2:] == ["a", "--help"]


def test_probes_import_a_library_without_scripts(tmp_path: Path) -> None:
    tool = mod.PackagedTool("magpie-x", Path("tools/b"), (), ("b",))
    ((label, command),) = mod.probes(tool, tmp_path)
    assert label == "import b"
    assert command[-2:] == ["-c", "import b"]
