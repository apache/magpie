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

"""Tests for in-place guard discovery — the property that lets the hook run
straight from an installed plugin with nothing copied into a consumer repo.

The failure these guard against is silent: a guard directory that stops being
discovered does not raise, it simply stops denying, and the operator finds out
when an unguarded command lands."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

import agent_guard

REPO_ROOT = Path(agent_guard.__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
def _no_env_dirs(monkeypatch):
    monkeypatch.delenv(agent_guard.GUARD_DIRS_ENV, raising=False)


def test_framework_root_is_the_checkout_holding_skills_and_the_engine():
    assert agent_guard.framework_root() == REPO_ROOT
    assert (REPO_ROOT / "skills").is_dir()
    assert (REPO_ROOT / "tools" / "agent-guard").is_dir()


def test_framework_root_is_none_for_a_standalone_copy(tmp_path, monkeypatch):
    """A single self-contained copy of the engine has no framework tree above it.
    ``framework_root`` must say so rather than climbing to an unrelated ancestor
    that happens to hold a ``skills/`` directory."""
    lone = tmp_path / "hooks" / "agent-guard.py"
    lone.parent.mkdir(parents=True)
    lone.write_text(Path(agent_guard.__file__).read_text(encoding="utf-8"), encoding="utf-8")

    spec = importlib.util.spec_from_file_location("_standalone_agent_guard", lone)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.framework_root() is None
    assert module.guard_dirs() == []  # no guards.d sibling either


def test_skill_guard_dirs_are_discovered_without_configuration():
    """Every ``skills/*/guards`` in the framework tree is scanned as-is — this is
    what removes the "collect skill guards into a local guards.d" install step."""
    dirs = agent_guard.guard_dirs()
    on_disk = sorted((REPO_ROOT / "skills").glob("*/guards"))
    assert on_disk, "expected at least one skill-owned guards dir in the repo"
    for d in on_disk:
        assert d in dirs
    assert dirs[-1] == Path(agent_guard.__file__).resolve().parent / "guards.d"


def test_env_dirs_are_searched_before_discovered_ones(monkeypatch, tmp_path):
    extra = tmp_path / "extra-guards"
    extra.mkdir()
    monkeypatch.setenv(agent_guard.GUARD_DIRS_ENV, str(extra))
    assert agent_guard.guard_dirs()[0] == extra


def test_a_skill_owned_guard_denies_with_no_env_configuration(monkeypatch):
    """End-to-end: the mention guard lives in ``skills/pr-management-triage/guards``
    and must fire on a plain dispatch with nothing pointing at it."""
    for name in ("MAGPIE_GUARD_OFF", "MAGPIE_ALLOW_MENTIONS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(agent_guard, "_run", lambda args, cwd=None: None)

    reason = agent_guard.dispatch('gh pr comment 123 --body "@somebody take a look"', None)

    assert reason is not None
    assert "mention" in reason


def test_discovery_survives_being_reached_through_a_symlinked_plugin_root(tmp_path):
    """How the published plugin actually resolves: ``plugins/magpie-agent-guard``
    exposes the engine through a symlink, so ``__file__`` is a path outside the
    framework tree until it is resolved."""
    link_parent = tmp_path / "plugin" / "tools"
    link_parent.mkdir(parents=True)
    (link_parent / "agent-guard").symlink_to(REPO_ROOT / "tools" / "agent-guard")

    entry = link_parent / "agent-guard" / "src" / "agent_guard" / "__init__.py"
    spec = importlib.util.spec_from_file_location("_linked_agent_guard", entry)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.framework_root() == REPO_ROOT
    assert sorted((REPO_ROOT / "skills").glob("*/guards"))[0] in module.guard_dirs()


def test_guard_dirs_are_deduplicated(monkeypatch):
    """A skill guards dir named in the environment as well as discovered is
    scanned once — otherwise its guards would run twice per command."""
    skill_guards = sorted((REPO_ROOT / "skills").glob("*/guards"))[0]
    monkeypatch.setenv(agent_guard.GUARD_DIRS_ENV, f"{skill_guards}{os.pathsep}{skill_guards}")
    assert agent_guard.guard_dirs().count(skill_guards) == 1
