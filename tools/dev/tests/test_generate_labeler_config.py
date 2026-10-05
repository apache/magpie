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


_TAXONOMY = """
| `family:release-management` | opt-in | release skills |
| `family:tools` | Substrate tools |
| `family:ci` | workflows |
| `family:docs` | docs |
| `capability:resolve` | Resolve. |
| `capability:triage` | Triage. |
"""


def _skill(root: Path, plugin: str, name: str, link: str, frontmatter: str) -> None:
    d = root / "plugins" / plugin / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n{frontmatter}---\n# {name}\n", encoding="utf-8")
    (root / "skills").mkdir(exist_ok=True)
    (root / "skills" / link).symlink_to(Path("..") / "plugins" / plugin / "skills" / name)
    (root / "tools" / "skill-evals" / "evals" / link).mkdir(parents=True, exist_ok=True)


def _taxonomy(root: Path) -> None:
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "labels-and-capabilities.md").write_text(_TAXONOMY, encoding="utf-8")


def test_skill_family_and_capabilities_cover_skill_and_eval_suite(tmp_path: Path) -> None:
    _taxonomy(tmp_path)
    _skill(
        tmp_path,
        "magpie-release-management",
        "rc-cut",
        "release-rc-cut",
        "family: release-management\ncapability:\n  - capability:resolve\n  - capability:triage\n",
    )
    rules = mod.load_path_rules(tmp_path)
    skill = "plugins/magpie-release-management/skills/rc-cut/**"
    suite = "tools/skill-evals/evals/release-rc-cut/**"
    assert rules["capability:resolve"] == [skill, suite]
    assert rules["capability:triage"] == [skill, suite]
    # the plugin-wide glob already covers the skill directory, so it is pruned
    assert rules["family:release-management"] == ["plugins/magpie-release-management/**", suite]


def test_unknown_labels_are_never_emitted(tmp_path: Path) -> None:
    _taxonomy(tmp_path)
    _skill(
        tmp_path,
        "magpie-release-management",
        "rc-cut",
        "release-rc-cut",
        "family: releases\ncapability: capability:resolving\n",
    )
    rules = mod.load_path_rules(tmp_path)
    assert "family:releases" not in rules and "capability:resolving" not in rules


def test_tool_only_plugin_and_tools_tree_are_family_tools_without_evals(tmp_path: Path) -> None:
    _taxonomy(tmp_path)
    (tmp_path / "plugins" / "magpie-agent-guard" / "tools").mkdir(parents=True)
    _tool(tmp_path, "osv", "contract:security-cross-ref")
    out = mod.render(mod.load_capabilities(tmp_path), mod.load_path_rules(tmp_path))
    block = out.split("family:tools:\n", 1)[1].split("\n\n", 1)[0]
    assert "'plugins/magpie-agent-guard/**'" in block
    assert (
        "- all-globs-to-any-file:\n              - 'tools/**'\n              - '!tools/skill-evals/evals/**'"
        in block
    )


def test_limit_is_not_a_low_cliff() -> None:
    # actions/labeler drops every changed-files label when more than the limit match
    assert mod.LABELS_LIMIT >= 20
