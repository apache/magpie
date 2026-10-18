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

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from pr_management.stack_review import stack_ledger


def _file_diff(path: str, hunks: list[tuple[list[str], list[str]]], status: str = "M") -> str:
    """Render one file's unified diff from (removed, added) line pairs."""
    out = [f"diff --git a/{path} b/{path}"]
    if status == "A":
        out.append("new file mode 100644")
    elif status == "D":
        out.append("deleted file mode 100644")
    out += [f"--- a/{path}", f"+++ b/{path}"]
    line_no = 1
    for removed, added in hunks:
        out.append(f"@@ -{line_no},{len(removed)} +{line_no},{len(added)} @@")
        out += [f"-{line}" for line in removed]
        out += [f"+{line}" for line in added]
        line_no += 20
    return "\n".join(out) + "\n"


def _union_fix(name: str) -> tuple[list[str], list[str]]:
    """The hunk a typing codemod leaves in every file it touches."""
    return ([f"    {name}: Optional[str] = None"], [f"    {name}: str | None = None"])


def _hunk(path: str, start: int, removed: list[str], added: list[str]) -> stack_ledger.Hunk:
    return stack_ledger.Hunk(
        path, start, max(len(added), 1), [f"-{x}" for x in removed] + [f"+{x}" for x in added]
    )


def _layers(*diffs: str) -> dict[int, list[stack_ledger.FileDiff]]:
    return {i + 1: stack_ledger.parse_unified_diff(d) for i, d in enumerate(diffs)}


class ParseTest(unittest.TestCase):
    def test_parses_files_hunks_and_statuses(self) -> None:
        text = _file_diff("a.py", [(["x = 1"], ["x = 2"])]) + _file_diff(
            "b.py", [([], ["y = 1"])], status="A"
        )
        text += _file_diff("old.py", [(["z = 1"], [])], status="D")
        files = stack_ledger.parse_unified_diff(text)
        self.assertEqual(
            [(f.path, f.status, len(f.hunks)) for f in files],
            [("a.py", "M", 1), ("b.py", "A", 1), ("old.py", "D", 1)],
        )
        self.assertEqual(files[0].hunks[0].removed, ["x = 1"])
        self.assertEqual(files[0].hunks[0].added, ["x = 2"])
        self.assertEqual(files[0].hunks[0].ref, "a.py:1")

    def test_content_lines_starting_with_dashes_are_kept(self) -> None:
        text = "diff --git a/q.sql b/q.sql\n--- a/q.sql\n+++ b/q.sql\n@@ -1,2 +1,2 @@\n--- old comment\n+++ new marker\n ctx\n"
        files = stack_ledger.parse_unified_diff(text)
        self.assertEqual(files[0].hunks[0].removed, ["-- old comment"])
        self.assertEqual(files[0].hunks[0].added, ["++ new marker"])
        self.assertEqual(files[0].hunks[0].span, "q.sql:1-2")

    def test_binary_and_rename_headers(self) -> None:
        text = "diff --git a/img.png b/img.png\nBinary files a/img.png and b/img.png differ\n"
        text += "diff --git a/x.py b/y.py\nsimilarity index 90%\nrename from x.py\nrename to y.py\n"
        files = stack_ledger.parse_unified_diff(text)
        self.assertTrue(files[0].binary)
        self.assertEqual((files[1].status, files[1].old_path, files[1].path), ("R", "x.py", "y.py"))


class ShapeTest(unittest.TestCase):
    def test_skeleton_masks_identifiers_numbers_strings_and_comma_lists(self) -> None:
        self.assertEqual(
            stack_ledger.skeleton('  from typing import Optional  # "x" 42'), 'from _ import _ # "" 0'
        )
        self.assertEqual(stack_ledger.skeleton("return foo(bar, 3)"), "return _(_, 0)")
        # Import arity does not split shapes: one name or three is the same rewrite.
        self.assertEqual(
            stack_ledger.skeleton("from datetime import datetime, timezone"), "from _ import _,+"
        )
        self.assertEqual(
            stack_ledger.skeleton("from datetime import UTC, datetime, tzinfo"), "from _ import _,+"
        )

    def test_same_rewrite_on_different_names_and_counts_shares_a_shape(self) -> None:
        a = _hunk("a.py", 1, *_union_fix("alpha"))
        b = _hunk("b.py", 7, *_union_fix("beta_gamma"))
        two = _hunk(
            "c.py",
            7,
            ["    x: Optional[str] = None", "    y: Optional[str] = None"],
            ["    x: str | None = None", "    y: str | None = None"],
        )
        other = _hunk("d.py", 7, ["def helper():"], ["def helper(x):"])
        self.assertEqual(stack_ledger.hunk_shape(a), stack_ledger.hunk_shape(b))
        self.assertEqual(stack_ledger.hunk_shape(a), stack_ledger.hunk_shape(two))
        self.assertNotEqual(stack_ledger.hunk_shape(a), stack_ledger.hunk_shape(other))


