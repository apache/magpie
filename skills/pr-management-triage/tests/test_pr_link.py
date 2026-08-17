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

import pr_link


class PrLinkTest(unittest.TestCase):
    def test_short_reference_uses_canonical_target(self) -> None:
        rendered = pr_link.format_pr_reference("example/widget#66444", {"TERM": "xterm-256color"})

        self.assertEqual(
            rendered,
            "\033]8;;https://github.com/example/widget/pull/66444\033\\example/widget#66444\033]8;;\033\\",
        )

    def test_url_reference_is_normalised(self) -> None:
        rendered = pr_link.format_pr_reference(
            "https://github.com/example/widget/pull/66444/",
            {"TERM": "xterm-256color"},
        )

        self.assertEqual(
            rendered,
            "\033]8;;https://github.com/example/widget/pull/66444\033\\"
            "https://github.com/example/widget/pull/66444\033]8;;\033\\",
        )

    def test_number_reference_uses_repository_context(self) -> None:
        rendered = pr_link.format_pr_reference(
            "#66444",
            {"TERM": "xterm-256color"},
            repository="example/widget",
        )

        self.assertEqual(
            rendered,
            "\033]8;;https://github.com/example/widget/pull/66444\033\\#66444\033]8;;\033\\",
        )

    def test_no_color_uses_plain_text_fallback(self) -> None:
        rendered = pr_link.format_pr_reference(
            "example/widget#66444", {"TERM": "xterm-256color", "NO_COLOR": ""}
        )

        self.assertEqual(
            rendered,
            "example/widget#66444  https://github.com/example/widget/pull/66444",
        )

    def test_dumb_terminal_uses_plain_text_fallback(self) -> None:
        rendered = pr_link.format_pr_reference("example/widget#66444", {"TERM": "dumb"})

        self.assertEqual(
            rendered,
            "example/widget#66444  https://github.com/example/widget/pull/66444",
        )

    def test_missing_term_uses_plain_text_fallback(self) -> None:
        rendered = pr_link.format_pr_reference("example/widget#66444", {})

        self.assertEqual(
            rendered,
            "example/widget#66444  https://github.com/example/widget/pull/66444",
        )

    def test_plain_url_is_not_duplicated(self) -> None:
        rendered = pr_link.format_pr_reference(
            "https://github.com/example/widget/pull/66444", {"TERM": "dumb"}
        )

        self.assertEqual(rendered, "https://github.com/example/widget/pull/66444")

    def test_non_pr_reference_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            pr_link.format_pr_reference(
                "https://github.com/example/widget/issues/66444",
                {"TERM": "xterm-256color"},
            )

    def test_number_reference_without_repository_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            pr_link.format_pr_reference("#66444", {"TERM": "xterm-256color"})


if __name__ == "__main__":
    unittest.main()
