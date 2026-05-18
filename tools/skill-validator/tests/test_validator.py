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

"""Tests for the skill validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from skill_validator import (
    BODY_INLINE_CATEGORY,
    FORBIDDEN_PATTERNS,
    MAX_METADATA_CHARS,
    PRINCIPLE_CATEGORY,
    SOFT_CATEGORIES,
    TRIGGER_PRESERVATION_CATEGORY,
    extract_headings,
    find_repo_root,
    parse_frontmatter,
    resolve_link,
    run_validation,
    slugify,
    validate_body_inline,
    validate_frontmatter,
    validate_links,
    validate_placeholders,
    validate_principle_compliance,
    validate_trigger_preservation,
)

# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self) -> None:
        text = "---\nname: foo\ndescription: bar\nlicense: Apache-2.0\n---\n# heading\n"
        fm = parse_frontmatter(text)
        assert fm is not None
        assert fm["name"] == "foo"
        assert fm["description"] == "bar"
        assert fm["license"] == "Apache-2.0"

    def test_folded_scalar(self) -> None:
        text = (
            "---\n"
            "name: my-skill\n"
            "description: |\n"
            "  First line of description.\n"
            "  Second line.\n"
            "license: Apache-2.0\n"
            "---\n"
        )
        fm = parse_frontmatter(text)
        assert fm is not None
        assert "First line" in fm["description"]
        assert "Second line" in fm["description"]

    def test_missing_frontmatter(self) -> None:
        assert parse_frontmatter("# no frontmatter\n") is None

    def test_no_closing_delimiter(self) -> None:
        assert parse_frontmatter("---\nname: foo\n") is None


# ---------------------------------------------------------------------------
# Frontmatter validation
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def test_valid(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "---\nname: foo\ndescription: bar\nlicense: Apache-2.0\n---\n"
        violations = list(validate_frontmatter(path, text))
        assert violations == []

    def test_missing_name(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "---\ndescription: bar\nlicense: Apache-2.0\n---\n"
        violations = list(validate_frontmatter(path, text))
        assert len(violations) == 1
        assert "name" in violations[0].message

    def test_missing_multiple_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "---\n---\n"
        violations = list(validate_frontmatter(path, text))
        messages = {v.message for v in violations}
        assert any("name" in m for m in messages)
        assert any("description" in m for m in messages)
        assert any("license" in m for m in messages)

    def test_empty_value(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "---\nname: \ndescription: bar\nlicense: Apache-2.0\n---\n"
        violations = list(validate_frontmatter(path, text))
        assert any("name' is empty" in v.message for v in violations)

    def test_invalid_license(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "---\nname: foo\ndescription: bar\nlicense: MIT\n---\n"
        violations = list(validate_frontmatter(path, text))
        assert any("MIT" in v.message for v in violations)

    def test_valid_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        for mode in ("Triage", "Mentoring", "Drafting", "Pairing"):
            text = f"---\nname: foo\ndescription: bar\nlicense: Apache-2.0\nmode: {mode}\n---\n"
            violations = list(validate_frontmatter(path, text))
            assert violations == [], f"mode '{mode}' should be valid"

    def test_invalid_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "---\nname: foo\ndescription: bar\nlicense: Apache-2.0\nmode: Auto-merge\n---\n"
        violations = list(validate_frontmatter(path, text))
        assert any("mode" in v.message and "'Auto-merge'" in v.message for v in violations)

    def test_mode_optional(self, tmp_path: Path) -> None:
        # Skills without a mode (e.g. setup-* infrastructure) must not fail.
        path = tmp_path / "SKILL.md"
        text = "---\nname: foo\ndescription: bar\nlicense: Apache-2.0\n---\n"
        violations = list(validate_frontmatter(path, text))
        assert violations == []

    def test_metadata_under_limit(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        desc = "a" * 800
        wtu = "b" * 700
        text = f"---\nname: foo\ndescription: {desc}\nwhen_to_use: {wtu}\nlicense: Apache-2.0\n---\n"
        violations = list(validate_frontmatter(path, text))
        assert violations == []

    def test_metadata_over_limit(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        desc = "a" * 1000
        wtu = "b" * (MAX_METADATA_CHARS - 1000 + 1)
        text = f"---\nname: foo\ndescription: {desc}\nwhen_to_use: {wtu}\nlicense: Apache-2.0\n---\n"
        violations = list(validate_frontmatter(path, text))
        assert any("truncates" in v.message and str(MAX_METADATA_CHARS) in v.message for v in violations)

    def test_argument_hint_accepted(self, tmp_path: Path) -> None:
        # argument-hint is a Claude Code autocomplete-only field; it must not be
        # rejected as an unknown key, and it must not count toward the
        # description+when_to_use metadata budget.
        path = tmp_path / "SKILL.md"
        text = (
            "---\n"
            "name: foo\n"
            "description: bar\n"
            "license: Apache-2.0\n"
            "argument-hint: [--quick|--standard|--deep] <idea>\n"
            "---\n"
        )
        violations = list(validate_frontmatter(path, text))
        assert violations == []

    def test_metadata_block_scalar_indicator_not_counted(self) -> None:
        text = f"---\nname: foo\ndescription: |\n  {'a' * 100}\nlicense: Apache-2.0\n---\n"
        fm = parse_frontmatter(text)
        assert fm is not None
        assert not fm["description"].startswith("|")
        assert len(fm["description"]) == 100


# ---------------------------------------------------------------------------
# Heading / anchor helpers
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_punctuation(self) -> None:
        assert slugify("What's new?") == "whats-new"

    def test_multiple_spaces(self) -> None:
        # GitHub's anchor algorithm replaces each whitespace character with
        # a dash one-for-one rather than collapsing runs. Doctoc and the
        # GitHub renderer agree on this; the canonical case is em-dash
        # headings, which strip to "" and leave two adjacent spaces.
        assert slugify("A  B   C") == "a--b---c"

    def test_em_dash_in_heading(self) -> None:
        assert slugify("Mentoring") == "mentoring"


class TestExtractHeadings:
    def test_basic(self) -> None:
        text = "# Foo\n## Bar Baz\n### Qux\n"
        slugs = extract_headings(text)
        assert slugs == {"foo", "bar-baz", "qux"}

    def test_with_links(self) -> None:
        text = "# [Foo](url)\n"
        slugs = extract_headings(text)
        assert "foo" in slugs


# ---------------------------------------------------------------------------
# Link resolution
# ---------------------------------------------------------------------------


class TestResolveLink:
    def test_external_http(self, tmp_path: Path) -> None:
        assert resolve_link(tmp_path / "SKILL.md", "http://example.com", set(), set()) is None

    def test_external_https(self, tmp_path: Path) -> None:
        assert resolve_link(tmp_path / "SKILL.md", "https://example.com", set(), set()) is None

    def test_mailto(self, tmp_path: Path) -> None:
        assert resolve_link(tmp_path / "SKILL.md", "mailto:a@b.com", set(), set()) is None

    def test_same_file_anchor(self, tmp_path: Path) -> None:
        source = tmp_path / "SKILL.md"
        result = resolve_link(source, "#anchor", set(), set())
        assert result == source


# ---------------------------------------------------------------------------
# Link validation
# ---------------------------------------------------------------------------


class TestValidateLinks:
    def test_valid_same_file_anchor(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "# Foo\n[link](#foo)\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_invalid_same_file_anchor(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "# Foo\n[link](#bar)\n"
        violations = list(validate_links(path, text, set(), set()))
        assert len(violations) == 1
        assert "#bar" in violations[0].message

    def test_valid_cross_file(self, tmp_path: Path) -> None:
        base = tmp_path
        source = base / "SKILL.md"
        target = base / "other.md"
        target.write_text("# Other\n", encoding="utf-8")
        text = "[link](other.md)\n"
        violations = list(validate_links(source, text, {base}, set()))
        assert violations == []

    def test_missing_cross_file(self, tmp_path: Path) -> None:
        base = tmp_path
        source = base / "SKILL.md"
        text = "[link](missing.md)\n"
        violations = list(validate_links(source, text, {base}, set()))
        assert len(violations) == 1
        assert "missing.md" in violations[0].message

    def test_valid_cross_file_anchor(self, tmp_path: Path) -> None:
        base = tmp_path
        source = base / "SKILL.md"
        target = base / "other.md"
        target.write_text("# Other\n## Sub Section\n", encoding="utf-8")
        text = "[link](other.md#sub-section)\n"
        violations = list(validate_links(source, text, {base}, set()))
        assert violations == []

    def test_invalid_cross_file_anchor(self, tmp_path: Path) -> None:
        base = tmp_path
        source = base / "SKILL.md"
        target = base / "other.md"
        target.write_text("# Other\n", encoding="utf-8")
        text = "[link](other.md#nonexistent)\n"
        violations = list(validate_links(source, text, {base}, set()))
        assert len(violations) == 1
        assert "#nonexistent" in violations[0].message

    def test_external_link_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "[link](https://example.com)\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_framework_placeholder_url_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "[doc](<project-config>/project.md)\n[doc2](../../../<project-config>/release-trains.md)\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_template_token_url_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "[a](<doc_url>)\n[b](<URL into the public source>)\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_anchor_with_placeholder_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "[link](#issuecomment-<id>)\n[link2](other.md#issuecomment-<id>)\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_ellipsis_url_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "[continues](...)\n[continues](…)\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_link_inside_inline_code_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "Use ``[text](url)`` form for emails.\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_link_inside_single_backtick_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "Write `[text](missing.md)` literally.\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_link_inside_fenced_code_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "```\nsee [doc](missing.md) here\n```\n"
        violations = list(validate_links(path, text, set(), set()))
        assert violations == []

    def test_duplicate_heading_anchor_resolves(self, tmp_path: Path) -> None:
        base = tmp_path
        source = base / "SKILL.md"
        target = base / "other.md"
        target.write_text("# Setup\n# Setup\n# Setup\n", encoding="utf-8")
        text = "[a](other.md#setup)\n[b](other.md#setup-1)\n[c](other.md#setup-2)\n"
        violations = list(validate_links(source, text, {base}, set()))
        assert violations == []


# ---------------------------------------------------------------------------
# Placeholder validation
# ---------------------------------------------------------------------------


class TestValidatePlaceholders:
    def test_clean_line(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "Use <PROJECT> and <upstream> here.\n"
        violations = list(validate_placeholders(path, text))
        assert violations == []

    def test_forbidden_pattern(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "See apache/airflow for details.\n"
        violations = list(validate_placeholders(path, text))
        assert len(violations) == 1
        assert "apache/airflow" in violations[0].message

    def test_allowlisted_path(self, tmp_path: Path) -> None:
        # Simulate a path inside projects/_template/
        path = tmp_path / "projects" / "_template" / "foo.md"
        path.parent.mkdir(parents=True)
        text = "This mentions apache/airflow intentionally.\n"
        violations = list(validate_placeholders(path, text))
        assert violations == []

    def test_inline_marker(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = "For example: apache/airflow is the upstream.\n"
        violations = list(validate_placeholders(path, text))
        assert violations == []


# ---------------------------------------------------------------------------
# Repo-root detection
# ---------------------------------------------------------------------------


class TestFindRepoRoot:
    def test_locates_root_from_validator_subtree(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Regression: the silent-pass bug fired only when CWD was inside the validator subtree.
        repo = Path(__file__).resolve().parents[3]
        assert (repo / ".claude" / "skills").is_dir(), "test setup precondition"
        monkeypatch.chdir(repo / "tools" / "skill-validator")
        assert find_repo_root() == repo

    def test_explicit_start_outside_repo(self, tmp_path: Path) -> None:
        assert find_repo_root(tmp_path) == tmp_path.resolve()


# ---------------------------------------------------------------------------
# End-to-end: real repo
# ---------------------------------------------------------------------------


class TestRunValidation:
    def test_no_duplicate_errors_with_check_placeholders(self) -> None:
        """Ensure our placeholder checks don't add noise beyond check-placeholders.sh.

        Both tools share the same forbidden-pattern list, so any line
        that check-placeholders.sh would catch we should also catch.
        This test verifies that the two validators stay in sync.
        """
        assert set(FORBIDDEN_PATTERNS) == {
            "apache/airflow",
            "airflow-s/airflow-s",
            "Apache Airflow",
            "apache.org/airflow",
        }

    def test_real_repo_passes(self) -> None:
        """Run the full validation suite against the actual repo.

        This is the primary integration test: it exercises every
        SKILL.md, every supporting file, and every internal link.

        SOFT categories (principle_compliance, trigger_preservation)
        are excluded — they are advisory and surface as warnings, not
        failures. The main runtime gate is `--strict`.
        """
        from skill_validator import SOFT_CATEGORIES

        violations = [v for v in run_validation() if v.category not in SOFT_CATEGORIES]
        if violations:
            # Pretty-print the first few failures so pytest output is useful
            lines = [str(v) for v in violations[:10]]
            pytest.fail(f"{len(violations)} validation violation(s) found:\n" + "\n".join(lines))


# ---------------------------------------------------------------------------
# Principle-compliance SOFT warnings
# ---------------------------------------------------------------------------


def _fm(description: str = "", when_to_use: str = "") -> str:
    parts = ["---", "name: test-skill", "license: Apache-2.0"]
    if description:
        parts.append(f"description: |\n  {description}")
    if when_to_use:
        parts.append(f"when_to_use: |\n  {when_to_use}")
    parts.append("---")
    parts.append("# body")
    return "\n".join(parts) + "\n"


class TestPrincipleCompliance:
    def test_action_inventory_in_description_warned(self) -> None:
        text = _fm(description="Does a, b, c, d, e, f, and finally g.")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        msgs = [v.message for v in violations]
        assert any("action-inventory" in m for m in msgs)
        assert all(v.category == PRINCIPLE_CATEGORY for v in violations)

    def test_action_inventory_below_threshold_silent(self) -> None:
        text = _fm(description="Does a, b, and c.")  # 2 commas
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert not any("action-inventory" in v.message for v in violations)

    def test_distinct_from_clause_warned(self) -> None:
        text = _fm(description="Walks a maintainer through review. Distinct from triage skill.")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("distinct-from" in v.message for v in violations)

    def test_unlike_clause_warned(self) -> None:
        text = _fm(description="Unlike security-issue-import, no Gmail involved.")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("distinct-from" in v.message for v in violations)

    def test_chain_handoff_warned(self) -> None:
        text = _fm(description="Does the thing. Hands off to security-issue-sync after.")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("chain-handoff" in v.message for v in violations)

    def test_ready_for_x_to_take_over_warned(self) -> None:
        text = _fm(description="Lands the tracker, ready for security-cve-allocate to take over.")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("chain-handoff" in v.message for v in violations)

    def test_parenthetical_rationale_warned(self) -> None:
        text = _fm(description="Closes the tracker (a separate REJECT flow is required first).")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("parenthetical rationale" in v.message for v in violations)

    def test_parenthetical_typically_warned(self) -> None:
        text = _fm(description="Merges two trackers (typically discovered independently).")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("parenthetical rationale" in v.message for v in violations)

    def test_neutral_parenthetical_not_warned(self) -> None:
        """A spec-style paren like (`<tracker>`, `<upstream>`) should not trip the rule."""
        text = _fm(description="Use placeholders (`<tracker>`, `<upstream>`, `<security-list>`).")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert not any("parenthetical rationale" in v.message for v in violations)

    def test_criteria_source_doc_path_warned(self) -> None:
        text = _fm(description="Walks the checklist documented in `docs/setup/agents.md`.")
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("criteria-source" in v.message for v in violations)

    def test_criteria_source_process_step_warned(self) -> None:
        text = _fm(when_to_use='Invoke after "consensus reached" — typically after process step 6.')
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("criteria-source" in v.message for v in violations)

    def test_criteria_source_step_with_letter_warned(self) -> None:
        text = _fm(when_to_use='Invoke when "duplicate" surfaces at Step 2a.')
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert any("criteria-source" in v.message for v in violations)

    def test_clean_frontmatter_silent(self) -> None:
        text = _fm(
            description="Triage open PRs and propose a disposition.",
            when_to_use='Invoke when a maintainer says "triage the PR queue".',
        )
        violations = list(validate_principle_compliance(Path("skill.md"), text))
        assert violations == []


# ---------------------------------------------------------------------------
# Trigger-phrase non-regression
# ---------------------------------------------------------------------------


class TestTriggerPreservation:
    def test_unavailable_base_ref_no_op(self, tmp_path: Path) -> None:
        """When git or the base ref isn't reachable, the check returns no violations."""
        skill = tmp_path / "SKILL.md"
        skill.write_text(_fm(when_to_use='Invoke when "trim me" is said.'), encoding="utf-8")
        violations = list(
            validate_trigger_preservation(
                skill,
                skill.read_text(encoding="utf-8"),
                base_ref="nonexistent/ref/__nope__",
                repo_root=tmp_path,
            )
        )
        # No git history at *all* for tmp_path — silently no-op.
        assert violations == []

    def test_quoted_phrase_diff_reports_missing(self, tmp_path: Path) -> None:
        """Initialise a tiny git repo and detect a dropped trigger."""
        import subprocess

        # Skip cleanly if git isn't available in the test environment.
        try:
            subprocess.run(
                ["git", "init", "-q"],
                cwd=str(tmp_path),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "config", "commit.gpgsign", "false"],
                cwd=str(tmp_path),
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("git not available")

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill = skills_dir / "demo" / "SKILL.md"
        skill.parent.mkdir()

        # Base version has both triggers
        skill.write_text(
            _fm(when_to_use='Invoke when "alpha" or "beta" is said.'),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-q",
                "-m",
                "init",
            ],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

        # Current version drops "beta"
        skill.write_text(_fm(when_to_use='Invoke when "alpha" is said.'), encoding="utf-8")

        violations = list(
            validate_trigger_preservation(
                skill,
                skill.read_text(encoding="utf-8"),
                base_ref="HEAD",
                repo_root=tmp_path,
            )
        )
        assert len(violations) == 1
        assert violations[0].category == TRIGGER_PRESERVATION_CATEGORY
        assert "'beta'" in violations[0].message


