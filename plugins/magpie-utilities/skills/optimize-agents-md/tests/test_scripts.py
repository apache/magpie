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

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure
import nest
import rule_inventory

BEFORE = """\
# Agents

<!-- START doctoc -->
- [Commits](#commits)
<!-- END doctoc -->

## Commits

Never add a co-author trailer.
Keep messages short.
Commits land on main.

## Releases

Always sign the tag before pushing it.

- Run the link check.
- **Verify the hook** before every commit.
- The changelog lives in docs/.

```bash
git tag -s v1
```
"""


class MeasureTest(unittest.TestCase):
    def test_counts_toc_code_and_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENTS.md"
            path.write_text(BEFORE, encoding="utf-8")
            report = measure.measure(path)
        self.assertEqual(report.chars, len(BEFORE))
        self.assertFalse(report.over_harness_warning)
        self.assertGreater(report.toc_chars, 0)
        self.assertEqual(report.code_blocks, 1)
        self.assertEqual([s["heading"] for s in report.sections], ["Releases", "Commits"])

    def test_reports_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "extra.md").write_text("x" * 40, encoding="utf-8")
            path = Path(tmp) / "CLAUDE.md"
            path.write_text("@extra.md\n@missing.md\n", encoding="utf-8")
            report = measure.measure(path)
        self.assertEqual(
            [(i["path"], i["chars"]) for i in report.imports],
            [("extra.md", 40), ("missing.md", None)],
        )


