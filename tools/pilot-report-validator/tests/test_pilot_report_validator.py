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

"""Tests for the pilot-report validator."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pilot_report_validator import (
    ALLOWED_PROFILES,
    REQUIRED_FRONTMATTER_KEYS,
    REQUIRED_SECTIONS,
    collect_report_files,
    extract_section_headings,
    main,
    parse_frontmatter,
    run_validation,
    validate_body,
    validate_frontmatter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_REPORT = textwrap.dedent("""\
    <!-- SPDX-License-Identifier: Apache-2.0
         https://www.apache.org/licenses/LICENSE-2.0 -->

    ---
    skill: pairing-self-review
    date: 2024-06-01
    target_repo: example/myproject
    profile: asf
    reporter: jdoe
    ---

    # Pilot report: pairing-self-review on example/myproject

    ## Skill or family

    pairing-self-review

    ## Target repo and profile

    example/myproject — ASF profile.

    ## Blocked preflights

    None observed.

    ## False positives

    None observed.

    ## Confirmation points

    All confirmation points felt appropriate.

    ## Privacy and adapter notes

    None observed.

    ## Proposed spec changes

    No changes proposed at this time.
    """)


def _make_report(
    *,
    skill: str = "pairing-self-review",
    date: str = "2024-06-01",
    target_repo: str = "example/myproject",
    profile: str = "asf",
    extra_keys: str = "",
    spdx: bool = True,
) -> str:
    """Build a minimal valid pilot report."""
    spdx_header = (
        "<!-- SPDX-License-Identifier: Apache-2.0\n     https://www.apache.org/licenses/LICENSE-2.0 -->\n\n"
        if spdx
        else ""
    )
    fm = f"skill: {skill}\ndate: {date}\ntarget_repo: {target_repo}\nprofile: {profile}\n" + (
        f"{extra_keys}\n" if extra_keys else ""
    )
    body_sections = "\n\n".join(f"## {s}\n\nContent." for s in REQUIRED_SECTIONS)
    return f"{spdx_header}---\n{fm}---\n\n# Report\n\n{body_sections}\n"


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_report(self) -> None:
        fm = parse_frontmatter(_VALID_REPORT)
        assert fm is not None
        assert fm["skill"] == "pairing-self-review"
        assert fm["profile"] == "asf"

    def test_no_frontmatter_returns_none(self) -> None:
        assert parse_frontmatter("# Just a heading\n\nNo frontmatter.") is None

    def test_html_comment_prefix_allowed(self) -> None:
        text = "<!-- SPDX -->\n---\nskill: foo\ndate: 2024-01-01\ntarget_repo: a/b\nprofile: asf\n---\n"
        fm = parse_frontmatter(text)
        assert fm is not None
        assert fm["skill"] == "foo"

    def test_non_comment_prefix_returns_none(self) -> None:
        text = "Some prose\n---\nskill: foo\n---\n"
        assert parse_frontmatter(text) is None

    def test_extra_optional_key_included(self) -> None:
        fm = parse_frontmatter(_VALID_REPORT)
        assert fm is not None
        assert fm.get("reporter") == "jdoe"


# ---------------------------------------------------------------------------
# extract_section_headings
# ---------------------------------------------------------------------------


class TestExtractSectionHeadings:
    def test_extracts_required_sections(self) -> None:
        headings = extract_section_headings(_VALID_REPORT)
        for section in REQUIRED_SECTIONS:
            assert section in headings, f"expected section '{section}' in headings"

    def test_ignores_h1(self) -> None:
        headings = extract_section_headings(_VALID_REPORT)
        assert "Pilot report: pairing-self-review on example/myproject" not in headings

    def test_no_frontmatter_still_works(self) -> None:
        text = "# Title\n\n## Skill or family\n\ncontent\n"
        headings = extract_section_headings(text)
        assert "Skill or family" in headings


# ---------------------------------------------------------------------------
# validate_frontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def test_valid_report_no_violations(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        p.write_text(_VALID_REPORT)
        assert validate_frontmatter(p, _VALID_REPORT) == []

    def test_no_frontmatter_skipped(self, tmp_path: Path) -> None:
        text = "# No frontmatter\n\ncontent\n"
        p = tmp_path / "readme.md"
        assert validate_frontmatter(p, text) == []

    def test_missing_required_keys(self, tmp_path: Path) -> None:
        text = "---\nskill: foo\n---\n# t\n"
        p = tmp_path / "report.md"
        violations = validate_frontmatter(p, text)
        messages = [v.message for v in violations]
        assert any("date" in m for m in messages)
        assert any("target_repo" in m for m in messages)
        assert any("profile" in m for m in messages)

    def test_all_required_keys_present(self, tmp_path: Path) -> None:
        for key in sorted(REQUIRED_FRONTMATTER_KEYS):
            assert key in {"skill", "date", "target_repo", "profile"}

    @pytest.mark.parametrize("profile", sorted(ALLOWED_PROFILES))
    def test_all_valid_profiles_pass(self, tmp_path: Path, profile: str) -> None:
        text = _make_report(profile=profile)
        p = tmp_path / "report.md"
        violations = [v for v in validate_frontmatter(p, text) if "profile" in v.message]
        assert violations == []

    def test_invalid_profile(self, tmp_path: Path) -> None:
        text = _make_report(profile="unknown")
        p = tmp_path / "report.md"
        violations = validate_frontmatter(p, text)
        assert any("invalid profile" in v.message for v in violations)

    def test_violation_line_number_is_1(self, tmp_path: Path) -> None:
        text = _make_report(profile="bad")
        p = tmp_path / "report.md"
        violations = [v for v in validate_frontmatter(p, text) if "profile" in v.message]
        assert violations[0].line == 1

    def test_missing_key_violation_line_number_is_1(self, tmp_path: Path) -> None:
        text = "---\nskill: foo\n---\n# t\n"
        p = tmp_path / "report.md"
        violations = validate_frontmatter(p, text)
        assert all(v.line == 1 for v in violations)

    def test_angle_bracket_placeholder_flagged(self, tmp_path: Path) -> None:
        text = _make_report(skill="<skill-name>")
        p = tmp_path / "report.md"
        violations = [v.message for v in validate_frontmatter(p, text)]
        assert any("placeholder" in m and "skill" in m for m in violations), violations

    @pytest.mark.parametrize("bad_date", ["YYYY-MM-DD", "2026/06/29", "29-06-2026", "not-a-date"])
    def test_non_iso_date_flagged(self, tmp_path: Path, bad_date: str) -> None:
        text = _make_report(date=bad_date)
        p = tmp_path / "report.md"
        violations = [v.message for v in validate_frontmatter(p, text)]
        assert any("must be ISO 8601" in m for m in violations), violations

    def test_iso_date_passes(self, tmp_path: Path) -> None:
        text = _make_report(date="2026-06-29")
        p = tmp_path / "report.md"
        date_violations = [v.message for v in validate_frontmatter(p, text) if "date" in v.message]
        assert date_violations == []

    def test_filled_values_no_violations(self, tmp_path: Path) -> None:
        text = _make_report(skill="pairing-self-review", date="2026-06-29", target_repo="example/myproject")
        p = tmp_path / "report.md"
        assert validate_frontmatter(p, text) == []


# ---------------------------------------------------------------------------
# validate_body
# ---------------------------------------------------------------------------


class TestValidateBody:
    def test_valid_report_no_violations(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        p.write_text(_VALID_REPORT)
        assert validate_body(p, _VALID_REPORT) == []

    def test_no_frontmatter_skipped(self, tmp_path: Path) -> None:
        text = "# No frontmatter\n\n## Skill or family\n\ncontent\n"
        p = tmp_path / "readme.md"
        assert validate_body(p, text) == []

    @pytest.mark.parametrize("section", REQUIRED_SECTIONS)
    def test_missing_section_flagged(self, tmp_path: Path, section: str) -> None:
        text = _make_report()
        text_no_section = text.replace(f"## {section}\n", "## REPLACED\n")
        p = tmp_path / "report.md"
        violations = validate_body(p, text_no_section)
        assert any(section in v.message for v in violations)

    def test_all_sections_present_no_violations(self, tmp_path: Path) -> None:
        text = _make_report()
        p = tmp_path / "report.md"
        assert validate_body(p, text) == []


# ---------------------------------------------------------------------------
# run_validation (integration)
# ---------------------------------------------------------------------------


class TestRunValidation:
    def test_valid_directory_no_violations(self, tmp_path: Path) -> None:
        (tmp_path / "report_a.md").write_text(_VALID_REPORT)
        (tmp_path / "report_b.md").write_text(_make_report(profile="non-asf"))
        assert run_validation(tmp_path) == []

    def test_readme_without_frontmatter_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# README\n\nNo frontmatter.\n")
        assert run_validation(tmp_path) == []

    def test_invalid_report_produces_violations(self, tmp_path: Path) -> None:
        text = "---\nskill: only-skill\n---\n# broken\n"
        (tmp_path / "broken.md").write_text(text)
        violations = run_validation(tmp_path)
        assert len(violations) > 0

    def test_single_file_target(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        p.write_text(_VALID_REPORT)
        assert run_validation(p) == []

    def test_nested_directory_scanned(self, tmp_path: Path) -> None:
        subdir = tmp_path / "reports"
        subdir.mkdir()
        (subdir / "report.md").write_text(_VALID_REPORT)
        assert run_validation(tmp_path) == []


# ---------------------------------------------------------------------------
# collect_report_files
# ---------------------------------------------------------------------------


class TestCollectReportFiles:
    def test_file_target_returns_self(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        p.write_text("# Test")
        assert collect_report_files(p) == [p]

    def test_directory_scans_recursively(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.md").write_text("a")
        (sub / "b.md").write_text("b")
        files = collect_report_files(tmp_path)
        assert len(files) == 2

    def test_non_md_files_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "report.md").write_text("x")
        (tmp_path / "notes.txt").write_text("y")
        files = collect_report_files(tmp_path)
        assert all(f.suffix == ".md" for f in files)


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------


class TestMain:
    def test_nonexistent_path_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["/nonexistent/path"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_valid_report_returns_0(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "report.md").write_text(_VALID_REPORT)
        rc = main([str(tmp_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_invalid_report_returns_1(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "bad.md").write_text("---\nskill: only\n---\n# bad\n")
        rc = main([str(tmp_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "violation" in captured.out

    def test_readme_only_returns_0(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "README.md").write_text("# README\n\nNo frontmatter, no validation.\n")
        rc = main([str(tmp_path)])
        assert rc == 0

    def test_output_lists_violations(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        text = _make_report(profile="bad-profile")
        (tmp_path / "report.md").write_text(text)
        rc = main([str(tmp_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "invalid profile" in captured.out


# ---------------------------------------------------------------------------
# Template file smoke test
# ---------------------------------------------------------------------------


class TestTemplate:
    """The shipped template must be a structurally valid report.

    Regression guard for the frontmatter-placement bug: the template's
    frontmatter must sit at the very top of the file so that reports
    copied from it are actually detected and validated. If the frontmatter
    is moved lower (e.g. below the table of contents), the validator
    silently skips it — and every real report along with it.
    """

    @staticmethod
    def _find_template() -> Path:
        start = Path(__file__).resolve()
        for candidate in (start, *start.parents):
            template = candidate / "docs" / "pilot-report-template.md"
            if template.is_file():
                return template
        # pytest.skip() raises Skipped, so control never falls through; the explicit
        # raise keeps every path either returning a Path or raising (no implicit None).
        pytest.skip("docs/pilot-report-template.md not found — skipping template smoke test")
        raise AssertionError("unreachable")  # pragma: no cover

    def test_template_frontmatter_is_detected_at_top(self) -> None:
        text = self._find_template().read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        assert fm is not None, (
            "template frontmatter is not detected — it must be at the very top of the file, "
            "above the table of contents, or reports copied from it will be silently skipped"
        )
        assert REQUIRED_FRONTMATTER_KEYS <= set(fm), (
            f"template frontmatter is missing required keys: {sorted(REQUIRED_FRONTMATTER_KEYS - set(fm))}"
        )

    def test_template_flags_unfilled_placeholders(self) -> None:
        """The unfilled template reports its placeholder values, and nothing else.

        Every violation must be a placeholder / date-format finding — not a
        missing key, bad profile, or missing section — which proves the
        frontmatter and body are structurally complete and only the values
        remain to be filled in.
        """
        template = self._find_template()
        messages = [v.message for v in run_validation(template)]
        assert messages, "unfilled template should report its placeholder values as violations"
        for m in messages:
            assert "placeholder" in m or "must be ISO 8601" in m, f"unexpected violation: {m}"

    def test_filled_report_from_template_validates(self, tmp_path: Path) -> None:
        """A user copying the template and filling in real values gets a clean run."""
        text = self._find_template().read_text(encoding="utf-8")
        filled = (
            text.replace("<skill-name>", "pairing-self-review")
            .replace("YYYY-MM-DD", "2026-06-29")
            .replace("<owner>/<repo>", "example/myproject")
            .replace("<github-handle>", "jdoe")
        )
        report = tmp_path / "filled-report.md"
        report.write_text(filled, encoding="utf-8")
        violations = [str(v) for v in run_validation(report)]
        assert violations == [], f"filled report should validate clean, got: {violations}"
