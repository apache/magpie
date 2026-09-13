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

"""Tests for the pure file-merge core of the ``model_pr.py`` helper.

The create-versus-append branch is the part of the helper that lands text in
someone else's repository, so it is the part held to a test. The git and PR
side effects are exercised by ``--dry-run``.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import model_pr


class LicenseHeaderTest(unittest.TestCase):
    def test_spdx_header_is_prepended_by_default(self) -> None:
        out = model_pr.ensure_license_header("# Threat model\n")
        self.assertTrue(out.startswith("<!-- SPDX-License-Identifier: Apache-2.0"))
        self.assertIn("# Threat model", out)

    def test_apache_full_header_is_prepended_when_requested(self) -> None:
        out = model_pr.ensure_license_header("# Threat model\n", "apache-full")
        self.assertTrue(out.startswith("<!--\nLicensed to the Apache Software Foundation"))

    def test_none_adds_nothing(self) -> None:
        self.assertEqual(model_pr.ensure_license_header("# Threat model\n", "none"), "# Threat model\n")

    def test_existing_header_is_left_alone(self) -> None:
        already = "<!-- SPDX-License-Identifier: Apache-2.0 -->\n\n# Threat model\n"
        self.assertEqual(model_pr.ensure_license_header(already), already)

    def test_prose_mentioning_the_license_still_gets_a_header(self) -> None:
        # The file does not *open* with a licence comment, so a licence checker
        # scanning the top of the file would not find one. A passing mention in
        # the body must not suppress the header.
        body = "# Threat model\n\nThis project is under the Apache License, Version 2.0.\n"
        self.assertTrue(model_pr.ensure_license_header(body).startswith("<!-- SPDX"))


class BranchNameTest(unittest.TestCase):
    def test_default_prefix(self) -> None:
        self.assertEqual(
            model_pr.branch_name("discoverability", "2026-09-08"),
            "security-model/discoverability-2026-09-08",
        )

    def test_custom_prefix(self) -> None:
        self.assertEqual(
            model_pr.branch_name("threat-model", "2026-09-08", "asf-security"),
            "asf-security/threat-model-2026-09-08",
        )


class CloneCmdTest(unittest.TestCase):
    def test_default_branch_is_not_pinned(self) -> None:
        self.assertEqual(
            model_pr.clone_cmd("https://github.com/example/widget.git", None, "/tmp/widget"),
            ["git", "clone", "--depth", "1", "https://github.com/example/widget.git", "/tmp/widget"],
        )

    def test_explicit_base_is_cloned_directly(self) -> None:
        self.assertIn(
            "--branch",
            model_pr.clone_cmd("https://github.com/example/widget.git", "2.x", "/tmp/widget"),
        )


class ModelReferenceTest(unittest.TestCase):
    def test_in_repo_model_is_a_relative_link(self) -> None:
        self.assertEqual(
            model_pr.model_reference("THREAT_MODEL.md", None),
            "[THREAT_MODEL.md](./THREAT_MODEL.md)",
        )

    def test_pointer_is_an_autolink_so_trailing_punctuation_stays_outside(self) -> None:
        ref = model_pr.model_reference(None, "https://example.invalid/THREAT_MODEL.md")
        self.assertEqual(ref, "<https://example.invalid/THREAT_MODEL.md>")


class BuildAgentsMdTest(unittest.TestCase):
    def test_creates_the_file_when_absent(self) -> None:
        out = model_pr.build_agents_md(None, "widget")
        self.assertIn("# Agent guide for widget", out)
        self.assertIn("## Security", out)
        self.assertIn("[SECURITY.md](./SECURITY.md)", out)

    def test_appends_one_section_when_present(self) -> None:
        existing = "# Agent guide\n\n## Build\n\nRun `make`.\n"
        out = model_pr.build_agents_md(existing, "widget")
        self.assertIn("## Build\n\nRun `make`.", out)
        self.assertIn("## Security", out)
        self.assertEqual(out.count("## Security"), 1)

    def test_is_idempotent(self) -> None:
        once = model_pr.build_agents_md("# Agent guide\n", "widget")
        self.assertEqual(model_pr.build_agents_md(once, "widget"), once)

    def test_note_is_appended_to_the_section(self) -> None:
        out = model_pr.build_agents_md(None, "widget", "This repository is build-time tooling.")
        self.assertIn("This repository is build-time tooling.", out)

    def test_created_file_carries_no_header_when_disabled(self) -> None:
        out = model_pr.build_agents_md(None, "widget", license_header="none")
        self.assertTrue(out.startswith("# Agent guide for widget"))


class BuildSecurityMdTest(unittest.TestCase):
    def test_creates_the_file_when_absent(self) -> None:
        out = model_pr.build_security_md(
            None,
            "example/widget",
            "[THREAT_MODEL.md](./THREAT_MODEL.md)",
            report_to="security@example.invalid",
        )
        self.assertIn("# Security policy", out)
        self.assertIn("security@example.invalid", out)
        self.assertIn("## Threat model", out)

    def test_creating_without_a_reporting_address_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            model_pr.build_security_md(None, "example/widget", "<https://example.invalid/m.md>")

    def test_appends_one_section_when_present(self) -> None:
        existing = "# Security Policy\n\nMail us.\n"
        out = model_pr.build_security_md(existing, "example/widget", "<https://example.invalid/m.md>")
        self.assertIn("Mail us.", out)
        self.assertIn("## Threat model", out)

    def test_existing_prose_is_never_edited(self) -> None:
        existing = "# Security Policy\n\nReport to security@example.invalid, not to the issue tracker.\n"
        out = model_pr.build_security_md(existing, "example/widget", "<https://example.invalid/m.md>")
        self.assertTrue(out.startswith(existing.rstrip()))

    def test_is_idempotent(self) -> None:
        once = model_pr.build_security_md(
            "# Security Policy\n", "example/widget", "<https://example.invalid/m.md>"
        )
        self.assertEqual(
            model_pr.build_security_md(once, "example/widget", "<https://example.invalid/m.md>"),
            once,
        )

    def test_policy_url_is_included_when_given(self) -> None:
        out = model_pr.build_security_md(
            None,
            "example/widget",
            "<https://example.invalid/m.md>",
            report_to="security@example.invalid",
            report_policy_url="https://example.invalid/security/",
        )
        self.assertIn("https://example.invalid/security/", out)


class ParserTest(unittest.TestCase):
    def test_model_and_pointer_are_mutually_exclusive(self) -> None:
        parser = model_pr.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--date",
                    "2026-09-08",
                    "--model",
                    "m.md",
                    "--pointer",
                    "https://example.invalid/m.md",
                ]
            )

    def test_one_of_model_or_pointer_is_required(self) -> None:
        parser = model_pr.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["open", "--repo", "example/widget", "--date", "2026-09-08"])

    def test_open_routes_to_cmd_open(self) -> None:
        args = model_pr.build_parser().parse_args(
            ["open", "--repo", "example/widget", "--date", "2026-09-08", "--model", "m.md"]
        )
        self.assertIs(model_pr.DISPATCH[args.cmd], model_pr.cmd_open)
        self.assertEqual(args.license_header, "spdx")
        self.assertEqual(args.model_name, "THREAT_MODEL.md")


if __name__ == "__main__":
    unittest.main()
