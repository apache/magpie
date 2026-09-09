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

"""Tests for the substrate-plugin half of ``check-family-plugins.py``.

A substrate plugin exists to make a framework tool run from the installed plugin
root, so the failures worth catching are the ones that leave a plugin looking
correct while the hook it publishes never fires: a hook command that no longer
matches the wiring, a tool symlink pointing somewhere else, or an engine path
that does not resolve through it. Each is silent at runtime — a guard that is
not there does not raise, it just stops denying."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "check-family-plugins.py"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_family_plugins", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()
NAME = "magpie-agent-guard"

SHARED = {
    "version": "9.9.9",
    "author": {"name": "Apache Magpie", "url": "https://magpie.apache.org/"},
    "homepage": "https://magpie.apache.org/",
    "repository": "https://github.com/apache/magpie",
    "license": "Apache-2.0",
}


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A minimal repo root holding the real tool tree the substrate plugin links
    to, with the plugin itself generated the way ``--fix`` generates it."""
    (tmp_path / "tools" / "agent-guard" / "src" / "agent_guard").mkdir(parents=True)
    (tmp_path / "tools" / "agent-guard" / "src" / "agent_guard" / "__init__.py").write_text(
        "# engine\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    mod.write_substrate(NAME, SHARED)
    return tmp_path


def _manifest(tree: Path) -> Path:
    return tree / "plugins" / NAME / ".claude-plugin" / "plugin.json"


def _rewrite(path: Path, **changes) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_generated_substrate_plugin_passes_its_own_check(tree):
    assert mod.check_substrate(NAME, SHARED) == []


def test_generated_manifest_wires_the_engine_under_the_plugin_root(tree):
    manifest = json.loads(_manifest(tree).read_text(encoding="utf-8"))
    command = manifest["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in command
    assert mod.AGENT_GUARD_ENGINE in command
    # The path the command names must be reachable through the generated symlink.
    assert (tree / "plugins" / NAME / mod.AGENT_GUARD_ENGINE).is_file()


def test_altered_hook_wiring_is_reported(tree):
    _rewrite(_manifest(tree), hooks={"PreToolUse": []})
    assert any("'hooks' does not match" in e for e in mod.check_substrate(NAME, SHARED))


def test_a_substrate_plugin_declaring_skills_is_reported(tree):
    _rewrite(_manifest(tree), skills="./skills")
    assert any("drop 'skills'" in e for e in mod.check_substrate(NAME, SHARED))


def test_metadata_not_inherited_from_the_root_manifest_is_reported(tree):
    _rewrite(_manifest(tree), version="0.0.1")
    assert any("'version' is '0.0.1'" in e for e in mod.check_substrate(NAME, SHARED))


def test_a_repointed_tool_symlink_is_reported(tree):
    link = tree / "plugins" / NAME / "tools" / "agent-guard"
    link.unlink()
    link.symlink_to("../../../tools/something-else")
    assert any("expected ../../../tools/agent-guard" in e for e in mod.check_substrate(NAME, SHARED))


def test_a_symlink_replaced_by_a_real_directory_is_reported(tree):
    link = tree / "plugins" / NAME / "tools" / "agent-guard"
    link.unlink()
    link.mkdir()
    assert any("not a symlink" in e for e in mod.check_substrate(NAME, SHARED))


def test_an_engine_that_does_not_resolve_is_reported(tree):
    """The manifest and the symlink can both be right while the file the hook
    command names has moved — the case where the guard silently never runs."""
    (tree / "tools" / "agent-guard" / "src" / "agent_guard" / "__init__.py").unlink()
    assert any("does not resolve" in e for e in mod.check_substrate(NAME, SHARED))


def test_substrate_plugins_are_not_flagged_as_orphans(tree):
    """The orphan rule asks which skill declares family ``<x>`` for every
    ``plugins/magpie-<x>``; a substrate plugin answers "none" by design, while a
    genuinely stray dir must still be caught."""
    mod.MARKETPLACE.parent.mkdir(parents=True, exist_ok=True)
    mod.MARKETPLACE.write_text(json.dumps({"plugins": []}), encoding="utf-8")
    (tree / "plugins" / "magpie-bogus").mkdir()

    orphans = [e for e in mod.check({}) if "orphan plugin" in e]

    assert any("magpie-bogus" in e for e in orphans)
    assert not any(NAME in e for e in orphans)


def test_unowned_entries_accepts_the_generated_substrate_layout(tree):
    assert mod.unowned_entries(mod.PLUGINS / NAME) == []


def test_unowned_entries_refuses_to_delete_a_hand_added_file(tree):
    """``--fix`` rmtree's plugin dirs before regenerating them; anything it did
    not generate has to stop that rather than be silently discarded."""
    (tree / "plugins" / NAME / "README.md").write_text("hand-written\n", encoding="utf-8")
    errors = mod.unowned_entries(mod.PLUGINS / NAME)
    assert len(errors) == 1
    assert "README.md" in errors[0]


def test_the_real_repository_is_in_sync(monkeypatch):
    """The checked-in tree matches what ``--fix`` would generate — the same
    assertion CI makes, so a hand-edit to either manifest fails here first."""
    monkeypatch.chdir(REPO_ROOT)
    assert mod.check(mod.families_from_frontmatter()) == []


def test_the_marketplace_lists_the_substrate_plugin(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    entries = json.loads(mod.MARKETPLACE.read_text(encoding="utf-8"))["plugins"]
    entry = next(e for e in entries if e["name"] == NAME)
    assert entry["source"] == f"./plugins/{NAME}"


def test_the_substrate_plugin_stays_out_of_the_non_claude_catalogs(monkeypatch):
    """Its tool symlink resolves outside the plugin root, which Agent Plugins 1.0
    forbids — the same reason the family plugins are Claude Code-only."""
    monkeypatch.chdir(REPO_ROOT)
    for path in mod.CLIENT_CATALOGS:
        names = [e.get("name") for e in json.loads(path.read_text(encoding="utf-8"))["plugins"]]
        assert NAME not in names, f"{path} advertises {NAME}"


def test_fix_regenerates_a_deleted_substrate_plugin(tree, monkeypatch):
    import shutil

    shutil.rmtree(tree / "plugins" / NAME)
    mod.write_substrate(NAME, SHARED)
    assert mod.check_substrate(NAME, SHARED) == []
    assert os.path.islink(tree / "plugins" / NAME / "tools" / "agent-guard")


# ---------------------------------------------------------------------------
# Plugin skill aliases — the family prefix comes off the symlink, not the source
# ---------------------------------------------------------------------------


def test_alias_strips_the_repeated_family_name():
    """`/magpie-security:security-issue-triage` said "security" twice."""
    assert mod.plugin_alias("security-issue-triage", "security") == "issue-triage"
    assert mod.plugin_alias("pr-management-triage", "pr-management") == "triage"


def test_alias_strips_the_first_family_segment_too():
    """`release-*` skills sit in the `release-management` family, so the token
    they repeat is the family's first segment, not its whole name."""
    assert mod.plugin_alias("release-vote-tally", "release-management") == "vote-tally"


def test_alias_leaves_a_name_that_does_not_repeat_the_family():
    assert mod.plugin_alias("dependency-audit", "repo-health") == "dependency-audit"
    assert mod.plugin_alias("reviewer-routing", "pr-management") == "reviewer-routing"


def test_alias_overrides_win():
    """`setup` would strip to nothing; `contributor-to-committer` to a fragment."""
    assert mod.plugin_alias("setup", "setup") == "setup"
    assert mod.plugin_alias("contributor-to-committer", "contributor-growth") == ("contributor-to-committer")


def test_aliases_are_unique_within_every_real_family(monkeypatch):
    """The guarantee the scheme rests on. Across families they may repeat —
    `stale-sweep` exists in both magpie-issue and magpie-pr-management — because
    each plugin is its own namespace."""
    monkeypatch.chdir(REPO_ROOT)
    for family, skills in mod.families_from_frontmatter().items():
        aliases = mod.aliases_for(family, skills)
        assert len(aliases) == len(skills), f"magpie-{family} lost a skill to a collision"


def test_a_within_family_alias_collision_is_refused():
    with pytest.raises(SystemExit, match="alias collision"):
        mod.aliases_for("demo", {"demo-triage", "triage"})


def test_generated_symlink_is_named_by_the_alias_and_targets_the_source(tree, monkeypatch):
    """The whole point: the link *name* de-stutters, the *target* is untouched,
    so the source directory (and the portable install name) never moves."""
    monkeypatch.chdir(REPO_ROOT)
    link = REPO_ROOT / "plugins" / "magpie-security" / "skills" / "issue-triage"
    assert link.is_symlink()
    assert link.readlink().name == "security-issue-triage"
    assert (link / "SKILL.md").is_file()