# ---------------------------------------------------------------------------
# body-inline check (Pattern 9 extension)
# ---------------------------------------------------------------------------


def _fenced_skill(cmd: str) -> str:
    """Wrap *cmd* in a minimal SKILL.md with a fenced bash block."""
    return (
        "---\nname: test\ndescription: test\nlicense: Apache-2.0\n---\n\n"
        f"```bash\n{cmd}\n```\n"
    )


class TestBodyInline:
    def test_no_body_arg_silent(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = _fenced_skill("gh issue create --title 'Bug' --body-file /tmp/body.txt")
        violations = list(validate_body_inline(path, text))
        assert violations == []

    def test_body_space_double_quote_fenced_flagged(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = _fenced_skill('gh issue create --title "T" --body "some text"')
        violations = list(validate_body_inline(path, text))
        assert len(violations) == 1
        assert violations[0].category == BODY_INLINE_CATEGORY
        assert "body-inline" in violations[0].message

    def test_body_space_single_quote_fenced_flagged(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = _fenced_skill("gh issue create --title T --body 'some text'")
        violations = list(validate_body_inline(path, text))
        assert len(violations) == 1
        assert violations[0].category == BODY_INLINE_CATEGORY

    def test_body_equals_double_quote_fenced_flagged(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = _fenced_skill('gh issue create --body="some text"')
        violations = list(validate_body_inline(path, text))
        assert len(violations) == 1
        assert violations[0].category == BODY_INLINE_CATEGORY

    def test_body_equals_single_quote_fenced_flagged(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = _fenced_skill("gh issue create --body='some text'")
        violations = list(validate_body_inline(path, text))
        assert len(violations) == 1
        assert violations[0].category == BODY_INLINE_CATEGORY

    def test_inline_backtick_mention_skipped(self, tmp_path: Path) -> None:
        """Prose like ``never use --body "..."`` should not fire."""
        path = tmp_path / "SKILL.md"
        text = (
            "---\nname: test\ndescription: test\nlicense: Apache-2.0\n---\n\n"
            "Do not use `--body \"text\"` — prefer `--body-file` instead.\n"
        )
        violations = list(validate_body_inline(path, text))
        assert violations == []

    def test_body_file_not_flagged(self, tmp_path: Path) -> None:
        """``--body-file`` must never be flagged — it is the correct form."""
        path = tmp_path / "SKILL.md"
        text = _fenced_skill("gh issue create --title T --body-file /tmp/b.txt")
        violations = list(validate_body_inline(path, text))
        assert violations == []

    def test_violation_line_number_correct(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        # _fenced_skill layout (1-indexed):
        #   1: ---
        #   2: name: test
        #   3: description: test
        #   4: license: Apache-2.0
        #   5: ---
        #   6: (blank)
        #   7: ```bash
        #   8: gh issue create --body "text"   ← violation here
        #   9: ```
        text = _fenced_skill('gh issue create --body "text"')
        violations = list(validate_body_inline(path, text))
        assert len(violations) == 1
        assert violations[0].line == 8

    def test_body_inline_is_soft(self) -> None:
        assert BODY_INLINE_CATEGORY in SOFT_CATEGORIES

    def test_message_references_body_file(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        text = _fenced_skill('gh pr create --body "description"')
        violations = list(validate_body_inline(path, text))
        assert len(violations) == 1
        assert "--body-file" in violations[0].message

    def test_security_checklist_skipped(self, tmp_path: Path) -> None:
        """security-checklist.md documents bad patterns intentionally — must not fire."""
        path = tmp_path / "write-skill" / "security-checklist.md"
        path.parent.mkdir(parents=True)
        text = _fenced_skill('gh issue create --body "bad pattern documented here"')
        violations = list(validate_body_inline(path, text))
        assert violations == []


# ---------------------------------------------------------------------------
# SOFT category exposure
# ---------------------------------------------------------------------------


class TestSoftCategories:
    def test_soft_categories_set(self) -> None:
        assert PRINCIPLE_CATEGORY in SOFT_CATEGORIES
        assert TRIGGER_PRESERVATION_CATEGORY in SOFT_CATEGORIES
        assert BODY_INLINE_CATEGORY in SOFT_CATEGORIES
