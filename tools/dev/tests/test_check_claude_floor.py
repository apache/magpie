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
"""Tests for ``check-claude-floor.py``.

A fake replaces npm and ``claude``, so nothing here touches the network.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "check-claude-floor.py"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_claude_floor", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


class FakeRun:
    """Stand-in for ``subprocess.run`` that records each command and answers like the CLI."""

    def __init__(self, version: str = "2.1.202", failing: tuple[str, ...] = ()) -> None:
        self.version_output = f"{version} (Claude Code)\n"
        self.failing = failing
        self.calls: list[list[str]] = []

    def __call__(self, args: list[Any], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv = [str(arg) for arg in args]
        self.calls.append(argv)
        if argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout=self.version_output, stderr="")
        if argv[1:3] == ["plugin", "validate"]:
            return subprocess.CompletedProcess(argv, 1 if argv[3] in self.failing else 0)
        if argv[:2] == ["npm", "install"]:
            prefix = Path(argv[argv.index("--prefix") + 1])
            package = prefix / "node_modules" / "@anthropic-ai" / "claude-code"
            package.mkdir(parents=True)
            (package / "install.cjs").write_text("// postinstall\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0)


def write_manifest(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def write_marketplace(root: Path, plugins: list[Any], make_dirs: bool = True) -> Path:
    for entry in plugins:
        source = entry.get("source") if isinstance(entry, dict) else None
        if make_dirs and isinstance(source, str) and source.startswith("./"):
            manifest = root / source / ".claude-plugin" / "plugin.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text("{}", encoding="utf-8")
    marketplace = root / ".claude-plugin" / "marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text(json.dumps({"name": "test", "plugins": plugins}), encoding="utf-8")
    return marketplace


# floor_version ------------------------------------------------------------


def test_floor_version_reads_min_version(tmp_path: Path) -> None:
    manifest = write_manifest(
        tmp_path / "pinned.toml",
        '[tools.socat]\nversion = "1.8.1.3"\n\n[tools.claude-code]\nmin_version = "2.1.202"\n',
    )
    assert mod.floor_version(manifest) == "2.1.202"


def test_floor_version_of_the_real_manifest_is_its_min_version() -> None:
    data = tomllib.loads(mod.PINNED_VERSIONS.read_text(encoding="utf-8"))
    assert mod.floor_version() == data["tools"]["claude-code"]["min_version"]


@pytest.mark.parametrize(
    "body",
    [
        '[tools.claude-code]\nversion = "2.1.202"\n',  # a pin, not a floor
        '[tools.claude-code]\nmin_version = "^2.1.202"\n',  # a range
        '[tools.claude-code]\nmin_version = "2.1"\n',
        "[tools.claude-code]\nmin_version = 2\n",
        "not = toml = at all\n",
    ],
)
def test_floor_version_refuses_anything_but_an_exact_release(tmp_path: Path, body: str) -> None:
    with pytest.raises(mod.FloorError):
        mod.floor_version(write_manifest(tmp_path / "pinned.toml", body))


# plugin_dirs --------------------------------------------------------------


def test_plugin_dirs_follow_the_marketplace_order(tmp_path: Path) -> None:
    marketplace = write_marketplace(
        tmp_path,
        [
            {"name": "b", "source": "./plugins/b"},
            {"name": "a", "source": "./plugins/a"},
        ],
    )
    assert mod.plugin_dirs(marketplace) == [Path("plugins/b"), Path("plugins/a")]


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "remote", "source": {"source": "github", "repo": "example/plugin"}},
        {"name": "absolute", "source": "/opt/plugins/x"},
        {"name": "escape", "source": "./plugins/../../x"},
        {"name": "missing"},
    ],
)
def test_plugin_dirs_fail_on_a_source_they_cannot_validate(tmp_path: Path, entry: dict[str, Any]) -> None:
    marketplace = write_marketplace(tmp_path, [{"name": "ok", "source": "./plugins/ok"}, entry])
    with pytest.raises(mod.FloorError, match=repr(entry["name"])):
        mod.plugin_dirs(marketplace)


def test_plugin_dirs_fail_on_a_directory_without_a_plugin_manifest(tmp_path: Path) -> None:
    marketplace = write_marketplace(tmp_path, [{"name": "gone", "source": "./plugins/gone"}], make_dirs=False)
    with pytest.raises(mod.FloorError, match=re.escape("plugin.json")):
        mod.plugin_dirs(marketplace)


def test_plugin_dirs_fail_on_an_empty_marketplace(tmp_path: Path) -> None:
    with pytest.raises(mod.FloorError, match="lists no plugins"):
        mod.plugin_dirs(write_marketplace(tmp_path, []))


def test_the_marketplace_lists_every_plugin_in_the_tree() -> None:
    """A plugin the marketplace leaves out would never be validated at the floor."""
    in_tree = {
        path.relative_to(REPO_ROOT)
        for path in (REPO_ROOT / "plugins").iterdir()
        if (path / ".claude-plugin" / "plugin.json").is_file()
    }
    assert in_tree
    assert set(mod.plugin_dirs()) == in_tree


# install ------------------------------------------------------------------


def test_install_skips_lifecycle_scripts_then_runs_the_postinstall_itself(tmp_path: Path) -> None:
    run = FakeRun()
    claude = mod.install("2.1.202", tmp_path, run=run)

    npm, node = run.calls
    assert npm[:3] == ["npm", "install", "@anthropic-ai/claude-code@2.1.202"]
    assert "--ignore-scripts" in npm
    # Cache and install both stay in the throwaway directory.
    assert npm[npm.index("--cache") + 1] == str(tmp_path / "npm-cache")
    assert npm[npm.index("--prefix") + 1] == str(tmp_path / "claude-code")
    assert node == [
        "node",
        str(tmp_path / "claude-code" / "node_modules" / "@anthropic-ai" / "claude-code" / "install.cjs"),
    ]
    assert claude == tmp_path / "claude-code" / "node_modules" / ".bin" / "claude"


def test_install_fails_loudly_when_the_packaging_changes(tmp_path: Path) -> None:
    def no_postinstall(args: list[Any], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([str(arg) for arg in args], 0)

    with pytest.raises(mod.FloorError, match=re.escape("install.cjs")):
        mod.install("2.1.202", tmp_path, run=no_postinstall)


# check --------------------------------------------------------------------

TARGETS = [Path(".claude-plugin/marketplace.json"), Path("plugins/magpie-a"), Path("plugins/magpie-b")]


def test_check_validates_every_target_with_the_floor_and_without_strict(tmp_path: Path) -> None:
    run = FakeRun()
    claude = tmp_path / "claude"

    assert mod.check(claude, "2.1.202", TARGETS, env={}, run=run, cwd=tmp_path) == 0

    assert run.calls[0] == [str(claude), "--version"]
    assert run.calls[1:] == [[str(claude), "plugin", "validate", str(target)] for target in TARGETS]
    assert not any("--strict" in call or "test" in call for call in run.calls)


def test_check_reports_every_failure_and_fails_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = FakeRun(failing=("plugins/magpie-a",))

    assert mod.check(tmp_path / "claude", "2.1.202", TARGETS, env={}, run=run, cwd=tmp_path) == 1

    validated = [call[3] for call in run.calls if call[1:3] == ["plugin", "validate"]]
    assert validated == [str(target) for target in TARGETS]
    assert capsys.readouterr().out.splitlines() == [f"== {target}" for target in TARGETS]


@pytest.mark.parametrize("reported", ["2.1.328", "2.1.2020"])
def test_check_refuses_a_binary_that_is_not_the_floor(tmp_path: Path, reported: str) -> None:
    run = FakeRun(version=reported)

    assert mod.check(tmp_path / "claude", "2.1.202", TARGETS, env={}, run=run, cwd=tmp_path) == 1
    assert run.calls == [[str(tmp_path / "claude"), "--version"]]


def test_claude_runs_with_a_throwaway_configuration(tmp_path: Path) -> None:
    env = mod.claude_env(tmp_path / "config")
    assert env["CLAUDE_CONFIG_DIR"] == str(tmp_path / "config")
    assert env["DISABLE_AUTOUPDATER"] == "1"
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"


# the hook and the CI step -------------------------------------------------


def hook_block(hook_id: str) -> str:
    """The hook's own keys: the lines indented under its ``- id:`` line."""
    text = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    lines = text.split(f"      - id: {hook_id}\n", 1)[1].splitlines()
    block = []
    for line in lines:
        if not line.startswith("        "):
            break
        block.append(line)
    assert block
    return "\n".join(block)


