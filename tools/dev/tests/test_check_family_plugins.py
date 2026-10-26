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
import pathlib
import re
import subprocess
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


def _hooks(tree: Path) -> Path:
    return tree / "plugins" / NAME / "hooks" / "hooks.json"


def _rewrite(path: Path, **changes) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_generated_substrate_plugin_passes_its_own_check(tree):
    assert mod.check_substrate(NAME, SHARED) == []


def test_generated_hook_config_wires_the_engine_under_the_plugin_root(tree):
    manifest = json.loads(_manifest(tree).read_text(encoding="utf-8"))
    assert "hooks" not in manifest

    hooks = json.loads(_hooks(tree).read_text(encoding="utf-8"))
    command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}" in command
    assert mod.AGENT_GUARD_ENGINE in command
    # The path the command names must exist inside the generated plugin.
    assert (tree / "plugins" / NAME / mod.AGENT_GUARD_ENGINE).is_file()


def test_altered_hook_wiring_is_reported(tree):
    _rewrite(_hooks(tree), hooks={"PreToolUse": []})
    assert any("hook wiring does not match" in e for e in mod.check_substrate(NAME, SHARED))


def test_missing_hook_config_is_reported(tree):
    _hooks(tree).unlink()
    assert any("missing substrate hook configuration" in e for e in mod.check_substrate(NAME, SHARED))


def test_inline_manifest_hook_is_reported(tree):
    _rewrite(_manifest(tree), hooks={"PreToolUse": []})
    assert any("belongs in hooks/hooks.json" in e for e in mod.check_substrate(NAME, SHARED))


def test_a_substrate_plugin_declaring_skills_is_reported(tree):
    _rewrite(_manifest(tree), skills="./skills")
    assert any("drop 'skills'" in e for e in mod.check_substrate(NAME, SHARED))


def test_metadata_not_inherited_from_the_root_manifest_is_reported(tree):
    _rewrite(_manifest(tree), version="0.0.1")
    assert any("'version' is '0.0.1'" in e for e in mod.check_substrate(NAME, SHARED))


def test_altered_copied_runtime_is_reported(tree):
    runtime = tree / "plugins" / NAME / "tools" / "agent-guard" / "src" / "agent_guard" / "__init__.py"
    runtime.write_text("# altered\n", encoding="utf-8")
    assert any("copied runtime file" in e and "out of sync" in e for e in mod.check_substrate(NAME, SHARED))


def test_missing_copied_runtime_is_reported(tree):
    import shutil

    runtime = tree / "plugins" / NAME / "tools" / "agent-guard" / "src" / "agent_guard"
    shutil.rmtree(runtime)
    assert any("missing copied runtime tree" in e for e in mod.check_substrate(NAME, SHARED))


def test_an_engine_that_does_not_resolve_is_reported(tree):
    """The generated plugin can be wired correctly while the packaged engine
    named by the hook is missing."""
    (tree / "plugins" / NAME / mod.AGENT_GUARD_ENGINE).unlink()
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


