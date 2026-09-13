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

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import list_skills


def write_skill(
    skills_dir: Path,
    dir_name: str,
    *,
    name: str | None = None,
    family: str | None = None,
    description: str = "Does a thing. And then another thing.",
) -> Path:
    """Create a minimal SKILL.md with the frontmatter shape the framework uses."""
    skill_dir = skills_dir / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---", "# SPDX-License-Identifier: Apache-2.0"]
    if name is not None:
        lines.append(f"name: {name}")
    if family is not None:
        lines.append(f"family: {family}")
    lines.append("description: |")
    for part in description.split("\n"):
        lines.append(f"  {part}")
    lines += ["license: Apache-2.0", "---", "", "# body", ""]
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")
    return skill_dir


class FrontmatterTest(unittest.TestCase):
    def test_block_scalar_is_folded_onto_one_line(self) -> None:
        text = "---\nname: magpie-x\ndescription: |\n  First line\n  second line.\n---\nbody\n"
        meta = list_skills.parse_frontmatter(text)
        self.assertEqual(meta["description"], "First line second line.")

    def test_plain_scalars_and_quotes(self) -> None:
        text = '---\nname: magpie-x\nfamily: utilities\nmode: "Meta"\n---\n'
        meta = list_skills.parse_frontmatter(text)
        self.assertEqual(meta["name"], "magpie-x")
        self.assertEqual(meta["family"], "utilities")
        self.assertEqual(meta["mode"], "Meta")

    def test_nested_keys_do_not_leak_as_top_level(self) -> None:
        text = "---\nname: magpie-x\nnested:\n  inner: value\nfamily: setup\n---\n"
        meta = list_skills.parse_frontmatter(text)
        self.assertNotIn("inner", meta)
        self.assertEqual(meta["family"], "setup")

    def test_colon_inside_a_block_scalar_is_not_a_key(self) -> None:
        text = "---\nname: magpie-x\ndescription: |\n  Use it: like this.\n---\n"
        meta = list_skills.parse_frontmatter(text)
        self.assertEqual(meta["description"], "Use it: like this.")
        self.assertNotIn("Use it", meta)

    def test_missing_or_malformed_frontmatter_is_empty(self) -> None:
        self.assertEqual(list_skills.parse_frontmatter("no frontmatter here"), {})
        self.assertEqual(list_skills.parse_frontmatter("---\nunterminated: yes\n"), {})

    def test_first_sentence(self) -> None:
        self.assertEqual(list_skills.first_sentence("One. Two. Three."), "One.")
        self.assertEqual(list_skills.first_sentence("No terminator"), "No terminator")


class DiscoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        # A script path outside any plugin cache, so the marketplace source is
        # inert unless a test asks for it.
        self.plain_script = self.tmp / "elsewhere" / "scripts" / "list_skills.py"
        self.plain_script.parent.mkdir(parents=True)
        self.plain_script.touch()

    def test_family_comes_from_frontmatter_not_the_name_prefix(self) -> None:
        """Golden rule 8: `write-skill` is family `utilities`, not family `write`."""
        root = self.tmp / "repo"
        write_skill(
            root / ".agents/skills", "magpie-write-skill", name="magpie-write-skill", family="utilities"
        )
        write_skill(
            root / ".agents/skills",
            "magpie-optimize-skill",
            name="magpie-optimize-skill",
            family="utilities",
        )
        rows = list_skills.collect_rows(root, self.plain_script)
        self.assertEqual({r["family"] for r in rows}, {"utilities"})

    def test_skill_without_a_family_key_lands_in_other(self) -> None:
        root = self.tmp / "repo"
        write_skill(root / ".agents/skills", "magpie-legacy", name="magpie-legacy")
        rows = list_skills.collect_rows(root, self.plain_script)
        self.assertEqual(rows[0]["family"], "other")

    def test_relay_directories_collapse_to_one_row(self) -> None:
        root = self.tmp / "repo"
        write_skill(root / ".agents/skills", "magpie-x", name="magpie-x", family="setup")
        write_skill(root / ".claude/skills", "magpie-x", name="magpie-x", family="setup")
        write_skill(root / ".github/skills", "magpie-x", name="magpie-x", family="setup")
        rows = list_skills.collect_rows(root, self.plain_script)
        self.assertEqual([r["invocation"] for r in rows], ["/magpie-x"])

    def test_framework_checkout_skills_are_found(self) -> None:
        root = self.tmp / "framework"
        write_skill(root / "skills", "setup", name="magpie-setup", family="setup")
        write_skill(root / "skills", "list-skills", name="magpie-list-skills", family="utilities")
        rows = list_skills.collect_rows(root, self.plain_script)
        self.assertEqual(sorted(r["invocation"] for r in rows), ["/magpie-list-skills", "/magpie-setup"])

    def test_a_bare_skills_dir_is_not_mistaken_for_the_framework(self) -> None:
        """A project of its own with an unrelated `skills/` directory is not
        the framework checkout, and must not be walked as one."""
        root = self.tmp / "some-project"
        write_skill(root / "skills", "their-own-thing", name="their-own-thing")
        rows = list_skills.collect_rows(root, self.plain_script)
        self.assertEqual(rows, [])

    def test_marketplace_install_finds_every_sibling_plugin(self) -> None:
        """The regression this fix exists for: running from one installed
        family plugin must list every installed family, not just its own."""
        cache = self.tmp / "home" / ".claude" / "plugins" / "cache" / "apache-magpie"
        version = "0.2.0.dev1"
        for plugin, skill, family in [
            ("magpie-utilities", "list-skills", "utilities"),
            ("magpie-utilities", "write-skill", "utilities"),
            ("magpie-setup", "setup", "setup"),
            ("magpie-pr-management", "pr-management-triage", "pr-management"),
        ]:
            write_skill(cache / plugin / version / "skills", skill, name=f"magpie-{skill}", family=family)
        script = (
            cache / "magpie-utilities" / version / "skills" / "list-skills" / "scripts" / "list_skills.py"
        )
        script.parent.mkdir(parents=True)
        script.touch()

        rows = list_skills.collect_rows(self.tmp / "unrelated-repo", script)
        self.assertEqual(
            sorted(r["invocation"] for r in rows),
            [
                "/magpie-pr-management:pr-management-triage",
                "/magpie-setup:setup",
                "/magpie-utilities:list-skills",
                "/magpie-utilities:write-skill",
            ],
        )
        self.assertEqual({r["family"] for r in rows}, {"utilities", "setup", "pr-management"})

    def test_marketplace_prefers_the_running_version_over_a_stale_one(self) -> None:
        cache = self.tmp / "home" / ".claude" / "plugins" / "cache" / "apache-magpie"
        write_skill(cache / "magpie-setup" / "0.1.0" / "skills", "old-skill", name="magpie-old-skill")
        write_skill(cache / "magpie-setup" / "0.2.0" / "skills", "new-skill", name="magpie-new-skill")
        script = cache / "magpie-setup" / "0.2.0" / "skills" / "new-skill" / "scripts" / "list_skills.py"
        script.parent.mkdir(parents=True)
        script.touch()

        rows = list_skills.collect_rows(self.tmp / "unrelated-repo", script)
        self.assertEqual([r["invocation"] for r in rows], ["/magpie-setup:new-skill"])

    def test_repository_and_marketplace_installs_are_both_reported(self) -> None:
        """Two install methods side by side are two different things to type,
        so both rows survive de-duplication."""
        root = self.tmp / "repo"
        write_skill(
            root / ".agents/skills", "magpie-list-skills", name="magpie-list-skills", family="utilities"
        )
        cache = self.tmp / "home" / ".claude" / "plugins" / "cache" / "apache-magpie"
        write_skill(
            cache / "magpie-utilities" / "0.2.0" / "skills",
            "list-skills",
            name="magpie-list-skills",
            family="utilities",
        )
        script = (
            cache / "magpie-utilities" / "0.2.0" / "skills" / "list-skills" / "scripts" / "list_skills.py"
        )
        script.parent.mkdir(parents=True)
        script.touch()

        rows = list_skills.collect_rows(root, script)
        self.assertEqual(
            sorted(r["invocation"] for r in rows),
            ["/magpie-list-skills", "/magpie-utilities:list-skills"],
        )


class RenderTest(unittest.TestCase):
    def test_render_groups_by_family_and_reports_sources(self) -> None:
        rows = [
            {
                "invocation": "/magpie-setup",
                "family": "setup",
                "description": "A.",
                "source": "repository (.agents/skills)",
            },
            {
                "invocation": "/magpie-write-skill",
                "family": "utilities",
                "description": "B.",
                "source": "repository (.agents/skills)",
            },
        ]
        out = list_skills.render(rows, verbose=False)
        self.assertIn("Skills installed for this repository (2 total)", out)
        self.assertIn("setup/  (1)", out)
        self.assertIn("utilities/  (1)", out)
        self.assertIn("Installed from:", out)
        self.assertIn("2  repository (.agents/skills)", out)

    def test_verbose_puts_description_on_its_own_line(self) -> None:
        rows = [
            {
                "invocation": "/magpie-setup",
                "family": "setup",
                "description": "A.",
                "source": "repository (.agents/skills)",
            }
        ]
        out = list_skills.render(rows, verbose=True)
        self.assertIn("  /magpie-setup\n      A.", out)


class MainTest(unittest.TestCase):
    def test_empty_repository_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list_skills.main(["--root", tmp]), 1)


if __name__ == "__main__":
    unittest.main()
