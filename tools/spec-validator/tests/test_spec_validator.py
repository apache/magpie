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
    SPDX_MARKER,
    Violation,
    evaluate_gap_predicate,
    extract_section_headings,
    family_count_claims,
    find_repo_root,
    get_section_body,
    has_acceptance_items,
    known_gap_bullets,
    main,
    parse_frontmatter,
    run_validation,
    validate_body,
    validate_cross_spec_counts,
    validate_frontmatter,
    validate_gap_predicates,
    validate_spdx_header,
    validate_spec_loop_runner_fixtures,
    validate_validation_paths,
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
    pytest
    ```

    ## Known gaps

    - `stable`; no gaps at this time.
    """)


def _make_spec(*, status: str = "stable", spdx: bool = True, **overrides: str) -> str:
    """Build a minimal valid spec, replacing frontmatter values as needed.

    Pass ``spdx=False`` to produce a spec intentionally missing the SPDX
    header (used by SPDX-check tests).
    """
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
    header = f"<!-- {SPDX_MARKER}\n     https://www.apache.org/licenses/LICENSE-2.0 -->\n\n" if spdx else ""
    return f"{header}---\n{fm}\n---\n\n# Test spec\n\n{body_sections}\n"


def _make_spec_with_validation(cmd: str) -> str:
    """Build a minimal valid spec with a custom Validation command."""
    body_sections = "\n\n".join(f"## {s}\n\nContent." for s in REQUIRED_SECTIONS)
    body_sections = body_sections.replace(
        "## Validation\n\nContent.",
        f"## Validation\n\n```bash\n{cmd}\n```",
    )
    fm = (
        "title: Test spec\n"
        "status: stable\n"
        "kind: feature\n"
        "mode: Triage\n"
        "source: MISSION.md\n"
        "acceptance:\n"
        "  - One criterion.\n"
    )
    return f"---\n{fm}---\n\n# Test spec\n\n{body_sections}\n"


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
# validate_spdx_header
# ---------------------------------------------------------------------------


class TestValidateSpdxHeader:
    def test_spec_with_spdx_passes(self, tmp_path: Path) -> None:
        text = _make_spec()  # spdx=True by default
        p = tmp_path / "spec.md"
        p.write_text(text)
        assert validate_spdx_header(p, text) == []

    def test_spec_missing_spdx_flagged(self, tmp_path: Path) -> None:
        text = _make_spec(spdx=False)
        p = tmp_path / "spec.md"
        p.write_text(text)
        violations = validate_spdx_header(p, text)
        assert len(violations) == 1
        assert SPDX_MARKER in violations[0].message

    def test_readme_without_frontmatter_skipped(self, tmp_path: Path) -> None:
        text = "# README\n\nNo frontmatter, no SPDX required.\n"
        p = tmp_path / "README.md"
        p.write_text(text)
        assert validate_spdx_header(p, text) == []

    def test_valid_spec_fixture_has_spdx(self, tmp_path: Path) -> None:
        p = tmp_path / "spec.md"
        p.write_text(_VALID_SPEC)
        assert validate_spdx_header(p, _VALID_SPEC) == []

    def test_spdx_violation_line_number_is_1(self, tmp_path: Path) -> None:
        text = _make_spec(spdx=False)
        p = tmp_path / "spec.md"
        p.write_text(text)
        violations = validate_spdx_header(p, text)
        assert violations[0].line == 1

    def test_run_validation_catches_missing_spdx(self, tmp_path: Path) -> None:
        (tmp_path / "spec.md").write_text(_make_spec(spdx=False))
        violations = run_validation(tmp_path)
        assert any(SPDX_MARKER in v.message for v in violations)

    def test_run_validation_accepts_spec_with_spdx(self, tmp_path: Path) -> None:
        (tmp_path / "spec.md").write_text(_make_spec())
        violations = [v for v in run_validation(tmp_path) if SPDX_MARKER in v.message]
        assert violations == []


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
        # Valid specs produce no HARD violation; their unannotated Known-gap
        # bullets are SOFT advisories, which never fail the run.
        violations = run_validation(tmp_path)
        assert [v for v in violations if v.hard] == []
        assert violations and all(v.severity == "SOFT" for v in violations)

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
        assert [v for v in run_validation(p) if v.hard] == []

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


class TestSpecLoopRunnerFixtures:
    def test_missing_fixture_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "tools").mkdir()
        assert validate_spec_loop_runner_fixtures(tmp_path) == []

    def test_passing_fixture_is_ok(self, tmp_path: Path) -> None:
        fixture = tmp_path / "tools" / "spec-loop" / "tests" / "test_runner_fixtures.sh"
        fixture.parent.mkdir(parents=True)
        fixture.write_text("#!/usr/bin/env bash\nexit 0\n")
        assert validate_spec_loop_runner_fixtures(tmp_path) == []

    def test_failing_fixture_is_reported(self, tmp_path: Path) -> None:
        fixture = tmp_path / "tools" / "spec-loop" / "tests" / "test_runner_fixtures.sh"
        fixture.parent.mkdir(parents=True)
        fixture.write_text("#!/usr/bin/env bash\necho broken >&2\nexit 7\n")
        violations = validate_spec_loop_runner_fixtures(tmp_path)
        assert len(violations) == 1
        assert "exit code 7" in violations[0].message
        assert "broken" in violations[0].message


# ---------------------------------------------------------------------------
# Validation-path check (check #8)
# ---------------------------------------------------------------------------


class TestValidateValidationPaths:
    """Tests for check #8: paths in ## Validation code blocks must exist."""

    def test_existing_project_path_no_violation(self, tmp_path: Path) -> None:
        (tmp_path / "tools" / "my-tool").mkdir(parents=True)
        spec = _make_spec_with_validation("uv run --project tools/my-tool --group dev pytest")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_missing_project_path_violation(self, tmp_path: Path) -> None:
        spec = _make_spec_with_validation("uv run --project tools/nonexistent --group dev pytest")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert len(violations) == 1
        assert "tools/nonexistent" in violations[0].message

    def test_shell_variable_skipped(self, tmp_path: Path) -> None:
        spec = _make_spec_with_validation(
            "for t in a b; do uv run --project tools/$t --group dev pytest; done"
        )
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_placeholder_token_skipped(self, tmp_path: Path) -> None:
        spec = _make_spec_with_validation("uv run --project tools/<tool-name> --group dev pytest")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_bare_command_skipped(self, tmp_path: Path) -> None:
        # "pytest" alone has no "/" — not a path
        spec = _make_spec_with_validation("pytest")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_bash_n_existing_file_no_violation(self, tmp_path: Path) -> None:
        script = tmp_path / "tools" / "run.sh"
        script.parent.mkdir(parents=True)
        script.touch()
        spec = _make_spec_with_validation("bash -n tools/run.sh")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_bash_n_missing_file_violation(self, tmp_path: Path) -> None:
        spec = _make_spec_with_validation("bash -n tools/run.sh")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert len(violations) == 1
        assert "tools/run.sh" in violations[0].message
        assert "bash -n" in violations[0].message

    def test_shellcheck_missing_file_violation(self, tmp_path: Path) -> None:
        spec = _make_spec_with_validation("shellcheck tools/run.sh")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert len(violations) == 1
        assert "tools/run.sh" in violations[0].message

    def test_shellcheck_existing_file_no_violation(self, tmp_path: Path) -> None:
        script = tmp_path / "tools" / "run.sh"
        script.parent.mkdir(parents=True)
        script.touch()
        spec = _make_spec_with_validation("shellcheck tools/run.sh")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_test_f_existing_file_no_violation(self, tmp_path: Path) -> None:
        readme = tmp_path / "docs" / "setup" / "README.md"
        readme.parent.mkdir(parents=True)
        readme.touch()
        spec = _make_spec_with_validation("test -f docs/setup/README.md")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_test_f_missing_file_violation(self, tmp_path: Path) -> None:
        spec = _make_spec_with_validation("test -f docs/setup/README.md")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert len(violations) == 1
        assert "docs/setup/README.md" in violations[0].message

    def test_no_frontmatter_skipped(self, tmp_path: Path) -> None:
        text = "# No frontmatter\n\n## Validation\n\n```bash\nuv run --project tools/nonexistent\n```\n"
        violations = validate_validation_paths(Path("test.md"), text, repo_root=tmp_path)
        assert violations == []

    def test_uv_directory_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "tools" / "my-tool").mkdir(parents=True)
        spec = _make_spec_with_validation("uv run --directory tools/my-tool pytest")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_uv_directory_missing_violation(self, tmp_path: Path) -> None:
        spec = _make_spec_with_validation("uv run --directory tools/gone pytest")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert len(violations) == 1
        assert "tools/gone" in violations[0].message

    def test_line_continuation_joined(self, tmp_path: Path) -> None:
        (tmp_path / "tools" / "my-tool").mkdir(parents=True)
        spec = _make_spec_with_validation("uv run --project tools/my-tool \\\n  --group dev pytest")
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert violations == []

    def test_multiple_missing_paths(self, tmp_path: Path) -> None:
        spec = _make_spec_with_validation(
            "uv run --project tools/foo --group dev pytest\nbash -n tools/foo/run.sh"
        )
        violations = validate_validation_paths(Path("specs/test.md"), spec, repo_root=tmp_path)
        assert len(violations) == 2


# ---------------------------------------------------------------------------
# find_repo_root
# ---------------------------------------------------------------------------


class TestFindRepoRoot:
    def test_finds_tools_dir(self, tmp_path: Path) -> None:
        (tmp_path / "tools").mkdir()
        result = find_repo_root(tmp_path)
        assert result == tmp_path

    def test_walks_up_to_tools_dir(self, tmp_path: Path) -> None:
        (tmp_path / "tools").mkdir()
        child = tmp_path / "tools" / "spec-loop" / "specs"
        child.mkdir(parents=True)
        result = find_repo_root(child)
        assert result == tmp_path

    def test_falls_back_to_start_when_no_tools(self, tmp_path: Path) -> None:
        isolated = tmp_path / "isolated"
        isolated.mkdir()
        result = find_repo_root(isolated)
        # Should fall back — does not raise; returns some ancestor
        assert isinstance(result, Path)


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
        violations = [v for v in run_validation(specs_dir) if v.hard]
        if violations:
            messages = "\n".join(str(v) for v in violations)
            pytest.fail(f"Live spec violations found:\n{messages}")


# ---------------------------------------------------------------------------
# Known-gap close conditions and cross-spec family counts
# ---------------------------------------------------------------------------


def _repo(tmp_path: Path, families: dict[str, list[str]]) -> Path:
    """A tree with skills/<name>/SKILL.md carrying the given families."""
    root = tmp_path / "repo"
    for family, names in families.items():
        for name in names:
            d = root / "skills" / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"---\nname: {name}\nfamily: {family}\n---\n# {name}\n")
    (root / "tools" / "lib").mkdir(parents=True)
    (root / "tools" / "lib" / "mod.py").write_text(
        "def wired():\n    return 1\n\n\ndef unwired():\n    return 2\n\n\nwired()\n"
    )
    return root


def _spec_with_gaps(gaps: str, body_extra: str = "") -> str:
    base = _make_spec()
    head, _sep, _tail = base.partition("## Known gaps")
    return head.replace("## Behaviour & contract\n", "## Behaviour & contract\n\n" + body_extra + "\n") + (
        "## Known gaps\n\n" + textwrap.dedent(gaps)
    )


class TestGapPredicates:
    def test_bullets_are_split_and_fenced_examples_skipped(self) -> None:
        text = _spec_with_gaps(
            """\
            - **First.** Line one
              continues here.
              <!-- gap-closes-when: path-exists:a -->

            ```markdown
            - **Example in a fence.** <!-- gap-closes-when: path-exists:b -->
            ```

            - **Second.**
            """
        )
        bullets = known_gap_bullets(text)
        assert [b.splitlines()[0] for _line, b in bullets] == ["- **First.** Line one", "- **Second.**"]
        assert "path-exists:a" in bullets[0][1]

    @pytest.mark.parametrize(
        ("predicate", "state"),
        [
            ("path-exists:skills/one", "closed"),
            ("path-exists:skills/missing", "open"),
            ("path-exists:../etc", "invalid"),
            ("symbol-called:tools/lib::wired", "closed"),
            ("symbol-called:tools/lib::unwired", "open"),  # defined, never called: the point of the predicate
            ("symbol-called:tools/lib::absent", "open"),
            ("symbol-called:tools/nowhere::wired", "invalid"),
            ("symbol-called:tools/lib", "invalid"),
            ("skill-count:repo-health=2", "closed"),
            ("skill-count:repo-health=3", "open"),
            ("skill-count:repo-health=many", "invalid"),
            ("none (narrative)", "open"),
            ("file-says:anything", "invalid"),
            ("nonsense", "invalid"),
        ],
    )
    def test_predicates(self, tmp_path: Path, predicate: str, state: str) -> None:
        root = _repo(tmp_path, {"repo-health": ["one", "two"]})
        assert evaluate_gap_predicate(predicate, root)[0] == state

    def test_closed_and_malformed_are_hard_unannotated_is_soft_narrative_is_silent(
        self, tmp_path: Path
    ) -> None:
        root = _repo(tmp_path, {"repo-health": ["one", "two"]})
        text = _spec_with_gaps(
            """\
            - **Shipped.** <!-- gap-closes-when: path-exists:skills/one -->
            - **Broken.** <!-- gap-closes-when: symbol-called:nope -->
            - **Still open.** <!-- gap-closes-when: path-exists:skills/later -->
            - **Status note.** <!-- gap-closes-when: none (narrative) -->
            - **Unannotated.**
            """
        )
        found = validate_gap_predicates(Path("s.md"), text, root)
        hard = sorted(v.message.split("'")[1] for v in found if v.hard)
        soft = [v.message.split("'")[1] for v in found if not v.hard]
        assert hard == ["Broken.", "Shipped."]
        assert soft == ["Unannotated."]

    def test_soft_never_fails_main(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "spec.md").write_text(_spec_with_gaps("- **Unannotated.**\n"))
        assert main([str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "SOFT:" in out and "OK (no violations)" in out


_FAMILIES = {"repo-health": ["ci-audit", "dep-audit", "fixer"], "issue": ["triage"]}


class TestCrossSpecCounts:
    def _write(self, tmp_path: Path, **specs: str) -> list[Path]:
        paths = []
        for name, body in specs.items():
            p = tmp_path / f"{name}.md"
            p.write_text(_spec_with_gaps("- **x.** <!-- gap-closes-when: none (narrative) -->\n", body))
            paths.append(p)
        return paths

    def test_claim_extraction_is_narrow(self) -> None:
        families = ["repo-health", "issue", "pr-management"]
        text = _spec_with_gaps(
            "- **ok**\n",
            "Repo-health audits are now a six-skill family. "
            "The issue family has 3 skills. "
            "See [repo-health-family.md](repo-health-family.md) for all 9 skills. "
            "`magpie-repo-health` ships 4 skills. "
            "A run over repo-health found many things across a long sentence, in 7 skills.",
        )
        claims = family_count_claims(text, families)
        assert [(f, n) for f, n, _s in claims] == [("repo-health", 6)]
        assert [n for _f, n, _s in family_count_claims("All 4 repo-health skills ship.", families)] == [4]

    def test_matching_live_count_is_clean(self, tmp_path: Path) -> None:
        root = _repo(tmp_path, _FAMILIES)
        paths = self._write(
            tmp_path, a="Repo-health is a three-skill family.", b="All 3 repo-health skills ship."
        )
        assert validate_cross_spec_counts(paths, root) == []

    def test_disagreeing_specs_both_fire_and_name_the_disputed_skill(self, tmp_path: Path) -> None:
        root = _repo(tmp_path, _FAMILIES)
        paths = self._write(
            tmp_path,
            a="Repo-health is a two-skill family: `ci-audit` and `dep-audit`.",
            b="Repo-health is a three-skill family: `ci-audit`, `dep-audit`, `fixer`.",
        )
        found = {v.path.name: v for v in validate_cross_spec_counts(paths, root)}
        # Two specs disagreeing is a violation regardless of which is right.
        assert sorted(found) == ["a.md", "b.md"]
        assert all(isinstance(v, Violation) and v.hard for v in found.values())
        assert "claims 2 repo-health skills, but 3" in found["a.md"].message
        assert "other specs claim 3" in found["a.md"].message
        assert "not named in this spec: fixer" in found["a.md"].message
        assert "matching the 3 SKILL.md files" in found["b.md"].message
        assert "other specs claim 2" in found["b.md"].message

    def test_agreeing_but_stale_specs_still_fire(self, tmp_path: Path) -> None:
        # Every spec agreeing reads as confirmation; the live count still decides.
        root = _repo(tmp_path, _FAMILIES)
        paths = self._write(
            tmp_path, a="Repo-health is a two-skill family.", b="All 2 repo-health skills ship."
        )
        assert sorted(v.path.name for v in validate_cross_spec_counts(paths, root)) == ["a.md", "b.md"]

    def test_no_skills_tree_is_skipped(self, tmp_path: Path) -> None:
        paths = self._write(tmp_path, a="Repo-health is a two-skill family.")
        assert validate_cross_spec_counts(paths, tmp_path / "empty") == []
