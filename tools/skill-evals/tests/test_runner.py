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
"""Tests for ``skill_evals.runner``."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from skill_evals.runner import (
    build_corpus_text,
    build_roster_text,
    extract_skill_section,
    find_cases,
    find_repo_root,
    load_case,
    load_step_config,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    """Return a directory that looks like a git repo root."""
    (tmp_path / ".git").mkdir()
    return tmp_path


def _make_fixtures_dir(
    parent: Path,
    *,
    step_config: dict | None = None,
    system_prompt: str | None = None,
    output_spec: str | None = None,
    user_prompt_template: str | None = None,
) -> Path:
    fixtures_dir = parent / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    if step_config is not None:
        (fixtures_dir / "step-config.json").write_text(json.dumps(step_config))
    if system_prompt is not None:
        (fixtures_dir / "system-prompt.md").write_text(system_prompt)
    if output_spec is not None:
        (fixtures_dir / "output-spec.md").write_text(output_spec)
    if user_prompt_template is not None:
        (fixtures_dir / "user-prompt-template.md").write_text(user_prompt_template)
    return fixtures_dir


def _make_case(fixtures_dir: Path, name: str, *, report: str = "report text", expected: dict | None = None) -> Path:
    case_dir = fixtures_dir / name
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "report.md").write_text(report)
    (case_dir / "expected.json").write_text(json.dumps(expected or {"verdict": "ok"}))
    return case_dir


def _run_main(capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


# ---------------------------------------------------------------------------
# build_corpus_text
# ---------------------------------------------------------------------------


def test_build_corpus_text_empty():
    assert build_corpus_text([]) == ""


def test_build_corpus_text_single_item():
    result = build_corpus_text([{"number": 42, "title": "A bug", "body": "Details here"}])
    assert "#42 | 'A bug'" in result
    assert "Details here" in result


def test_build_corpus_text_multiple_items():
    corpus = [
        {"number": 1, "title": "First", "body": "Body one"},
        {"number": 2, "title": "Second", "body": "Body two"},
    ]
    result = build_corpus_text(corpus)
    assert "#1 | 'First'" in result
    assert "#2 | 'Second'" in result
    # Items separated by blank lines
    assert result.count("\n\n") >= 1


def test_build_corpus_text_repr_escapes_quotes():
    result = build_corpus_text([{"number": 1, "title": "She said \"hi\"", "body": "x"}])
    # title is repr'd so quotes are escaped
    assert "'She said" in result or '"She said' in result


# ---------------------------------------------------------------------------
# build_roster_text
# ---------------------------------------------------------------------------


def test_build_roster_text_empty():
    assert build_roster_text({}) == "(none)"


def test_build_roster_text_single_entry():
    result = build_roster_text({"99": "user@example.com"})
    assert result == "#99: user@example.com"


def test_build_roster_text_multiple_entries():
    result = build_roster_text({"1": "a@b.com", "2": "c@d.com"})
    lines = result.splitlines()
    assert len(lines) == 2
    assert "#1: a@b.com" in lines
    assert "#2: c@d.com" in lines


# ---------------------------------------------------------------------------
# find_repo_root
# ---------------------------------------------------------------------------


def test_find_repo_root_from_child_directory(tmp_path: Path):
    _make_repo(tmp_path)
    child = tmp_path / "a" / "b" / "c"
    child.mkdir(parents=True)
    assert find_repo_root(child) == tmp_path


def test_find_repo_root_from_repo_root_itself(tmp_path: Path):
    _make_repo(tmp_path)
    assert find_repo_root(tmp_path) == tmp_path


def test_find_repo_root_raises_when_no_git(tmp_path: Path):
    child = tmp_path / "orphan"
    child.mkdir()
    with pytest.raises(RuntimeError, match=r"\.git"):
        find_repo_root(child)


# ---------------------------------------------------------------------------
# extract_skill_section
# ---------------------------------------------------------------------------


def test_extract_skill_section_returns_until_next_same_level_heading(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        textwrap.dedent("""\
        ## Step 1

        Content for step 1.

        ## Step 2

        Content for step 2.
        """)
    )
    result = extract_skill_section(skill_md, "## Step 1")
    assert "Content for step 1" in result
    assert "Step 2" not in result


def test_extract_skill_section_stops_at_higher_level_heading(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        textwrap.dedent("""\
        ### Sub-step A

        Content A.

        ## Parent heading

        Other content.
        """)
    )
    result = extract_skill_section(skill_md, "### Sub-step A")
    assert "Content A" in result
    assert "Parent heading" not in result


def test_extract_skill_section_returns_rest_of_file_when_last_heading(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        textwrap.dedent("""\
        ## Only Section

        Everything here belongs to this section.
        No more headings after this.
        """)
    )
    result = extract_skill_section(skill_md, "## Only Section")
    assert "Everything here" in result
    assert "No more headings" in result


def test_extract_skill_section_ignores_heading_inside_code_fence(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        textwrap.dedent("""\
        ## Real Section

        Some intro.

        ```
        ## This looks like a heading but is in a fence
        code here
        ```

        More real content.

        ## Next Section

        Should not appear.
        """)
    )
    result = extract_skill_section(skill_md, "## Real Section")
    assert "More real content" in result
    assert "Next Section" not in result


def test_extract_skill_section_raises_on_missing_heading(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("## Existing\n\nContent.\n")
    with pytest.raises(ValueError, match="not found"):
        extract_skill_section(skill_md, "## Missing Heading")


def test_extract_skill_section_raises_on_invalid_heading_format(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("## A\n\nContent.\n")
    with pytest.raises(ValueError, match="does not look like a Markdown heading"):
        extract_skill_section(skill_md, "Not a heading")


def test_extract_skill_section_includes_heading_line_itself(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("## My Section\n\nBody.\n")
    result = extract_skill_section(skill_md, "## My Section")
    assert result.startswith("## My Section")


# ---------------------------------------------------------------------------
# load_step_config
# ---------------------------------------------------------------------------


def test_load_step_config_uses_step_config_json(tmp_path: Path):
    repo_root = _make_repo(tmp_path)
    skill_md = repo_root / "skills" / "my-skill" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("## Target Step\n\nPrompt content here.\n\n## Other Step\n\nNot this.\n")

    fixtures_dir = _make_fixtures_dir(
        repo_root / "step-dir",
        step_config={"skill_md": "skills/my-skill/SKILL.md", "step_heading": "## Target Step"},
    )
    system_prompt, user_prompt_template = load_step_config(fixtures_dir)
    assert "Prompt content here" in system_prompt
    assert "Other Step" not in system_prompt


def test_load_step_config_appends_output_spec(tmp_path: Path):
    repo_root = _make_repo(tmp_path)
    skill_md = repo_root / "SKILL.md"
    skill_md.write_text("## Step\n\nBase prompt.\n")

    fixtures_dir = _make_fixtures_dir(
        repo_root / "step-dir",
        step_config={"skill_md": "SKILL.md", "step_heading": "## Step"},
        output_spec="Return JSON only.",
    )
    system_prompt, _ = load_step_config(fixtures_dir)
    assert "Base prompt" in system_prompt
    assert "Return JSON only" in system_prompt


def test_load_step_config_falls_back_to_system_prompt_md(tmp_path: Path):
    fixtures_dir = _make_fixtures_dir(
        tmp_path / "step-dir",
        system_prompt="You are a helpful assistant.",
    )
    system_prompt, _ = load_step_config(fixtures_dir)
    assert "You are a helpful assistant" in system_prompt


def test_load_step_config_uses_custom_user_prompt_template(tmp_path: Path):
    fixtures_dir = _make_fixtures_dir(
        tmp_path / "step-dir",
        system_prompt="System.",
        user_prompt_template="Custom: {report}",
    )
    _, user_prompt_template = load_step_config(fixtures_dir)
    assert user_prompt_template == "Custom: {report}"


def test_load_step_config_uses_default_user_prompt_template_when_absent(tmp_path: Path):
    fixtures_dir = _make_fixtures_dir(
        tmp_path / "step-dir",
        system_prompt="System.",
    )
    _, user_prompt_template = load_step_config(fixtures_dir)
    assert "{corpus}" in user_prompt_template
    assert "{roster}" in user_prompt_template
    assert "{report}" in user_prompt_template


def test_load_step_config_raises_when_neither_config_present(tmp_path: Path):
    fixtures_dir = tmp_path / "empty-fixtures"
    fixtures_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        load_step_config(fixtures_dir)


# ---------------------------------------------------------------------------
# load_case
# ---------------------------------------------------------------------------


def test_load_case_loads_report_and_expected(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    case_dir = _make_case(fixtures_dir, "case-1", report="The report.", expected={"verdict": "duplicate"})

    corpus, roster, report, expected = load_case(case_dir)
    assert report == "The report."
    assert expected == {"verdict": "duplicate"}
    assert corpus == []
    assert roster == {}


def test_load_case_loads_optional_corpus(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    corpus_data = [{"number": 1, "title": "T", "body": "B"}]
    (fixtures_dir / "corpus.json").write_text(json.dumps(corpus_data))
    case_dir = _make_case(fixtures_dir, "case-1")

    corpus, _, _, _ = load_case(case_dir)
    assert corpus == corpus_data


def test_load_case_loads_optional_roster(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    roster_data = {"42": "reporter@example.com"}
    (fixtures_dir / "reporter-roster.json").write_text(json.dumps(roster_data))
    case_dir = _make_case(fixtures_dir, "case-1")

    _, roster, _, _ = load_case(case_dir)
    assert roster == roster_data


# ---------------------------------------------------------------------------
# find_cases
# ---------------------------------------------------------------------------


def test_find_cases_single_case_dir(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    case_dir = _make_case(fixtures_dir, "case-1")

    # Pass the case directory directly
    results = find_cases(case_dir)
    assert len(results) == 1
    assert results[0] == (case_dir, fixtures_dir)


def test_find_cases_fixtures_dir_with_multiple_cases(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    case1 = _make_case(fixtures_dir, "case-1")
    case2 = _make_case(fixtures_dir, "case-2")

    results = find_cases(fixtures_dir)
    assert len(results) == 2
    assert (case1, fixtures_dir) in results
    assert (case2, fixtures_dir) in results


def test_find_cases_recursive_skill_dir(tmp_path: Path):
    step1_fixtures = tmp_path / "step-1" / "fixtures"
    step2_fixtures = tmp_path / "step-2" / "fixtures"
    c1 = _make_case(step1_fixtures, "case-1")
    c2 = _make_case(step2_fixtures, "case-1")

    results = find_cases(tmp_path)
    assert len(results) == 2
    assert (c1, step1_fixtures) in results
    assert (c2, step2_fixtures) in results


def test_find_cases_returns_empty_for_no_cases(tmp_path: Path):
    empty_dir = tmp_path / "nothing"
    empty_dir.mkdir()
    assert find_cases(empty_dir) == []


def test_find_cases_deduplicates_nested_fixtures(tmp_path: Path):
    # A fixtures dir that itself contains another fixtures dir — the inner
    # one should not be double-counted.
    outer_fixtures = tmp_path / "step-1" / "fixtures"
    _make_case(outer_fixtures, "case-1")
    inner_fixtures = outer_fixtures / "nested" / "fixtures"
    _make_case(inner_fixtures, "case-inner")

    results = find_cases(tmp_path)
    fixtures_dirs = [f for _, f in results]
    assert fixtures_dirs.count(outer_fixtures) == 1


# ---------------------------------------------------------------------------
# main (CLI)
# ---------------------------------------------------------------------------


def test_main_exits_1_when_no_cases_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    empty = tmp_path / "empty"
    empty.mkdir()
    rc, _, stderr = _run_main(capsys, [str(empty)])
    assert rc == 1
    assert "No eval cases found" in stderr


def test_main_prints_case_header_and_expected(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    repo_root = _make_repo(tmp_path)
    skill_md = repo_root / "SKILL.md"
    skill_md.write_text("## My Step\n\nDo the thing.\n")

    fixtures_dir = _make_fixtures_dir(
        repo_root / "step-dir",
        step_config={"skill_md": "SKILL.md", "step_heading": "## My Step"},
    )
    _make_case(fixtures_dir, "case-1", expected={"result": "pass"})

    rc, stdout, _ = _run_main(capsys, [str(fixtures_dir)])
    assert rc == 0
    assert "CASE:" in stdout
    assert '"result": "pass"' in stdout


def test_main_quiet_suppresses_prompts(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    repo_root = _make_repo(tmp_path)
    skill_md = repo_root / "SKILL.md"
    skill_md.write_text("## Step\n\nSecret system prompt.\n")

    fixtures_dir = _make_fixtures_dir(
        repo_root / "step-dir",
        step_config={"skill_md": "SKILL.md", "step_heading": "## Step"},
    )
    _make_case(fixtures_dir, "case-1")

    rc, stdout, _ = _run_main(capsys, [str(fixtures_dir), "--quiet"])
    assert rc == 0
    assert "Secret system prompt" not in stdout
    assert "CASE:" in stdout
    assert "EXPECTED" in stdout


def test_main_prints_system_and_user_prompt_without_quiet(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    repo_root = _make_repo(tmp_path)
    skill_md = repo_root / "SKILL.md"
    skill_md.write_text("## Step\n\nSystem content here.\n")

    fixtures_dir = _make_fixtures_dir(
        repo_root / "step-dir",
        step_config={"skill_md": "SKILL.md", "step_heading": "## Step"},
    )
    _make_case(fixtures_dir, "case-1", report="The incoming report.")

    rc, stdout, _ = _run_main(capsys, [str(fixtures_dir)])
    assert rc == 0
    assert "SYSTEM PROMPT" in stdout
    assert "System content here" in stdout
    assert "USER PROMPT" in stdout
    assert "The incoming report" in stdout


def test_main_caches_step_config_across_cases(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Step config should be loaded once per fixtures dir even with multiple cases."""
    repo_root = _make_repo(tmp_path)
    skill_md = repo_root / "SKILL.md"
    skill_md.write_text("## Step\n\nPrompt.\n")

    fixtures_dir = _make_fixtures_dir(
        repo_root / "step-dir",
        step_config={"skill_md": "SKILL.md", "step_heading": "## Step"},
    )
    _make_case(fixtures_dir, "case-1")
    _make_case(fixtures_dir, "case-2")

    rc, stdout, _ = _run_main(capsys, [str(fixtures_dir)])
    assert rc == 0
    # Both cases should appear
    assert stdout.count("CASE:") == 2


def test_main_bad_user_prompt_template_raises(tmp_path: Path):
    """A malformed user-prompt-template.md with unknown slots raises an error."""
    repo_root = _make_repo(tmp_path)
    skill_md = repo_root / "SKILL.md"
    skill_md.write_text("## Step\n\nPrompt.\n")

    fixtures_dir = _make_fixtures_dir(
        repo_root / "step-dir",
        step_config={"skill_md": "SKILL.md", "step_heading": "## Step"},
        user_prompt_template="Hello {unknown_slot}",
    )
    _make_case(fixtures_dir, "case-1")

    with pytest.raises(KeyError):
        main([str(fixtures_dir)])
