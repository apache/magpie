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
"""Tests for ``generate-labeler-config.py``."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[1] / "generate-labeler-config.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_labeler_config", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def _tool(root: Path, name: str, capability: str) -> None:
    d = root / "tools" / name
    d.mkdir(parents=True)
    (d / "README.md").write_text(f"# {name}\n\n**Capability:** {capability}\n\nProse.\n", encoding="utf-8")


def test_multi_capability_tool_lands_under_every_label(tmp_path: Path) -> None:
    _tool(tmp_path, "github", "contract:tracker + contract:change-request")
    _tool(tmp_path, "jira", "contract:tracker")
    assert mod.load_capabilities(tmp_path) == {
        "contract:change-request": ["github"],
        "contract:tracker": ["github", "jira"],
    }


def test_backticks_and_readmes_without_capability_are_handled(tmp_path: Path) -> None:
    _tool(tmp_path, "guard", "`substrate:action-guard`")
    (tmp_path / "tools" / "notes").mkdir(parents=True)
    (tmp_path / "tools" / "notes" / "README.md").write_text("# notes\n", encoding="utf-8")
    assert mod.load_capabilities(tmp_path) == {"substrate:action-guard": ["guard"]}


def test_excluded_paths_render_as_negated_globs(tmp_path: Path) -> None:
    _tool(tmp_path, "dev", "substrate:framework-dev")
    _tool(tmp_path, "skill-evals", "substrate:framework-dev")
    out = mod.render(mod.load_capabilities(tmp_path))
    assert "- 'tools/dev/**'" in out
    assert "- all-globs-to-any-file:\n              - 'tools/skill-evals/**'\n" in out
    assert "- '!tools/skill-evals/evals/**'" in out
    assert out.count("changed-files:") == 2  # plain tools and the excluded tool are OR-ed


def test_main_rewrites_then_reports_in_sync(tmp_path: Path) -> None:
    _tool(tmp_path, "osv", "contract:security-cross-ref")
    (tmp_path / ".github").mkdir()
    assert mod.main(["--root", str(tmp_path)]) == 1  # written
    assert mod.main(["--root", str(tmp_path)]) == 0  # now in sync
    _tool(tmp_path, "nvd", "contract:security-cross-ref")
    assert mod.main(["--root", str(tmp_path), "--check"]) == 1  # drift, not written
    assert "tools/nvd/**" not in (tmp_path / ".github" / "labeler.yml").read_text(encoding="utf-8")


def test_committed_config_is_in_sync() -> None:
    assert mod.main(["--check"]) == 0