class RuleInventoryTest(unittest.TestCase):
    def run_inventory(self, after: str, extra: dict[str, str] | None = None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "before.md").write_text(BEFORE, encoding="utf-8")
            (root / "AGENTS.md").write_text(after, encoding="utf-8")
            for name, text in (extra or {}).items():
                (root / name).write_text(text, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = rule_inventory.main(
                    ["--before", str(root / "before.md"), "--after", str(root / "AGENTS.md"), "--json"]
                )
        return code, json.loads(out.getvalue())

    def test_extracts_normative_and_imperative_prose_only(self) -> None:
        self.assertEqual(
            rule_inventory.rules(BEFORE),
            [
                "Never add a co-author trailer.",
                "Keep messages short.",
                "Always sign the tag before pushing it.",
                "Run the link check.",
                "**Verify the hook** before every commit.",
            ],
        )

    def test_imperative_detection(self) -> None:
        for sentence in ("Run it.", "`Re-run` the hook.", "**Check** the TOC.", "Use `gh browse`."):
            self.assertTrue(rule_inventory.is_imperative(sentence), sentence)
        for sentence in ("The hook runs on commit.", "Commits land on main.", "- Plain fact."):
            self.assertFalse(rule_inventory.is_imperative(sentence), sentence)

    def test_unchanged_file_keeps_everything(self) -> None:
        code, result = self.run_inventory(BEFORE)
        self.assertEqual(code, 0)
        self.assertEqual((result["kept"], result["missing"]), (5, []))

    def test_rewrapped_rule_still_counts_as_kept(self) -> None:
        code, result = self.run_inventory(BEFORE.replace("Always sign the tag", "Always sign\nthe tag"))
        self.assertEqual(code, 0)
        self.assertEqual(result["kept"], 5)

    def test_rule_moved_behind_a_link_is_reported_as_moved(self) -> None:
        head, releases = BEFORE.split("## Releases\n")
        after = head + "## Releases\n\nBefore tagging, read [releasing](docs-releasing.md).\n"
        code, result = self.run_inventory(after, {"docs-releasing.md": "# Releasing\n" + releases})
        self.assertEqual(code, 0)
        self.assertEqual(len(result["moved"]), 3)
        self.assertTrue(all(m["to"].endswith("docs-releasing.md") for m in result["moved"]))

    def test_dropped_rule_is_missing_and_fails(self) -> None:
        code, result = self.run_inventory(BEFORE.replace("Never add a co-author trailer.\n", ""))
        self.assertEqual(code, 1)
        self.assertEqual(result["missing"], ["Never add a co-author trailer."])

    def test_dropped_plain_command_is_missing(self) -> None:
        # The gap a normative-words-only check had: no "must", still a rule.
        code, result = self.run_inventory(BEFORE.replace("- Run the link check.\n", ""))
        self.assertEqual(code, 1)
        self.assertEqual(result["missing"], ["Run the link check."])


NESTED_ROOT = """\
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Agents

## Commits

Never push to main.

## Writing tools

Run the `tools/foo/` tests; see [docs](docs/x.md) and [above](#commits).
Keep `tools/foo/pyproject.toml` tidy.

### Tool READMEs

Use the template.

## Other

Check links.
"""


class NestTest(unittest.TestCase):
    def make_repo(self, tmp: str, inbound: bool = False, claude_link: bool = False) -> Path:
        root = Path(tmp)
        (root / "tools/foo").mkdir(parents=True)
        (root / "tools/foo/pyproject.toml").write_text("", encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs/x.md").write_text(
            "see [w](../AGENTS.md#writing-tools)\n" if inbound else "docs\n", encoding="utf-8"
        )
        (root / "AGENTS.md").write_text(NESTED_ROOT, encoding="utf-8")
        if claude_link:
            (root / "CLAUDE.md").symlink_to("AGENTS.md")
        return root

    def test_suggest_finds_the_subtree_section_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp)
            found = nest.suggest(root / "AGENTS.md", min_refs=2)
        self.assertEqual([(c["heading"], c["dir"]) for c in found], [("Writing tools", "tools/foo")])

    def test_apply_creates_nested_file_and_rewrites_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp)
            plan = nest.apply(root / "AGENTS.md", "Writing tools", "tools", pointer=False, dry_run=False)
            nested = (root / "tools/AGENTS.md").read_text(encoding="utf-8")
            after = (root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(plan["nested_created"])
        self.assertFalse(plan["root_keeps_pointer"])
        self.assertTrue(nested.startswith("<!-- SPDX-License-Identifier: Apache-2.0 -->\n\n# AGENTS"))
        self.assertIn("[docs](../docs/x.md) and [above](../AGENTS.md#commits)", nested)
        self.assertIn("### Tool READMEs\n\nUse the template.", nested)
        self.assertNotIn("Writing tools", after)
        self.assertIn("## Other", after)

    def test_inbound_anchor_keeps_a_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp, inbound=True, claude_link=True)
            plan = nest.apply(root / "AGENTS.md", "Writing tools", "tools", pointer=False, dry_run=False)
            after = (root / "AGENTS.md").read_text(encoding="utf-8")
            mirrored = (root / "tools/CLAUDE.md").is_symlink()
        self.assertEqual(plan["inbound_links"], ["docs/x.md"])
        self.assertIn(
            "## Writing tools\n\nWhen working under `tools/`, read [`tools/AGENTS.md`](tools/AGENTS.md#writing-tools).",
            after,
        )
        self.assertTrue(mirrored)

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp)
            nest.apply(root / "AGENTS.md", "Writing tools", "tools", pointer=False, dry_run=True)
            self.assertFalse((root / "tools/AGENTS.md").exists())
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), NESTED_ROOT)

    def test_moved_section_passes_the_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp)
            (root / "before.md").write_text(NESTED_ROOT, encoding="utf-8")
            nest.apply(root / "AGENTS.md", "Writing tools", "tools", pointer=False, dry_run=False)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = rule_inventory.main(
                    [
                        "--before",
                        str(root / "before.md"),
                        "--after",
                        str(root / "AGENTS.md"),
                        "--also",
                        str(root / "tools/AGENTS.md"),
                        "--json",
                    ]
                )
            result = json.loads(out.getvalue())
        self.assertEqual(code, 0, result["missing"])
        self.assertEqual(len(result["moved"]), 3)


if __name__ == "__main__":
    unittest.main()
