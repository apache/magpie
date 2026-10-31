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
"""Tests for ``sync-hook-managers.py``.

The committed tree must be in sync, a registry that breaks a contract rule is
refused, and a stale block is rewritten (or reported under ``--check``).

The script's filename is hyphenated, which is not an importable module name, so
it is loaded through ``importlib.util``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "sync-hook-managers.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sync_hook_managers", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture
def registry() -> dict[str, Any]:
    return json.loads((mod.REPO_ROOT / mod.REGISTRY).read_text(encoding="utf-8"))


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A copy of every file the script reads or writes."""
    for rel in (mod.REGISTRY, mod.SHIM, mod.DISPATCHER, mod.SANDBOX_LINT, *mod.SETTINGS):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(mod.REPO_ROOT / rel, tmp_path / rel)
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")  # this repository uses prek
    return tmp_path


def test_the_committed_tree_is_in_sync() -> None:
    assert mod.main(["--check"]) == 0


def test_the_committed_registry_follows_the_contract(registry: dict[str, Any]) -> None:
    assert mod.validate(registry) == []


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("install", "strategy"), "not-a-strategy", "install.strategy"),
        (("install", "subcommand"), "install --now", "install.subcommand"),
        (("install", "runtime_env"), "yes", "install.runtime_env"),
        (("detect", "config_files"), [], "detect.config_files"),
        (("detect", "config_files"), ["sub/prek.toml"], "detect.config_files"),
        (("detect", "nested"), "yes", "detect.nested"),
        (("detect", "hook_marker"), "", "detect.hook_marker"),
        (("install", "flag"), "git-dir", "install.flag"),
        (("home", "sandbox"), "~/.cache/prek", "home.sandbox"),
        (("home", "sandbox"), "~/.cache/prek/sandbox", "home.sandbox"),
        (("home", "sandbox"), "/tmp/prek", "home.sandbox"),
        (("home", "host"), "~/.cache/prek-host", "home.host"),
        (("home", "host"), "~/.local/share/a/b", "home.host"),
        (("home", "expands_tilde"), False, "home.expands_tilde"),
        (("home", "env"), "prek_home", "home.env"),
    ],
)
def test_a_registry_that_breaks_the_contract_is_refused(
    registry: dict[str, Any], path: tuple[str, str], value: object, message: str
) -> None:
    broken = copy.deepcopy(registry)
    broken["adapters"]["prek"][path[0]][path[1]] = value
    assert any(message in e for e in mod.validate(broken)), mod.validate(broken)


def test_overcommit_uses_its_flag_and_runtime_env(registry: dict[str, Any]) -> None:
    adapter = registry["adapters"]["overcommit"]
    assert "home" not in adapter
    assert adapter["install"] == {
        "subcommand": "--install",
        "aliases": ["-i"],
        "strategy": "hooks-path-env",
        "runtime_env": True,
    }
    rendered = mod.render(registry)
    assert (
        "overcommit) install_subcommand=--install; install_strategy=hooks-path-env; "
        "install_aliases='--install -i'" in rendered[mod.SHIM]
    )
    assert 'hook_manager_runtime_envs="overcommit:overcommit"' in rendered[mod.DISPATCHER]


@pytest.mark.parametrize(
    ("aliases", "message"),
    [
        ([], "install.aliases: a non-empty list of flags"),
        ("-i", "install.aliases: a non-empty list of flags"),
        (["install"], "install.aliases: a non-empty list of flags"),
        (["--install"], "install.aliases: must not repeat the subcommand"),
    ],
)
def test_bad_install_aliases_are_refused(registry: dict[str, Any], aliases: object, message: str) -> None:
    broken = copy.deepcopy(registry)
    broken["adapters"]["overcommit"]["install"]["aliases"] = aliases
    assert any(message in e for e in mod.validate(broken)), mod.validate(broken)


def test_aliases_need_a_flag_style_subcommand(registry: dict[str, Any]) -> None:
    broken = copy.deepcopy(registry)
    broken["adapters"]["prek"]["install"]["aliases"] = ["-i"]
    assert any("only a flag-style subcommand takes aliases" in e for e in mod.validate(broken)), mod.validate(
        broken
    )


def test_a_manager_without_a_home_is_allowed(registry: dict[str, Any]) -> None:
    del registry["adapters"]["prek"]["home"]
    assert mod.validate(registry) == []
    assert mod.render(registry)[mod.DISPATCHER] == (
        'hook_manager_homes=""\nhook_manager_runtime_envs="overcommit:overcommit"\n'
    )


def test_strategy_none_adapter_omits_shim_and_needs_no_subcommand(registry: dict[str, Any]) -> None:
    assert mod.validate(registry) == []
    shim = mod.render(registry)[mod.SHIM]
    # Tools with strategy: none must not emit a case in the shim
    for tool in ("cargo-husky", "git-build-hook", "git-code-format-maven-plugin", "simple-git-hooks"):
        assert f"    {tool})" not in shim
    # Prek (git-dir-flag) must still emit a case
    assert (
        "    prek) install_subcommand=install; install_strategy=git-dir-flag; install_flag=--git-dir ;;"
        in shim
    )


