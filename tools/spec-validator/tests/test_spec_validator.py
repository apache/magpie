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

"""Tests for the spec validator."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from spec_validator import (
    ALLOWED_KIND,
    ALLOWED_MODE,
    ALLOWED_STATUS,
    REQUIRED_SECTIONS,
    extract_section_headings,
    get_section_body,
    has_acceptance_items,
    main,
    parse_frontmatter,
    run_validation,
    validate_body,
    validate_frontmatter,
    validation_has_code_block,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SPEC = textwrap.dedent("""\
    <!-- SPDX-License-Identifier: Apache-2.0
         https://www.apache.org/licenses/LICENSE-2.0 -->

    ---
    title: Example spec
    status: stable
    kind: feature
    mode: Triage
    source: MISSION.md § some section
    acceptance:
      - At least one criterion is met.
    ---

    # Example spec

    ## What it does

    A brief description.

    ## Where it lives

    - `tools/example/`

    ## Behaviour & contract

    The contract.

    ## Out of scope

    Nothing.

    ## Acceptance criteria

    1. Criterion one.

    ## Validation

    ```bash
    uv run --project tools/example --group dev pytest
    ```

    ## Known gaps

    - `stable`; no gaps at this time.
    """)


def _make_spec(*, status: str = "stable", **overrides: str) -> str:
    """Build a minimal valid spec, replacing frontmatter values as needed."""
    defaults = {
        "title": "Test spec",
        "kind": "feature",
        "mode": "Triage",
        "source": "MISSION.md",
        "acceptance_items": "  - One criterion.",
    }
    defaults.update(overrides)
    acceptance_items = defaults.pop("acceptance_items")
    fm_lines = [
        f"title: {defaults['title']}",
        f"status: {status}",
        f"kind: {defaults['kind']}",
        f"mode: {defaults['mode']}",
        f"source: {defaults['source']}",
        "acceptance:",
        acceptance_items,
    ]
    body_sections = "\n\n".join(f"## {s}\n\nContent." for s in REQUIRED_SECTIONS)
    # Replace Validation section with one that has a code block
    body_sections = body_sections.replace(
        "## Validation\n\nContent.",
        "## Validation\n\n```bash\npytest\n```",
    )
    fm = "\n".join(fm_lines)
    return f"---\n{fm}\n---\n\n# Test spec\n\n{body_sections}\n"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self) -> None:
        fm = parse_frontmatter(_VALID_SPEC)
        assert fm is not None
        assert fm["title"] == "Example spec"
        assert fm["status"] == "stable"

    def test_no_frontmatter_returns_none(self) -> None:
        assert parse_frontmatter("# Just a heading\n\nNo frontmatter.") is None

    def test_html_comment_prefix_allowed(self) -> None:
        text = "<!-- SPDX-License-Identifier: Apache-2.0 -->\n---\ntitle: foo\n---\n"
        fm = parse_frontmatter(text)
        assert fm is not None
        assert fm["title"] == "foo"

    def test_non_comment_prefix_returns_none(self) -> None:
        text = "Some prose\n---\ntitle: foo\n---\n"
        assert parse_frontmatter(text) is None

    def test_folded_block_scalar(self) -> None:
        text = "---\nsource: >\n  line one\n  line two\n---\n"
        fm = parse_frontmatter(text)
        assert fm is not None
        assert "line one" in fm["source"]

    def test_multiline_value(self) -> None:
        text = "---\ntitle: My\n  continuation\n---\n"
        fm = parse_frontmatter(text)
        assert fm is not None
        assert "My" in fm["title"]


class TestHasAcceptanceItems:
    def test_has_items(self) -> None:
        text = "---\nacceptance:\n  - item one\n  - item two\n---\n"
        assert has_acceptance_items(text) is True

    def test_no_items(self) -> None:
        text = "---\nacceptance:\n---\n"
        assert has_acceptance_items(text) is False

    def test_no_frontmatter(self) -> None:
        assert has_acceptance_items("# no frontmatter") is False


# ---------------------------------------------------------------------------
# Body section extraction
# ---------------------------------------------------------------------------


class TestExtractSectionHeadings:
    def test_extracts_h2_headings(self) -> None:
        headings = extract_section_headings(_VALID_SPEC)
        assert "What it does" in headings
        assert "Validation" in headings

    def test_ignores_h1(self) -> None:
        headings = extract_section_headings(_VALID_SPEC)
        assert "Example spec" not in headings

    def test_no_frontmatter_still_works(self) -> None:
        text = "# Title\n\n## Section A\n\ncontent\n"
        headings = extract_section_headings(text)
        assert "Section A" in headings


class TestGetSectionBody:
    def test_returns_section_content(self) -> None:
        body = get_section_body(_VALID_SPEC, "What it does")
        assert body is not None
        assert "A brief description" in body

    def test_returns_none_for_missing_section(self) -> None:
        assert get_section_body(_VALID_SPEC, "Nonexistent") is None

    def test_stops_at_next_section(self) -> None:
        body = get_section_body(_VALID_SPEC, "What it does")
        assert body is not None
        assert "Where it lives" not in body


class TestValidationHasCodeBlock:
    def test_valid_spec_has_code_block(self) -> None:
        assert validation_has_code_block(_VALID_SPEC) is True

    def test_missing_code_block(self) -> None:
        spec = _make_spec()
        spec_no_code = spec.replace("```bash\npytest\n```", "Run pytest manually.")
        assert validation_has_code_block(spec_no_code) is False

    def test_no_validation_section(self) -> None:
        text = "---\ntitle: t\n---\n## Other\n\ncontent\n"
        assert validation_has_code_block(text) is False


# ---------------------------------------------------------------------------
# validate_frontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def test_valid_spec_no_violations(self, tmp_path: Path) -> None:
        p = tmp_path / "spec.md"
        p.write_text(_VALID_SPEC)
        assert validate_frontmatter(p, _VALID_SPEC) == []

    def test_no_frontmatter_skipped(self, tmp_path: Path) -> None:
        text = "# No frontmatter\n\ncontent\n"
        p = tmp_path / "readme.md"
        p.write_text(text)
        assert validate_frontmatter(p, text) == []

    def test_missing_required_key(self, tmp_path: Path) -> None:
        text = "---\ntitle: foo\nstatus: stable\n---\n# foo\n"
        p = tmp_path / "spec.md"
        p.write_text(text)
        violations = validate_frontmatter(p, text)
        messages = [v.message for v in violations]
        assert any("kind" in m for m in messages)
        assert any("mode" in m for m in messages)

    @pytest.mark.parametrize("status", sorted(ALLOWED_STATUS))
    def test_all_valid_statuses_pass(self, tmp_path: Path, status: str) -> None:
        text = _make_spec(status=status)
        p = tmp_path / "spec.md"
        p.write_text(text)
        violations = [v for v in validate_frontmatter(p, text) if "status" in v.message]
        assert violations == []

    def test_invalid_status(self, tmp_path: Path) -> None:
        text = _make_spec(status="unknown")
        p = tmp_path / "spec.md"
        p.write_text(text)
        violations = validate_frontmatter(p, text)
        assert any("invalid status" in v.message for v in violations)

    @pytest.mark.parametrize("kind", sorted(ALLOWED_KIND))
    def test_all_valid_kinds_pass(self, tmp_path: Path, kind: str) -> None:
        text = _make_spec(kind=kind)
        p = tmp_path / "spec.md"
        violations = [v for v in validate_frontmatter(p, text) if "kind" in v.message]
        assert violations == []

    def test_invalid_kind(self, tmp_path: Path) -> None:
        text = _make_spec(kind="unknown")
        p = tmp_path / "spec.md"
        violations = validate_frontmatter(p, text)
        assert any("invalid kind" in v.message for v in violations)

    @pytest.mark.parametrize("mode", sorted(ALLOWED_MODE))
    def test_all_valid_modes_pass(self, tmp_path: Path, mode: str) -> None:
        text = _make_spec(mode=mode)
        p = tmp_path / "spec.md"
        violations = [v for v in validate_frontmatter(p, text) if "mode" in v.message]
        assert violations == []

    def test_invalid_mode(self, tmp_path: Path) -> None:
        text = _make_spec(mode="UnknownMode")
        p = tmp_path / "spec.md"
        violations = validate_frontmatter(p, text)
        assert any("invalid mode" in v.message for v in violations)

    def test_empty_acceptance_list(self, tmp_path: Path) -> None:
        text = (
            "---\ntitle: t\nstatus: stable\nkind: feature\nmode: Triage\nsource: x\nacceptance:\n---\n# t\n"
        )
        p = tmp_path / "spec.md"
        violations = validate_frontmatter(p, text)
        assert any("acceptance" in v.message for v in violations)

    def test_acceptance_with_items_passes(self, tmp_path: Path) -> None:
        text = _make_spec()
        p = tmp_path / "spec.md"
        violations = [v for v in validate_frontmatter(p, text) if "acceptance" in v.message]
        assert violations == []


# ---------------------------------------------------------------------------
# validate_body
# ---------------------------------------------------------------------------


class TestValidateBody:
    def test_valid_spec_no_violations(self, tmp_path: Path) -> None:
        p = tmp_path / "spec.md"
        p.write_text(_VALID_SPEC)
        assert validate_body(p, _VALID_SPEC) == []

    def test_no_frontmatter_skipped(self, tmp_path: Path) -> None:
        text = "# No frontmatter\n\n## What it does\n\ncontent\n"
        p = tmp_path / "readme.md"
        assert validate_body(p, text) == []

    @pytest.mark.parametrize("section", REQUIRED_SECTIONS)
    def test_missing_section_flagged(self, tmp_path: Path, section: str) -> None:
        text = _make_spec()
        # Remove the section heading
        text_no_section = text.replace(f"## {section}\n", "## REPLACED_SECTION\n")
        p = tmp_path / "spec.md"
        violations = validate_body(p, text_no_section)
        assert any(section in v.message for v in violations)

    def test_validation_without_code_block(self, tmp_path: Path) -> None:
        text = _make_spec()
        text_no_code = text.replace("```bash\npytest\n```", "Run manually.")
        p = tmp_path / "spec.md"
        violations = validate_body(p, text_no_code)
        assert any("fenced code block" in v.message for v in violations)

    def test_all_sections_present_no_violations(self, tmp_path: Path) -> None:
        text = _make_spec()
        p = tmp_path / "spec.md"
        assert validate_body(p, text) == []


# ---------------------------------------------------------------------------
# run_validation (integration)
# ---------------------------------------------------------------------------


class TestRunValidation:
    def test_valid_directory_no_violations(self, tmp_path: Path) -> None:
        (tmp_path / "spec_a.md").write_text(_VALID_SPEC)
        (tmp_path / "spec_b.md").write_text(_make_spec(status="experimental"))
        assert run_validation(tmp_path) == []

    def test_readme_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# README\n\nNo frontmatter.\n")
        assert run_validation(tmp_path) == []

    def test_invalid_spec_produces_violations(self, tmp_path: Path) -> None:
        text = "---\ntitle: broken\n---\n# broken\n"
        (tmp_path / "broken.md").write_text(text)
        violations = run_validation(tmp_path)
        assert len(violations) > 0

    def test_single_file_target(self, tmp_path: Path) -> None:
        p = tmp_path / "spec.md"
        p.write_text(_VALID_SPEC)
        assert run_validation(p) == []

    def test_nonexistent_path_via_main(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["/nonexistent/path"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_main_ok(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "spec.md").write_text(_VALID_SPEC)
        rc = main([str(tmp_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_main_violations(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "bad.md").write_text("---\ntitle: bad\n---\n# bad\n")
        rc = main([str(tmp_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "violation" in captured.out


# ---------------------------------------------------------------------------
# Live specs (smoke test)
# ---------------------------------------------------------------------------


class TestLiveSpecs:
    """Run the validator against the actual specs on disk."""

    @pytest.fixture
    def specs_dir(self) -> Path | None:
        """Locate tools/spec-loop/specs/ relative to the repo root."""
        start = Path(__file__).resolve()
        for candidate in (start, *start.parents):
            p = candidate / "tools" / "spec-loop" / "specs"
            if p.is_dir():
                return p
        return None

    def test_live_specs_pass(self, specs_dir: Path | None) -> None:
        if specs_dir is None:
            pytest.skip("tools/spec-loop/specs/ not found — skipping live test")
        violations = run_validation(specs_dir)
        if violations:
            messages = "\n".join(str(v) for v in violations)
            pytest.fail(f"Live spec violations found:\n{messages}")
