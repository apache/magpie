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
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import retention

TWO_X = [{"label": "2.x", "pattern": "2.x"}]


class SortTest(unittest.TestCase):
    def test_numeric_not_lexical(self) -> None:
        self.assertEqual(
            sorted(["2.10.0", "2.9.0", "2.11.0"], key=retention.version_key), ["2.9.0", "2.10.0", "2.11.0"]
        )

    def test_prerelease_before_final_and_post_after(self) -> None:
        self.assertEqual(
            sorted(["3.0.0.post1", "3.0.0", "3.0.0rc1"], key=retention.version_key),
            ["3.0.0rc1", "3.0.0", "3.0.0.post1"],
        )

    def test_listing_drops_slash_and_separates_non_versions(self) -> None:
        self.assertEqual(retention.parse_listing("2.10.0/\nKEYS\n\nproviders/\n"), (["2.10.0"], ["KEYS", "providers"]))


class SweepTest(unittest.TestCase):
    def test_single_line(self) -> None:
        out = retention.sweep(["2.11.0", "2.10.0"], TWO_X)
        self.assertEqual(out["releases_found"], ["2.10.0", "2.11.0"])
        self.assertEqual(out["past_retention"], ["2.10.0"])
        self.assertEqual(out["latest_of_each_line"], {"2.x": "2.11.0"})
        self.assertFalse(out["handoff_required"])
        self.assertEqual(out["handoff_reasons"], [])

    def test_multi_line(self) -> None:
        trains = TWO_X + [{"label": "3.x", "pattern": "3.x"}]
        out = retention.sweep(["2.9.0", "2.10.0", "2.11.0", "3.0.0", "3.0.1"], trains)
        self.assertEqual(out["past_retention"], ["2.9.0", "2.10.0", "3.0.0"])
        self.assertEqual(out["latest_of_each_line"], {"2.x": "2.11.0", "3.x": "3.0.1"})

    def test_orphan_listed_never_archived(self) -> None:
        out = retention.sweep(["2.10.0", "2.11.0", "1.10.15"], TWO_X)
        self.assertEqual(out["orphans"], ["1.10.15"])
        self.assertNotIn("1.10.15", out["past_retention"])
        self.assertTrue(out["handoff_required"])
        self.assertIn("1.10.15", out["handoff_reasons"][0])

    def test_keep_two(self) -> None:
        out = retention.sweep(["2.9.0", "2.10.0", "2.11.0"], [{"label": "2.x", "pattern": "2.x", "keep": 2}])
        self.assertEqual(out["past_retention"], ["2.9.0"])

    def test_keep_zero_is_retention_rule_error(self) -> None:
        out = retention.sweep(["2.10.0", "2.11.0"], [{"label": "2.x", "pattern": "2.x", "keep": 0}])
        self.assertTrue(out["retention_rule_error"])
        self.assertEqual(out["past_retention"], [])
        self.assertTrue(out["handoff_required"])

    def test_loose_pattern_goes_unmapped(self) -> None:
        out = retention.sweep(["1.0.0", "2.0.0"], [{"label": "LTS", "pattern": "long-term support line"}])
        self.assertEqual([u["version"] for u in out["unmapped"]], ["1.0.0", "2.0.0"])
        self.assertFalse(out["mapping_complete"])
        self.assertEqual(out["orphans"], [])

    def test_explicit_versions_resolve_loose_train(self) -> None:
        out = retention.sweep(["1.0.0", "1.1.0", "2.0.0"], [{"label": "LTS", "versions": ["1.0.0", "1.1.0"]}])
        self.assertEqual(out["past_retention"], ["1.0.0"])
        self.assertEqual(out["orphans"], ["2.0.0"])

    def test_overlapping_patterns_go_unmapped(self) -> None:
        trains = TWO_X + [{"label": "2.11", "pattern": "2.11.x"}]
        out = retention.sweep(["2.11.0"], trains)
        self.assertEqual(out["unmapped"][0]["version"], "2.11.0")


class PrereleaseTest(unittest.TestCase):
    """A pre-release in the release area never decides what is kept."""

    def test_rc_never_displaces_the_latest_release(self) -> None:
        out = retention.sweep(["2.10.5", "2.11.0-rc1", "2.10.4"], TWO_X)
        self.assertEqual(out["latest_of_each_line"], {"2.x": "2.10.5"})
        self.assertEqual(out["past_retention"], ["2.10.4"])
        self.assertNotIn("2.10.5", out["past_retention"])
        self.assertNotIn("2.11.0-rc1", out["past_retention"])

    def test_prerelease_is_handed_to_the_rm(self) -> None:
        out = retention.sweep(["2.10.5", "2.11.0rc1"], TWO_X)
        self.assertEqual(out["prereleases"], ["2.11.0rc1"])
        self.assertTrue(out["handoff_required"])
        self.assertTrue(any("2.11.0rc1" in r and "pre-release" in r for r in out["handoff_reasons"]))

    def test_post_release_still_counts_as_a_release(self) -> None:
        out = retention.sweep(["2.10.5", "2.10.5.post1"], TWO_X)
        self.assertEqual(out["latest_of_each_line"], {"2.x": "2.10.5.post1"})
        self.assertEqual(out["prereleases"], [])


if __name__ == "__main__":
    unittest.main()