def test_strategy_none_with_flag_is_refused(registry: dict[str, Any]) -> None:
    broken = copy.deepcopy(registry)
    broken["adapters"]["simple-git-hooks"]["install"]["flag"] = "--git-dir"
    errors = mod.validate(broken)
    assert any("strategy 'none' takes no flag" in e for e in errors), errors


def test_strategy_none_with_aliases_is_refused(registry: dict[str, Any]) -> None:
    broken = copy.deepcopy(registry)
    broken["adapters"]["simple-git-hooks"]["install"]["aliases"] = ["-i"]
    errors = mod.validate(broken)
    assert any("strategy 'none' takes no aliases" in e for e in errors), errors


def _add_demo(tree: Path, registry: dict[str, Any]) -> None:
    extra = copy.deepcopy(registry["adapters"]["prek"])
    extra["detect"] = {"config_files": ["demo.toml"], "nested": False, "hook_marker": "demo"}
    extra["home"].update(env="DEMO_HOME", default="~/.cache/demo", sandbox="~/.cache/demo-sandbox")
    extra["home"]["host"] = "~/.local/share/demo-host"
    registry["adapters"]["demo"] = extra
    (tree / mod.REGISTRY).write_text(json.dumps(registry), encoding="utf-8")


def test_a_new_adapter_reaches_every_block(tree: Path, registry: dict[str, Any]) -> None:
    _add_demo(tree, registry)
    assert mod.main(["--check", "--root", str(tree)]) == 1
    assert mod.main(["--root", str(tree)]) == 1  # rewrote the blocks; the settings lack the demo deny
    assert "    demo) install_subcommand=install;" in (tree / mod.SHIM).read_text()
    dispatcher = (tree / mod.DISPATCHER).read_text()
    assert 'hook_manager_homes="DEMO_HOME=demo-host PREK_HOME=prek-host"' in dispatcher
    assert 'hook_manager_runtime_envs="overcommit:overcommit"' in dispatcher
    lint = (tree / mod.SANDBOX_LINT).read_text()
    assert (
        '        "DEMO_HOME",\n        "~/.cache/demo",\n        "~/.cache/demo-sandbox",\n        ("demo.toml",),'
        in lint
    )


def _set(tree: Path, env: dict[str, str], deny: list[str]) -> None:
    for rel in mod.SETTINGS:
        settings = json.loads((tree / rel).read_text())
        settings["env"].update(env)
        settings["permissions"]["deny"].extend(deny)
        (tree / rel).write_text(json.dumps(settings), encoding="utf-8")


def test_every_adapter_needs_its_deny_and_a_used_one_its_home(tree: Path, registry: dict[str, Any]) -> None:
    """The default-home deny is per-user; the sandbox home only where the repository uses it."""
    _add_demo(tree, registry)
    mod.main(["--root", str(tree)])
    _set(tree, {}, ["Edit(~/.cache/demo/**)"])
    assert mod.main(["--check", "--root", str(tree)]) == 0  # not used here: the deny is enough
    (tree / "demo.toml").write_text("")
    assert mod.main(["--check", "--root", str(tree)]) == 1
    _set(tree, {"DEMO_HOME": "~/.cache/demo-sandbox"}, [])
    assert mod.main(["--check", "--root", str(tree)]) == 0


def test_a_repository_without_the_manager_needs_no_settings(tree: Path) -> None:
    (tree / ".pre-commit-config.yaml").unlink()
    rel = mod.SETTINGS[0]
    settings = json.loads((tree / rel).read_text())
    del settings["env"]["PREK_HOME"]
    (tree / rel).write_text(json.dumps(settings), encoding="utf-8")
    assert mod.main(["--check", "--root", str(tree)]) == 0


def test_settings_without_the_sandbox_home_fail(tree: Path) -> None:
    rel = mod.SETTINGS[0]
    settings = json.loads((tree / rel).read_text())
    del settings["env"]["PREK_HOME"]
    (tree / rel).write_text(json.dumps(settings), encoding="utf-8")
    assert mod.main(["--check", "--root", str(tree)]) == 1


def test_a_missing_block_is_reported(tree: Path) -> None:
    shim = tree / mod.SHIM
    shim.write_text(shim.read_text().replace("# BEGIN generated", "# BEGIN removed"))
    assert mod.main(["--root", str(tree)]) == 1


def test_empty_config_files_allowed_with_hook_marker(registry: dict[str, Any]) -> None:
    valid = copy.deepcopy(registry)
    valid["adapters"]["cargo-husky"]["detect"]["config_files"] = []
    valid["adapters"]["cargo-husky"]["detect"]["hook_marker"] = "cargo-husky"
    assert mod.validate(valid) == []


def test_none_strategy_generates_no_shim_case(registry: dict[str, Any]) -> None:
    """Adapters with strategy 'none' get no shim case in hook-manager-shim.sh."""
    blocks = mod.render(registry)
    shim_body = blocks[mod.SHIM]
    for name, adapter in registry["adapters"].items():
        if adapter["install"]["strategy"] == "none":
            assert f"{name})" not in shim_body