def test_the_hook_reads_the_floor_instead_of_pinning_a_release() -> None:
    """A release pinned in the hook would not follow the floor."""
    block = hook_block("check-claude-floor")
    assert "additional_dependencies" not in block
    assert "entry: python3 tools/dev/check-claude-floor.py" in block
    assert "stages: [manual]" in block


@pytest.mark.parametrize(
    "path",
    [
        "tools/agent-isolation/pinned-versions.toml",  # raising the floor
        ".claude-plugin/marketplace.json",
        "plugins/magpie-setup/.claude-plugin/plugin.json",
        "plugins/magpie-utilities/hooks/hooks.json",
        "plugins/magpie-issue/skills/triage/SKILL.md",
        "tools/dev/check-claude-floor.py",
        ".pre-commit-config.yaml",
    ],
)
def test_the_hook_fires_on_every_change_that_can_change_its_result(path: str) -> None:
    """CI runs the hook on a pull request's own diff, so the filter decides whether it fires."""
    match = re.search(r"files: (.+)", hook_block("check-claude-floor"))
    assert match is not None
    assert re.search(match.group(1), path)


def test_ci_runs_the_hook() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "pre-commit.yml").read_text(encoding="utf-8")
    assert "prek run check-claude-floor --hook-stage manual" in workflow
