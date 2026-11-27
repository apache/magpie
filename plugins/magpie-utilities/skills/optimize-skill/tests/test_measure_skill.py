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
"""Tests for scripts/measure_skill.py."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure_skill

SKILL = (
    """---
name: tidy
description: >-
  Tidy the changelog.
when_to_use: When the changelog is messy.
---

# tidy

<!-- BEGIN MAGPIE PREFLIGHT -->
"""
    + "x" * 4000
    + """
<!-- END MAGPIE PREFLIGHT -->

Body text.
"""
)


class MeasureSkillTest(unittest.TestCase):
    def _write(self, text: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "tidy" / "SKILL.md"
        path.parent.mkdir()
        path.write_text(text)
        return path

    def test_always_on_counts_the_listing_line(self) -> None:
        """``name: description - when_to_use``, separators included, divided by four."""
        always_on, _, problems = measure_skill.measure(self._write(SKILL))
        listing = "tidy: Tidy the changelog. - When the changelog is messy."
        self.assertEqual(always_on, len(listing) // 4)
        self.assertEqual(problems, [])

    def test_body_leaves_out_the_preflight_block(self) -> None:
        _, body, _ = measure_skill.measure(self._write(SKILL))
        self.assertLess(body, 100)

    def test_flags_missing_frontmatter_and_name(self) -> None:
        _, _, no_frontmatter = measure_skill.measure(self._write("# tidy\n"))
        _, _, no_name = measure_skill.measure(self._write("---\ndescription: x\n---\n\nbody\n"))
        self.assertTrue(no_frontmatter and "no frontmatter" in no_frontmatter[0])
        self.assertTrue(no_name and "no name" in no_name[0])

    def test_main_searches_a_directory_and_fails_on_a_problem(self) -> None:
        good = self._write(SKILL)
        bad = good.parent.parent / "broken" / "SKILL.md"
        bad.parent.mkdir()
        bad.write_text("no frontmatter\n")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = measure_skill.main([str(good.parent.parent)])
        self.assertEqual(rc, 1)
        self.assertIn("tidy/SKILL.md", out.getvalue())
        self.assertIn("no frontmatter", err.getvalue())


if __name__ == "__main__":
    unittest.main()
