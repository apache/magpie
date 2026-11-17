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

import os
import stat
import sys
import tempfile
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
        self.assertFalse(args.overwrite)


class CmdOpenSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orig_run = model_pr._run
        self.commands: list[list[str]] = []

        def mock_run(cmd: list[str], cwd: str | None = None, capture: bool = False) -> str:
            self.commands.append(cmd)
            if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "clone":
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            if "api" in cmd and "user" in cmd:
                return "authenticated-user"
            if "rev-parse" in cmd:
                return "main"
            return ""

        model_pr._run = mock_run

    def tearDown(self) -> None:
        model_pr._run = self.orig_run

    def test_dry_run_skips_gh_repo_fork(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Threat Model\n", encoding="utf-8")
            workdir = Path(tmp) / "work"
            workdir.mkdir()

            parser = model_pr.build_parser()
            args = parser.parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--date",
                    "2026-11-17",
                    "--report-to",
                    "security@example.com",
                    "--workdir",
                    str(workdir),
                    "--dry-run",
                ]
            )

            # The mock clone creates the destination directory
            exit_code = model_pr.cmd_open(args)
            self.assertEqual(exit_code, 0)

            # Assert gh repo fork was NEVER invoked
            fork_calls = [
                cmd for cmd in self.commands if len(cmd) >= 3 and cmd[0:3] == ["gh", "repo", "fork"]
            ]
            self.assertEqual(fork_calls, [])

            # Assert git diff used --no-pager
            diff_calls = [cmd for cmd in self.commands if "diff" in cmd]
            self.assertTrue(any("--no-pager" in cmd for cmd in diff_calls))

    def test_dry_run_offline_gh_api_user_fallback(self) -> None:
        def failing_run(cmd: list[str], cwd: str | None = None, capture: bool = False) -> str:
            if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "clone":
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            if "api" in cmd and "user" in cmd:
                raise SystemExit("command failed (1): gh api user --jq .login")
            if "rev-parse" in cmd:
                return "main"
            return ""

        model_pr._run = failing_run
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Threat Model\n", encoding="utf-8")
            workdir = Path(tmp) / "work"
            workdir.mkdir()

            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--date",
                    "2026-11-17",
                    "--report-to",
                    "security@example.com",
                    "--workdir",
                    str(workdir),
                    "--dry-run",
                ]
            )
            # Should not raise SystemExit from gh api user
            exit_code = model_pr.cmd_open(args)
            self.assertEqual(exit_code, 0)

    def test_missing_model_file_fails_preflight(self) -> None:
        args = model_pr.build_parser().parse_args(
            [
                "open",
                "--repo",
                "example/widget",
                "--model",
                "non_existent_file_xyz.md",
                "--date",
                "2026-11-17",
            ]
        )
        with self.assertRaises(SystemExit) as ctx:
            model_pr.cmd_open(args)
        self.assertIn("--model file not found", str(ctx.exception))

    def test_missing_body_file_fails_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Model", encoding="utf-8")
            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--date",
                    "2026-11-17",
                    "--body-file",
                    "missing_body_xyz.md",
                ]
            )
            with self.assertRaises(SystemExit) as ctx:
                model_pr.cmd_open(args)
            self.assertIn("--body-file not found", str(ctx.exception))

    def test_workdir_existing_clone_fails_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Model", encoding="utf-8")
            workdir = Path(tmp) / "work"
            clone = workdir / "widget"
            clone.mkdir(parents=True)
            sentinel = clone / "precious.txt"
            sentinel.write_text("do not delete", encoding="utf-8")

            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--date",
                    "2026-11-17",
                    "--workdir",
                    str(workdir),
                ]
            )
            with self.assertRaises(SystemExit) as ctx:
                model_pr.cmd_open(args)
            self.assertIn("Destination directory already exists in --workdir", str(ctx.exception))
            # Verify file was NOT deleted
            self.assertTrue(sentinel.exists())

    def test_workdir_existing_clone_succeeds_with_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Model", encoding="utf-8")
            workdir = Path(tmp) / "work"
            clone = workdir / "widget"
            clone.mkdir(parents=True)
            sentinel = clone / "precious.txt"
            sentinel.write_text("will be overwritten", encoding="utf-8")

            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--date",
                    "2026-11-17",
                    "--report-to",
                    "security@example.com",
                    "--workdir",
                    str(workdir),
                    "--overwrite",
                    "--dry-run",
                ]
            )
            exit_code = model_pr.cmd_open(args)
            self.assertEqual(exit_code, 0)
            # The sentinel was wiped and replaced by the new clone
            self.assertFalse(sentinel.exists())

    def test_model_name_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "clone"
            clone.mkdir()
            bad_names = (
                "../../outside.md",
                "../escape.md",
                "/etc/passwd",
                "C:\\escaped.md",
                "D:drive_rel.md",
                "\\Users\\test.md",
                "/Users/test.md",
                "",
                "   ",
                ".",
                "..",
                "model.md:stream",
            )
            for bad_name in bad_names:
                with self.assertRaises(SystemExit, msg=f"Should reject: {bad_name!r}"):
                    model_pr._validate_model_name(clone, bad_name)

    def test_model_name_valid_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "clone"
            clone.mkdir()
            valid = model_pr._validate_model_name(clone, "docs/THREAT_MODEL.md")
            self.assertEqual(valid, Path("docs/THREAT_MODEL.md"))

    def test_cmd_open_with_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp) / "work"
            workdir.mkdir()
            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--pointer",
                    "https://example.invalid/THREAT_MODEL.md",
                    "--date",
                    "2026-11-17",
                    "--report-to",
                    "security@example.com",
                    "--workdir",
                    str(workdir),
                    "--dry-run",
                ]
            )
            exit_code = model_pr.cmd_open(args)
            self.assertEqual(exit_code, 0)
            add_calls = [cmd for cmd in self.commands if "add" in cmd]
            self.assertTrue(any("SECURITY.md" in cmd and "AGENTS.md" in cmd for cmd in add_calls))

    def test_cmd_open_full_execution_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Model", encoding="utf-8")
            workdir = Path(tmp) / "work"
            workdir.mkdir()
            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--date",
                    "2026-11-17",
                    "--report-to",
                    "security@example.com",
                    "--workdir",
                    str(workdir),
                    "--submit",
                ]
            )
            exit_code = model_pr.cmd_open(args)
            self.assertEqual(exit_code, 0)
            # Assert all lifecycle mutation commands were executed in sequence
            cmd_heads = [cmd[0:3] if len(cmd) >= 3 else cmd for cmd in self.commands]
            self.assertIn(["gh", "repo", "fork"], cmd_heads)
            self.assertIn(["git", "commit", "-q"], cmd_heads)
            self.assertIn(["git", "push", "-q"], cmd_heads)
            self.assertIn(["gh", "pr", "create"], cmd_heads)

    def test_remove_tree_handles_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            regular_file = Path(tmp) / "file.txt"
            regular_file.write_text("plain file", encoding="utf-8")
            model_pr._remove_tree(regular_file)
            self.assertFalse(regular_file.exists())

    def test_remove_tree_handles_readonly_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "to_delete"
            target_dir.mkdir()
            readonly_file = target_dir / "readonly.txt"
            readonly_file.write_text("cannot touch", encoding="utf-8")
            os.chmod(readonly_file, stat.S_IREAD)

            model_pr._remove_tree(target_dir)
            self.assertFalse(target_dir.exists())

    def test_temp_workroot_is_cleaned_up_on_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Model", encoding="utf-8")
            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--date",
                    "2026-11-17",
                    "--report-to",
                    "security@example.com",
                    "--dry-run",
                ]
            )
            # Find the clone path from commands
            exit_code = model_pr.cmd_open(args)
            self.assertEqual(exit_code, 0)
            clone_cmd_call = next(
                cmd for cmd in self.commands if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "clone"
            )
            clone_path = Path(clone_cmd_call[-1])
            temp_workroot = clone_path.parent
            # Assert temporary workroot was cleaned up
            self.assertFalse(temp_workroot.exists())

    def test_utf8_encoding_handles_unicode_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "unicode.md"
            unicode_text = "# Policy \u2014 Magpie \u00a9 2026 \u2713\n"
            test_file.write_text(unicode_text, encoding="utf-8")
            read_back = model_pr._read_or_none(test_file)
            self.assertEqual(read_back, unicode_text)

    def test_remove_tree_symlink_does_not_modify_target_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "outside_target"
            target_dir.mkdir()
            target_file = target_dir / "data.txt"
            target_file.write_text("critical data", encoding="utf-8")

            symlink = Path(tmp) / "workdir" / "repo_clone"
            symlink.parent.mkdir()
            try:
                symlink.symlink_to(target_dir, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"Symlinks not supported in this environment: {exc}")

            target_mode_before = target_dir.stat().st_mode
            model_pr._remove_tree(symlink)

            self.assertFalse(symlink.is_symlink())
            self.assertFalse(symlink.exists())
            self.assertTrue(target_dir.exists())
            self.assertEqual(target_dir.stat().st_mode, target_mode_before)
            self.assertEqual(target_file.read_text(encoding="utf-8"), "critical data")

    def test_remove_tree_broken_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            symlink = Path(tmp) / "broken_link"
            nonexistent = Path(tmp) / "missing_dir"
            try:
                symlink.symlink_to(nonexistent, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"Symlinks not supported in this environment: {exc}")

            self.assertTrue(symlink.is_symlink())
            self.assertFalse(symlink.exists())
            model_pr._remove_tree(symlink)
            self.assertFalse(symlink.is_symlink())

    def test_model_name_lexical_validation_fails_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Model", encoding="utf-8")
            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--model-name",
                    "../escaped.md",
                    "--date",
                    "2026-11-17",
                ]
            )
            with self.assertRaises(SystemExit) as ctx:
                model_pr.cmd_open(args)
            self.assertIn("--model-name must be a relative path", str(ctx.exception))
            # Zero subprocess commands executed (no gh api, no gh repo fork, no git clone)
            self.assertEqual(self.commands, [])

    def test_model_reference_uses_validated_model_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "model.md"
            model_file.write_text("# Model", encoding="utf-8")
            workdir = Path(tmp) / "work"
            workdir.mkdir()
            args = model_pr.build_parser().parse_args(
                [
                    "open",
                    "--repo",
                    "example/widget",
                    "--model",
                    str(model_file),
                    "--model-name",
                    "  docs/threat_model.md  ",
                    "--workdir",
                    str(workdir),
                    "--date",
                    "2026-11-17",
                    "--report-to",
                    "security@example.com",
                    "--dry-run",
                ]
            )
            exit_code = model_pr.cmd_open(args)
            self.assertEqual(exit_code, 0)
            clone = workdir / "widget"
            written_model = clone / "docs" / "threat_model.md"
            self.assertTrue(written_model.is_file())
            security_md = (clone / "SECURITY.md").read_text(encoding="utf-8")
            self.assertIn("./docs/threat_model.md", security_md)
            self.assertNotIn("./  docs/threat_model.md  ", security_md)


if __name__ == "__main__":
    unittest.main()