class ClassifyTest(unittest.TestCase):
    def test_classes(self) -> None:
        globs = stack_ledger.DEFAULT_GENERATED_GLOBS
        cases = {
            "dev/doc/images/output_shell.svg": "generated",
            "uv.lock": "generated",
            "generated/PYPI_README.md": "generated",
            "svc/internal/types.gen.go": "generated",
            "pkg/models_generated.py": "generated",
            "web/package-lock.json": "generated",
            "svc/go.sum": "generated",
            # A directory a project uses for hand-written code is never generated by default.
            "core/src/api/datamodels/dag_run.py": "source",
            "core/tests/unit/api/datamodels/test_dag_run.py": "test",
            "core/newsfragments/123.significant.rst": "release-note",
            "CHANGELOG.md": "release-note",
            "pkg/tests/unit/test_x.py": "test",
            "docs/guide.rst": "docs",
            "pkg/pyproject.toml": "config",
            "pkg/src/mod.py": "source",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(stack_ledger.classify_path(path, globs), expected)

    def test_gitattributes_generated_entries_are_honoured(self) -> None:
        text = "*.svg linguist-generated\n# comment\ndocs/api/** linguist-generated=true\n*.py diff=python\n"
        self.assertEqual(stack_ledger.parse_gitattributes_generated(text), ["*.svg", "docs/api/**"])


def _codemod_layer(n_files: int = 12, extra: str = "") -> str:
    return "".join(_file_diff(f"pkg/mod{i}.py", [_union_fix(f"field{i}")]) for i in range(n_files)) + extra


class LedgerTest(unittest.TestCase):
    def test_generated_lines_do_not_count_toward_sizing(self) -> None:
        lock = _file_diff(
            "pkg/uv.lock", [([f"v{i} = 1" for i in range(2000)], [f"v{i} = 2" for i in range(2000)])]
        )
        manifest = _file_diff(
            "pkg/pyproject.toml", [(['requires-python = ">=3.10"'], ['requires-python = ">=3.11"'])]
        )
        ledger = stack_ledger.build_ledger(_layers(lock + manifest))
        layer = ledger.layers[0]
        self.assertEqual((layer.changed_lines, layer.generated_lines), (2, 4000))
        self.assertEqual((layer.hunks, layer.generated_hunks), (1, 1))
        self.assertEqual(layer.generated_files, ["pkg/uv.lock"])
        self.assertEqual(layer.plan, "full")
        self.assertEqual(layer.planned_hunks, 1)  # the lock hunk is counted, never planned

    def test_mechanical_layer_flags_the_hand_edit_as_outlier(self) -> None:
        hand_edit = _file_diff(
            "pkg/pyproject.toml", [(['requires-python = ">=3.10"'], ['requires-python = ">=3.11"'])]
        )
        ledger = stack_ledger.build_ledger(_layers(_codemod_layer(extra=hand_edit)))
        layer = ledger.layers[0]
        self.assertTrue(layer.mechanical)
        self.assertEqual(layer.outliers, ["pkg/pyproject.toml:1"])
        self.assertEqual(layer.exemplars, ["pkg/mod0.py:1"])
        # Small enough for a full read: the budget, not the shape, decides the plan.
        self.assertEqual(layer.plan, "full")

    def test_small_semantic_layer_is_read_in_full_and_generated_only_layer_is_skipped(self) -> None:
        semantic = _file_diff("pkg/a.py", [(["def f():", "    return 1"], ["def f(x):", "    return x"])])
        semantic += _file_diff("pkg/b.py", [(["import os"], [])])
        generated = _file_diff("docs/out.svg", [(["<svg>"], ["<svg a>"])]) + _file_diff(
            "uv.lock", [(["v=1"], ["v=2"])]
        )
        ledger = stack_ledger.build_ledger(_layers(semantic, generated))
        self.assertEqual(
            [(layer.plan, layer.planned_hunks) for layer in ledger.layers], [("full", 2), ("skip", 0)]
        )
        self.assertFalse(ledger.layers[1].mechanical)

    def test_budget_demotes_mechanical_layers_first_and_plans_exemplars_outliers_and_off_theme(self) -> None:
        semantic = "".join(
            _file_diff(
                f"pkg/m{i}.py",
                [
                    (
                        [f"def f{i}_{j}(): pass" for j in range(i + 1)],
                        [f"def g{i}_{j}(): pass" for j in range(i + 1)],
                    )
                ],
            )
            for i in range(10)
        )  # 110 hand-written lines, every hunk its own shape
        mechanical = _codemod_layer(
            60, extra=_file_diff("docs/guide.rst", [(["Python 3.10"], ["Python 3.11"])])
        )  # 122 lines
        ledger = stack_ledger.build_ledger(_layers(mechanical, semantic), read_budget=150)
        mech, sem = ledger.layers
        self.assertEqual(sem.plan, "full")
        self.assertEqual(mech.plan, "exemplar")
        self.assertIn("read budget of 150 lines exhausted", mech.plan_reason)
        self.assertEqual(mech.outliers, ["docs/guide.rst:1"])
        self.assertEqual(mech.dir_outliers, ["docs/guide.rst"])
        # exemplar + outlier + off-theme hunk, de-duplicated: the outlier and the off-theme file are the same hunk.
        self.assertEqual(mech.planned_hunks, 2)
        self.assertEqual(mech.outliers_planned, 1)
        self.assertEqual(mech.planned_hunk_refs, ["docs/guide.rst:1", "pkg/mod0.py:1"])

    def test_hand_written_demoted_layer_ranks_outliers_within_its_budget_share(self) -> None:
        def big_layer(prefix: str) -> str:
            # 40 hunks, all distinct shapes, mixed classes; every hunk is an outlier.
            parts = []
            for i in range(40):
                klass = ["src", "docs", "tests", "config"][i % 4]
                path = {
                    "src": f"src/pkg/{prefix}_m{i}.py",
                    "docs": f"docs/{prefix}_d{i}.rst",
                    "tests": f"tests/test_{prefix}_t{i}.py",
                    "config": f"conf/{prefix}_c{i}.toml",
                }[klass]
                lines = ["a" + ".b" * (i + 100 * len(prefix)) + f" # {prefix}"]
                parts.append(_file_diff(path, [(lines, [line + ".c" for line in lines])]))
            return "".join(parts)

        # A large overlap file (Tier A, never cut) and one oversize source outlier sit in both layers.
        shared = _file_diff(
            "src/pkg/shared.py", [([f"x{j} = 1" for j in range(30)], [f"x{j} = 2" for j in range(30)])]
        )

        def huge(prefix: str) -> str:
            # Its own shape (`_ = _(0)`), so it is a 50-line outlier and not a sibling of the overlap file's `_ = 0`.
            return _file_diff(
                f"src/pkg/huge_{prefix}.py",
                [
                    (
                        [f"h{prefix}{j} = compute(1)" for j in range(25)],
                        [f"h{prefix}{j} = compute(2)" for j in range(25)],
                    )
                ],
            )

        ledger = stack_ledger.build_ledger(
            _layers(big_layer("one") + shared + huge("one"), big_layer("two") + shared + huge("two")),
            read_budget=40,
        )
        first, second = ledger.layers
        self.assertFalse(first.mechanical)
        self.assertEqual((first.plan, second.plan), ("exemplar", "exemplar"))
        # Both hand-written layers are demoted by the budget; each gets half of the 40 lines, and Tier A does not eat it.
        self.assertEqual(first.outlier_share, 20)
        self.assertIn(
            "src/pkg/shared.py:1", first.planned_hunk_refs
        )  # overlap file: Tier A, 60 lines, outside the share
        self.assertEqual(first.overlap_hunks, 1)
        # Small source outliers fit the 20-line share (2 lines each); the 50-line hunk is skipped, not a stopper.
        planned_sources = [r for r in first.planned_hunk_refs if r.startswith("src/pkg/one_m")]
        self.assertEqual(len(planned_sources), 10)
        self.assertNotIn("src/pkg/huge_one.py:1", first.planned_hunk_refs)
        self.assertEqual([r for r in first.planned_hunk_refs if r.startswith("docs/")], [])
        text = stack_ledger.render(ledger)
        self.assertIn("ranked source > config > test > docs, smallest first, within a 20-line share", text)
        # The overlap hunk is an outlier too, but Tier A read it: it is not counted as share-bought.
        self.assertEqual(first.outliers_in_share, 10)
        self.assertIn(
            "outliers 10 of 42 (ranked source > config > test > docs, smallest first, within a 20-line share; 1 more already read as overlap or off-theme)",
            text,
        )

    def test_generated_lock_without_suffix_fires_the_duplicate_detector_and_is_listed(self) -> None:
        lock = _file_diff("web/package-lock.json", [(['"version": "1"'], ['"version": "2"'])])
        manifest = _file_diff("web/package.json", [(['"name": "a"'], ['"name": "b"'])])
        ledger = stack_ledger.build_ledger(_layers(lock + manifest, lock))
        self.assertEqual(
            ledger.detectors["generated_in_several_layers"],
            [{"path": "web/package-lock.json", "layers": [1, 2]}],
        )
        self.assertEqual(ledger.layers[0].generated_files, ["web/package-lock.json"])
        self.assertEqual(ledger.touched_files, ["web/package-lock.json", "web/package.json"])
        self.assertIn("Generated or binary files (counted, never read)", stack_ledger.render(ledger))
        self.assertIn("- layer 1: `web/package-lock.json`", stack_ledger.render(ledger))

    def test_per_layer_limit_demotes_a_big_semantic_layer(self) -> None:
        def unique_line(k: int) -> str:
            return "a" + ".b" * k  # every attribute chain has its own skeleton

        big = "".join(
            _file_diff(
                f"pkg/m{i}.py",
                [
                    (
                        [unique_line(i * 61 + j) for j in range(i + 1)],
                        [unique_line(i * 61 + j) + ".c" for j in range(i + 1)],
                    )
                ],
            )
            for i in range(60)
        )  # 3660 hand-written lines, no repeated shape anywhere
        ledger = stack_ledger.build_ledger(_layers(big), read_budget=10_000)
        layer = ledger.layers[0]
        self.assertFalse(layer.mechanical)
        self.assertEqual(layer.plan, "exemplar")
        self.assertIn("exceed the per-layer limit of 1500", layer.plan_reason)
        self.assertEqual(len(layer.outliers), 60)  # every singleton hunk listed, smallest first
        self.assertEqual(layer.outliers[0], "pkg/m0.py:1")
        # Demoted by the per-layer limit, so the whole 10,000 budget is its share: everything fits.
        self.assertEqual(layer.outliers_planned, 60)
        deeper = stack_ledger.build_ledger(_layers(big), read_budget=10_000, full_read_max_lines=4000)
        self.assertEqual(deeper.layers[0].plan, "full")
        tight = stack_ledger.build_ledger(_layers(big), read_budget=300)
        self.assertLess(tight.layers[0].outliers_planned, 60)
        self.assertLessEqual(tight.layers[0].planned_lines, 300)

    def test_overlap_and_detectors(self) -> None:
        layer1 = _file_diff("core/newsfragments/1.rst", [([], ["Drop 3.10"])], status="A")
        layer1 += _file_diff("pkg/shared.py", [(["A = 1"], ["A = 2"])])
        layer1 += _file_diff("pkg/uv.lock", [(["lock v1"], ["lock v2"])])
        layer2 = _file_diff("core/newsfragments/1.rst", [(["Drop 3.10"], ["Drop Python 3.10"])])
        layer2 += _file_diff("pkg/shared.py", [(["A = 2"], ["A = 3"])])
        layer2 += _file_diff("pkg/pyproject.toml", [(["x = 1"], ["x = 2"])])
        layer3 = _file_diff("pkg/uv.lock", [(["lock v2"], ["lock v3"])]) + _file_diff(
            "pkg/pyproject.toml", [(["x = 2"], ["x = 3"])]
        )
        ledger = stack_ledger.build_ledger(_layers(layer1, layer2, layer3))
        self.assertEqual(ledger.distinct_files, 4)
        self.assertEqual(
            ledger.overlap,
            {
                "core/newsfragments/1.rst": [1, 2],
                "pkg/pyproject.toml": [2, 3],
                "pkg/shared.py": [1, 2],
                "pkg/uv.lock": [1, 3],
            },
        )
        self.assertEqual(ledger.overlap_pairs, {"1+2": 2, "2+3": 1, "1+3": 1})
        self.assertEqual(
            ledger.detectors["release_note_in_several_layers"],
            [{"path": "core/newsfragments/1.rst", "layers": [1, 2]}],
        )
        self.assertEqual(
            ledger.detectors["generated_in_several_layers"], [{"path": "pkg/uv.lock", "layers": [1, 3]}]
        )
        # The lock moved in layer 1 while its manifest only moved in layers 2 and 3.
        self.assertEqual(
            ledger.detectors["lock_without_manifest"],
            [{"path": "pkg/uv.lock", "layer": 1, "manifest_layers": [2, 3]}],
        )
        self.assertIn("pkg/uv.lock", ledger.read_fully_files)

    def test_render_lists_every_layer_overlap_and_exemplar_details(self) -> None:
        layer1 = _file_diff("pkg/a.py", [(["x = 1"], ["x = 2"])])
        layer2 = _codemod_layer(60, extra=_file_diff("pkg/a.py", [(["x = 2"], ["x = 3"])]))
        text = stack_ledger.render(stack_ledger.build_ledger(_layers(layer1, layer2), read_budget=50))
        self.assertIn("| 1 | 1 | 2 | 0 | 1 | no | full | 1 |", text)
        self.assertIn("`pkg/a.py` — layers 1, 2", text)
        self.assertIn("Hand-written hunks planned: 3 of 62 (6 of 124 hand-written lines)", text)
        self.assertIn(
            "Layer 2: 1 exemplar hunks, outliers 0 of 1 (all read: in a mechanical layer every outlier is a hand edit; 1 more already read as overlap or off-theme), 1 overlap-file hunks",
            text,
        )
        self.assertIn("- `pkg/a.py:1`", text)


class CliTest(unittest.TestCase):
    def test_ledger_then_render_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d1 = Path(tmp, "1.diff")
            d1.write_text(_file_diff("pkg/a.py", [(["x = 1"], ["x = 2"])]), encoding="utf-8")
            attrs = Path(tmp, ".gitattributes")
            attrs.write_text("pkg/a.py linguist-generated\n", encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                stack_ledger.main(
                    [
                        "ledger",
                        "--layer",
                        f"1={d1}",
                        "--gitattributes",
                        str(attrs),
                        "--full-read-max-lines",
                        "900",
                    ]
                )
            data = json.loads(out.getvalue())
            self.assertEqual(data["layers"][0]["classes"], {"generated": 1})
            self.assertEqual(data["layers"][0]["plan"], "skip")
            self.assertEqual(data["full_read_max_lines"], 900)
            ledger_json = Path(tmp, "ledger.json")
            ledger_json.write_text(out.getvalue(), encoding="utf-8")
            rendered = io.StringIO()
            with redirect_stdout(rendered):
                stack_ledger.main(["render", str(ledger_json)])
            self.assertIn("generated or binary files only", rendered.getvalue())

    def test_hunks_prints_planned_hunks_with_new_side_line_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d1 = Path(tmp, "1.diff")
            d1.write_text(
                "diff --git a/pkg/a.py b/pkg/a.py\n--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -10,3 +10,3 @@\n ctx\n-old = 1\n+new = 2\n",
                encoding="utf-8",
            )
            out = io.StringIO()
            with redirect_stdout(out):
                stack_ledger.main(["ledger", "--layer", f"1={d1}"])
            ledger_json = Path(tmp, "ledger.json")
            ledger_json.write_text(out.getvalue(), encoding="utf-8")
            hunks = io.StringIO()
            with redirect_stdout(hunks):
                stack_ledger.main(["hunks", str(ledger_json), "--layer", f"1={d1}"])
            self.assertEqual(
                hunks.getvalue().splitlines(),
                ["### 1:pkg/a.py:10-12 (outlier)", "    10  |ctx", "      -|old = 1", "    11 +|new = 2", ""],
            )


if __name__ == "__main__":
    unittest.main()