def test_codex_advertises_self_contained_substrates_only(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    names = {e["name"] for e in json.loads(mod.CODEX_CATALOG.read_text())["plugins"]}
    assert names >= mod.CODEX_SUBSTRATES
    for name in mod.CODEX_SUBSTRATES:
        spec = mod.SUBSTRATE_PLUGINS[name]
        assert not spec["links"], "Codex must not install outward tool symlinks"
        assert "hooks" not in spec, "Codex requires a hook config file"
        if "hook_config" in spec:
            plugin = REPO_ROOT / mod.PLUGINS / name
            manifest = json.loads((plugin / ".claude-plugin/plugin.json").read_text())
            assert "hooks" not in manifest
            assert json.loads((plugin / "hooks/hooks.json").read_text()) == spec["hook_config"]
        for relative in spec["must_resolve"]:
            path = REPO_ROOT / mod.PLUGINS / name / relative
            assert path.is_file()
            assert path.resolve().is_relative_to((REPO_ROOT / mod.PLUGINS / name).resolve())
    copilot = next(p for p in mod.CLIENT_CATALOGS if p != mod.CODEX_CATALOG)
    assert NAME not in {e["name"] for e in json.loads(copilot.read_text())["plugins"]}


def test_vetted_plugin_startup_creates_the_dispatcher_path(tmp_path):
    plugin = REPO_ROOT / mod.PLUGINS / "magpie-vetted-ops"
    hooks = json.loads((plugin / "hooks/hooks.json").read_text())
    command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    result = subprocess.run(
        ["bash", "-c", command],
        input="{}",
        text=True,
        capture_output=True,
        env={**os.environ, "HOME": str(tmp_path), "CLAUDE_PLUGIN_ROOT": str(plugin)},
    )
    assert result.returncode == 0, result.stderr
    link = tmp_path / ".claude/magpie/vetted-ops"
    assert link.is_symlink()
    assert link.resolve() == plugin / "tools/vetted-ops"
    assert (link / "src/vetted_ops/cli.py").is_file()


def test_fix_regenerates_a_deleted_substrate_plugin(tree, monkeypatch):
    import shutil

    shutil.rmtree(tree / "plugins" / NAME)
    mod.write_substrate(NAME, SHARED)
    assert mod.check_substrate(NAME, SHARED) == []
    runtime = tree / "plugins" / NAME / "tools" / "agent-guard" / "src" / "agent_guard" / "__init__.py"
    assert runtime.is_file()
    assert not os.path.islink(tree / "plugins" / NAME / "tools" / "agent-guard")


# ---------------------------------------------------------------------------
# magpie-setup ships the pre-flight checker inside its own root
# ---------------------------------------------------------------------------


def _preflight_layout(root: Path) -> None:
    """The shape the repository has: real package in the setup skill, the
    workspace member's ``src/`` linking in to it."""
    package = root / mod.SETUP_PREFLIGHT_PACKAGE
    package.mkdir(parents=True)
    (package / "__main__.py").write_text("# entry\n", encoding="utf-8")
    mirror = root / mod.SETUP_PREFLIGHT_MIRROR
    mirror.parent.mkdir(parents=True)
    mirror.symlink_to(mod.SETUP_PREFLIGHT_MIRROR_TARGET)


def test_the_setup_plugin_ships_the_preflight_package(monkeypatch):
    """A marketplace install is the plugin root and nothing else, so the
    checker every skill's pre-flight runs has to be a real directory in it."""
    monkeypatch.chdir(REPO_ROOT)
    package = REPO_ROOT / mod.SETUP_PREFLIGHT_PACKAGE
    assert package.is_dir() and not package.is_symlink()
    assert (package / "__main__.py").is_file()
    assert mod.check_setup_preflight_package() == []


def test_the_generated_preflight_layout_passes(tmp_path, monkeypatch):
    _preflight_layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert mod.check_setup_preflight_package() == []


def test_a_missing_preflight_package_is_reported(tmp_path, monkeypatch):
    _preflight_layout(tmp_path)
    (tmp_path / mod.SETUP_PREFLIGHT_PACKAGE / "__main__.py").unlink()
    monkeypatch.chdir(tmp_path)
    assert any("no pre-flight checker" in e for e in mod.check_setup_preflight_package())


def test_a_preflight_package_linked_out_of_the_plugin_is_reported(tmp_path, monkeypatch):
    """The out-of-root link Agent Plugins 1.0 forbids in a Codex-listed plugin."""
    real = tmp_path / "tools" / "setup-preflight" / "src" / "setup_preflight"
    real.mkdir(parents=True)
    (real / "__main__.py").write_text("# entry\n", encoding="utf-8")
    package = tmp_path / mod.SETUP_PREFLIGHT_PACKAGE
    package.parent.mkdir(parents=True)
    package.symlink_to("../../../../tools/setup-preflight/src/setup_preflight")
    monkeypatch.chdir(tmp_path)
    errors = mod.check_setup_preflight_package()
    assert any("must be a real directory" in e for e in errors)
    assert any("expected a symlink" in e for e in errors)


def _welcome_tree(root: Path) -> None:
    """A copy of the real checker beside one plugin skill, whose map is stale."""
    import shutil

    shutil.copytree(
        REPO_ROOT / mod.SETUP_PREFLIGHT_PACKAGE,
        root / mod.SETUP_PREFLIGHT_PACKAGE,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    skill = root / "plugins" / "magpie-security" / "skills" / "issue-sync"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: issue-sync\nfamily: security\n---\n", encoding="utf-8")


def test_the_real_welcome_family_map_is_in_sync(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    assert mod.welcome_families("check-constant") == []


def test_a_stale_welcome_family_map_is_reported_and_fixed(tmp_path, monkeypatch):
    _welcome_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert any("families.py" in e for e in mod.welcome_families("check-constant"))
    assert mod.welcome_families("write-constant") == []
    assert mod.welcome_families("check-constant") == []


def test_a_tree_without_the_checker_has_no_family_map_to_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert mod.welcome_families("check-constant") == []


# ---------------------------------------------------------------------------
# Plugin skill aliases — the family prefix comes off the symlink, not the source
# ---------------------------------------------------------------------------


def test_alias_strips_the_repeated_family_name():
    """`/magpie-security:security-issue-triage` said "security" twice."""
    assert mod.plugin_alias("security-issue-triage", "security") == "issue-triage"
    assert mod.plugin_alias("issue-triage", "issue") == "triage"


def test_alias_strips_the_first_family_segment_too():
    """`release-*` skills sit in the `release-management` family, so the token
    they repeat is the family's first segment, not its whole name."""
    assert mod.plugin_alias("release-vote-tally", "release-management") == "vote-tally"


def test_alias_leaves_a_name_that_does_not_repeat_the_family():
    assert mod.plugin_alias("dependency-audit", "repo-health") == "dependency-audit"
    assert mod.plugin_alias("reviewer-routing", "pr-management") == "reviewer-routing"


def test_alias_overrides_win():
    """`setup` would strip to nothing; `contributor-to-committer` to a fragment;
    the pull-request family's `triage` / `stale-sweep` would repeat the issue
    family's."""
    assert mod.plugin_alias("setup", "setup") == "setup"
    assert mod.plugin_alias("contributor-to-committer", "contributor-growth") == ("contributor-to-committer")
    assert mod.plugin_alias("pr-management-triage", "pr-management") == "pr-triage"
    assert mod.plugin_alias("pr-stale-sweep", "pr-management") == "pr-stale-sweep"


def test_aliases_are_unique_within_every_real_family(monkeypatch):
    """The guarantee the scheme rests on: no family loses a skill to a collision."""
    monkeypatch.chdir(REPO_ROOT)
    for family, skills in mod.families_from_frontmatter().items():
        aliases = mod.aliases_for(family, skills)
        assert len(aliases) == len(skills), f"magpie-{family} lost a skill to a collision"


def test_aliases_are_unique_across_all_families(monkeypatch):
    """The alias is also the skill's frontmatter `name:`, and Antigravity keeps
    skills in one flat slash-command namespace, so a repeat across families is a collision."""
    monkeypatch.chdir(REPO_ROOT)
    seen: dict[str, str] = {}
    for family, skills in mod.families_from_frontmatter().items():
        for alias in mod.aliases_for(family, skills):
            assert alias not in seen, f"'{alias}' is in magpie-{seen[alias]} and magpie-{family}"
            seen[alias] = family


def test_every_skill_name_is_its_plugin_directory(monkeypatch):
    """Claude Code and Codex invoke a plugin skill by frontmatter `name:`; a
    `magpie-<flat>` name surfaced as `/magpie-setup:magpie-setup-…`."""
    monkeypatch.chdir(REPO_ROOT)
    for skill_md in sorted((REPO_ROOT / "plugins").glob("magpie-*/skills/*/SKILL.md")):
        name = re.search(r"^name:\s*(\S+)", skill_md.read_text(encoding="utf-8"), re.M)
        assert name and name.group(1) == skill_md.parent.name, skill_md


def test_a_within_family_alias_collision_is_refused():
    with pytest.raises(SystemExit, match="alias collision"):
        mod.aliases_for("demo", {"demo-triage", "triage"})


def test_the_family_plugin_owns_its_skills_and_the_flat_tree_mirrors_them(tree, monkeypatch):
    """The direction that makes a family plugin installable off Claude Code.

    A plugin whose skills were symlinks out to the flat tree installs on Codex
    with zero skills -- silently, no error. So the plugin owns the real
    directory, de-stuttered, and `skills/<flat>` points back in to keep every
    path that has always said `skills/<flat>` resolving.
    """
    monkeypatch.chdir(REPO_ROOT)
    owned = REPO_ROOT / "plugins" / "magpie-security" / "skills" / "issue-triage"
    assert owned.is_dir() and not owned.is_symlink()
    assert (owned / "SKILL.md").is_file()

    mirror = REPO_ROOT / "skills" / "security-issue-triage"
    assert mirror.is_symlink()
    assert mirror.readlink() == pathlib.Path("../plugins/magpie-security/skills/issue-triage")
    assert (mirror / "SKILL.md").is_file()


def test_no_plugin_path_escapes_its_own_root(tree, monkeypatch):
    """Agent Plugins 1.0 §4.1: a package path resolving outside the plugin root
    must be rejected. Codex does not reject it -- it installs the plugin with
    the offending skills silently missing, which is worse."""
    monkeypatch.chdir(REPO_ROOT)
    for fam in sorted((REPO_ROOT / "plugins").glob("magpie-*")):
        skills = fam / "skills"
        if not skills.is_dir():
            continue
        for entry in skills.iterdir():
            assert not entry.is_symlink(), f"{entry} is a symlink; Codex would drop it"


# ---------------------------------------------------------------------------
# magpie-setup ships the project templates inside its own root
# ---------------------------------------------------------------------------


def _templates_layout(root: Path) -> None:
    """The shape the repository has: real templates in the setup skill,
    ``projects/_template`` linking in to them."""
    templates = root / mod.SETUP_TEMPLATES
    templates.mkdir(parents=True)
    (templates / "project.md").write_text("# template\n", encoding="utf-8")
    mirror = root / mod.SETUP_TEMPLATES_MIRROR
    mirror.parent.mkdir(parents=True)
    mirror.symlink_to(mod.SETUP_TEMPLATES_MIRROR_TARGET)


def test_the_setup_plugin_ships_the_project_templates(monkeypatch):
    """`setup config` scaffolds from these; a marketplace install has only
    the plugin root to take them from."""
    monkeypatch.chdir(REPO_ROOT)
    templates = REPO_ROOT / mod.SETUP_TEMPLATES
    assert templates.is_dir() and not templates.is_symlink()
    for name in ("project.md", "adversarial-review.md", "commit-attribution.toml"):
        assert (templates / name).is_file(), name
    assert mod.check_setup_templates() == []


def test_the_generated_templates_layout_passes(tmp_path, monkeypatch):
    _templates_layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert mod.check_setup_templates() == []


def test_missing_templates_are_reported(tmp_path, monkeypatch):
    _templates_layout(tmp_path)
    (tmp_path / mod.SETUP_TEMPLATES / "project.md").unlink()
    monkeypatch.chdir(tmp_path)
    assert any("no templates to scaffold from" in e for e in mod.check_setup_templates())


def test_templates_linked_out_of_the_plugin_are_reported(tmp_path, monkeypatch):
    """The out-of-root link Agent Plugins 1.0 forbids in a Codex-listed plugin."""
    real = tmp_path / "projects" / "_template"
    real.mkdir(parents=True)
    (real / "project.md").write_text("# template\n", encoding="utf-8")
    templates = tmp_path / mod.SETUP_TEMPLATES
    templates.parent.mkdir(parents=True)
    templates.symlink_to("../../projects/_template")
    monkeypatch.chdir(tmp_path)
    errors = mod.check_setup_templates()
    assert any("must be a real directory" in e for e in errors)
    assert any("expected a symlink" in e for e in errors)


def test_packaged_readme_links_stay_portable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "tools/tool/README.md"
    dest = tmp_path / "plugins/plugin/tools/tool/README.md"
    src.parent.mkdir(parents=True)
    (src.parent / "src").mkdir()
    src.write_text(
        '[local](src/file.py) [framework](../../docs/file.md#anchor "title") '
        "[web](https://example.com) [section](#part) [outside](../../../outside.md)\n"
        "```markdown\n[example](../../unchanged.md)\n```\n"
    )
    copies = {str(dest.parent / "src"): str(src.parent / "src")}
    text = mod.packaged_file_bytes(src, copies).decode()
    assert "](src/file.py)" in text
    assert '](https://github.com/apache/magpie/blob/main/docs/file.md#anchor "title")' in text
    assert "[web](https://example.com)" in text
    assert "](#part)" in text
    assert "](../../../outside.md)" in text
    assert "](../../unchanged.md)" in text


def test_file_copy_passes_and_reports_drift(tree, monkeypatch):
    source = tree / "runtime.toml"
    source.write_text("enabled = true\n")
    spec = {
        **mod.SUBSTRATE_PLUGINS[NAME],
        "copies": {
            **mod.SUBSTRATE_PLUGINS[NAME]["copies"],
            "tools/agent-guard/runtime.toml": "runtime.toml",
        },
    }
    monkeypatch.setitem(mod.SUBSTRATE_PLUGINS, NAME, spec)
    mod.write_substrate(NAME, SHARED)
    assert mod.check_substrate(NAME, SHARED) == []
    dest = tree / "plugins" / NAME / "tools/agent-guard/runtime.toml"
    dest.write_text("enabled = false\n")
    assert any("out of sync" in e for e in mod.check_substrate(NAME, SHARED))


@pytest.mark.parametrize(
    "path",
    [
        "tools/vetted-ops/src/vetted_ops/ops.py",
        "tools/vetted-ops/hooks/link-stable-path.sh",
        "tools/vetted-ops/pyproject.toml",
        "tools/vetted-ops/README.md",
        "tools/agent-guard/src/agent_guard/__init__.py",
        "tools/dev/check-family-plugins.py",
    ],
)
def test_source_changes_trigger_packaging_hook(path):
    config = (REPO_ROOT / ".pre-commit-config.yaml").read_text()
    block = config.split("- id: check-family-plugins\n", 1)[1].split("pass_filenames:", 1)[0]
    match = re.search(r"files: (.+)", block)
    assert match is not None
    assert re.match(match.group(1), path), f"packaging check would skip {path}"


# --- the packaged pyproject of a copied tool -------------------------------------


def test_a_copied_tool_pyproject_resolves_inside_the_plugin(tmp_path, monkeypatch):
    # A tool depending on another copied tool, with the workspace-only dev group.
    (tmp_path / "tools" / "a").mkdir(parents=True)
    (tmp_path / "tools" / "nested" / "b").mkdir(parents=True)
    (tmp_path / "tools" / "a" / "pyproject.toml").write_text(
        '[project]\nname = "a"\ndependencies = ["b>=1"]\n\n[dependency-groups]\ndev = ["magpie-dev"]\n\n'
        "[tool.ruff]\nline-length = 110\n",
        encoding="utf-8",
    )
    (tmp_path / "tools" / "nested" / "b" / "pyproject.toml").write_text(
        '[project]\nname = "b"\ndependencies = []\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    copies = {
        "tools/a/pyproject.toml": "tools/a/pyproject.toml",
        "tools/nested/b/pyproject.toml": "tools/nested/b/pyproject.toml",
    }
    packaged = mod.packaged_file_bytes(Path("tools/a/pyproject.toml"), copies).decode()
    assert "[dependency-groups]" not in packaged and "magpie-dev" not in packaged
    assert '[tool.uv.sources]\nb = { path = "../nested/b" }\n' in packaged
    assert "[tool.ruff]" in packaged  # only the dev group goes


def test_the_security_tools_plugin_ships_every_tool_the_skills_name():
    # Every `<framework>/tools/<tool>` a security skill runs is in the plugin.
    named = set()
    for skill in (REPO_ROOT / "plugins" / "magpie-security" / "skills").rglob("*.md"):
        named |= set(
            re.findall(r"<framework>/tools/([a-z0-9-]+(?:/[a-z0-9-]+)?)", skill.read_text(encoding="utf-8"))
        )
    shipped = {Path(dest).relative_to("tools").as_posix() for dest in mod.SECURITY_TOOLS} | {
        "security-tracker-stats-dashboard/run",
        "local-tracker",  # ships with magpie-vetted-ops, beside the dispatcher
    }
    assert named <= shipped, sorted(named - shipped)


def test_the_security_tools_plugin_ships_the_forwarder_registry():
    copies = mod.SUBSTRATE_PLUGINS["magpie-security-tools"]["copies"]
    assert "tools/forwarder-relay/README.md" in copies
    assert "tools/gmail/asf-relay.md" in copies


# ---------------------------------------------------------------------------
# Codex loads magpie-setup's upgrade hook from a hook file it can parse
# ---------------------------------------------------------------------------


@pytest.fixture
def codex_tree(tmp_path, monkeypatch):
    """The plugins with Codex hook files, generated the way ``--fix`` does, and
    a Codex catalogue listing them."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".codex-plugin").mkdir()
    (tmp_path / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "magpie", "version": SHARED["version"], "skills": "./skills"}), encoding="utf-8"
    )
    for name in mod.CODEX_FAMILY_HOOKS:
        pdir = tmp_path / "plugins" / name
        (pdir / ".claude-plugin").mkdir(parents=True)
        (pdir / "hooks").mkdir()
        (pdir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": name, "description": f"{name} skills", **SHARED, "skills": "./skills"}),
            encoding="utf-8",
        )
        # Claude Code's hook file, which Codex cannot parse.
        (pdir / "hooks" / "hooks.json").write_text(
            json.dumps({"$schema": "https://code.claude.com/schemas/hooks.json", "modules": ["./m.ts"]}),
            encoding="utf-8",
        )
        mod.write_codex_family_hooks(name, f"{name} skills", SHARED)
    catalog = tmp_path / mod.CODEX_CATALOG
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        json.dumps(
            {
                "plugins": [
                    {"name": name, "source": {"source": "local", "path": f"./plugins/{name}"}}
                    for name in mod.CODEX_FAMILY_HOOKS
                ]
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _codex_manifest(tree: Path, name: str = "magpie-setup") -> Path:
    return tree / "plugins" / name / ".codex-plugin" / "plugin.json"


def test_the_generated_codex_wiring_passes(codex_tree):
    assert mod.check_codex_family_hooks(SHARED) == []
    assert mod.check_codex_hook_files() == []


def test_the_codex_manifest_names_the_clean_hook_file(codex_tree):
    manifest = json.loads(_codex_manifest(codex_tree).read_text(encoding="utf-8"))
    assert manifest["hooks"] == "./hooks/codex-hooks.json"
    assert manifest["skills"] == "./skills"
    assert {k: manifest[k] for k in SHARED} == SHARED
    hooks = json.loads((codex_tree / "plugins/magpie-setup/hooks/codex-hooks.json").read_text())
    command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command == '/bin/bash -p "${PLUGIN_ROOT}/hooks/check-upgrade.sh"'


def test_a_root_codex_hook_is_reported(codex_tree):
    _rewrite(codex_tree / ".codex-plugin" / "plugin.json", hooks={"SessionStart": []})
    assert any("no catalogue installs the repo root" in e for e in mod.check_codex_family_hooks(SHARED))


def test_a_missing_codex_manifest_is_reported(codex_tree):
    _codex_manifest(codex_tree).unlink()
    assert any("missing" in e for e in mod.check_codex_family_hooks(SHARED))
    # ...and Codex then falls back to the Claude-only hooks.json.
    assert any("$schema" in e for e in mod.check_codex_hook_files())


def test_a_codex_manifest_left_at_an_old_version_is_reported(codex_tree):
    _rewrite(_codex_manifest(codex_tree), version="0.0.1")
    assert any("does not match the Codex manifest" in e for e in mod.check_codex_family_hooks(SHARED))


def test_an_altered_codex_hook_file_is_reported(codex_tree):
    _rewrite(codex_tree / "plugins/magpie-setup/hooks/codex-hooks.json", hooks={})
    assert any("does not match the Codex hook wiring" in e for e in mod.check_codex_family_hooks(SHARED))


def test_a_claude_only_key_in_a_codex_hook_file_is_reported(codex_tree):
    _rewrite(codex_tree / "plugins/magpie-setup/hooks/codex-hooks.json", modules=["./m.ts"])
    assert any("modules" in e and "rejects the whole file" in e for e in mod.check_codex_hook_files())


def test_an_inline_codex_hook_with_a_claude_only_key_is_reported(codex_tree):
    _rewrite(_codex_manifest(codex_tree), hooks={"$schema": "x", "hooks": {}})
    assert any("#hooks[0]" in e for e in mod.check_codex_hook_files())


def test_every_real_codex_plugin_exposes_parseable_hooks(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    assert mod.check_codex_hook_files() == []
    assert mod.check_codex_family_hooks(mod.root_metadata()[0]) == []
