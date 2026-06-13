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
import shlex
import textwrap
from pathlib import Path

import pytest

from skill_evals.runner import (
    DEFAULT_GRADER_CLI,
    DEFAULT_PROSE_FIELDS,
    batch_grade_prose_fields,
    batch_judge_assertions,
    build_corpus_text,
    build_roster_text,
    collect_diffs,
    collect_tag_counts,
    compare_outputs,
    compare_structural,
    compare_with_grader,
    evaluate_deterministic_assertion,
    extract_json_from_output,
    extract_skill_section,
    find_cases,
    find_repo_root,
    grade_prose_field,
    is_structural_expected,
    load_assertions,
    load_case,
    load_case_tags,
    load_grading_schema,
    load_step_config,
    main,
    run_cli,
)

_TESTS_DIR = Path(__file__).resolve().parent
_GRADER_YES = f"python3 {_TESTS_DIR / '_grader_yes.py'}"
_GRADER_NO = f"python3 {_TESTS_DIR / '_grader_no.py'}"
_JUDGE_YES = f"python3 {_TESTS_DIR / '_judge_yes.py'}"
_JUDGE_NO = f"python3 {_TESTS_DIR / '_judge_no.py'}"


def _grader_count_cli(counter_path: Path) -> str:
    """Return a grader-cli string that records each call to ``counter_path``.

    Wrapped in ``bash -c`` so the env-var prefix is honoured: ``run_cli`` now
    uses ``shell=False`` with ``shlex.split``, which would otherwise treat
    ``GRADER_COUNTER_FILE=...`` as a literal argv[0] binary name.
    """
    script = _TESTS_DIR / "_grader_count.py"
    inner = f"GRADER_COUNTER_FILE={shlex.quote(str(counter_path))} python3 {shlex.quote(str(script))}"
    return f"bash -c {shlex.quote(inner)}"


def _count_grader_calls(counter_path: Path) -> int:
    if not counter_path.exists():
        return 0
    return sum(1 for _ in counter_path.read_text().splitlines() if _)


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


def _make_case(
    fixtures_dir: Path, name: str, *, report: str = "report text", expected: dict | None = None
) -> Path:
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
    result = build_corpus_text([{"number": 1, "title": 'She said "hi"', "body": "x"}])
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
    system_prompt, _user_prompt_template = load_step_config(fixtures_dir)
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


def test_load_case_tags_missing_meta_returns_empty_set(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    case_dir = _make_case(fixtures_dir, "case-1")
    assert load_case_tags(case_dir) == set()


def test_load_case_tags_reads_case_meta(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    case_dir = _make_case(fixtures_dir, "case-1")
    (case_dir / "case-meta.json").write_text(json.dumps({"tags": ["llama", "smoke"]}))
    assert load_case_tags(case_dir) == {"llama", "smoke"}


def test_load_case_tags_rejects_non_string_tags(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    case_dir = _make_case(fixtures_dir, "case-1")
    (case_dir / "case-meta.json").write_text(json.dumps({"tags": ["llama", 3]}))
    with pytest.raises(ValueError, match="tags"):
        load_case_tags(case_dir)


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


# ---------------------------------------------------------------------------
# is_structural_expected
# ---------------------------------------------------------------------------


def test_is_structural_expected_plain_kvs():
    assert is_structural_expected({"class": "BUG", "confidence": "high"}) is False


def test_is_structural_expected_has_flag():
    assert is_structural_expected({"has_security_model_quote": True}) is True


def test_is_structural_expected_mention_list():
    assert is_structural_expected({"mention_handles": ["@alice"]}) is True


def test_is_structural_expected_non_dict():
    assert is_structural_expected(["a", "b"]) is False  # type: ignore[arg-type]


def test_is_structural_expected_empty_dict():
    assert is_structural_expected({}) is False


# ---------------------------------------------------------------------------
# extract_json_from_output
# ---------------------------------------------------------------------------


def test_extract_json_whole_output():
    value, err = extract_json_from_output('{"verdict": "ok"}')
    assert err is None
    assert value == {"verdict": "ok"}


def test_extract_json_whole_output_with_whitespace():
    value, err = extract_json_from_output('\n  {"verdict": "ok"}\n\n')
    assert err is None
    assert value == {"verdict": "ok"}


def test_extract_json_fenced_block():
    text = 'Here is the output:\n\n```json\n{"verdict": "ok"}\n```\n\nThank you.'
    value, err = extract_json_from_output(text)
    assert err is None
    assert value == {"verdict": "ok"}


def test_extract_json_bare_fenced_block():
    text = 'Result:\n```\n{"verdict": "ok"}\n```'
    value, err = extract_json_from_output(text)
    assert err is None
    assert value == {"verdict": "ok"}


def test_extract_json_largest_brace_block():
    text = 'I think the answer is {"verdict": "ok"} based on the data.'
    value, err = extract_json_from_output(text)
    assert err is None
    assert value == {"verdict": "ok"}


def test_extract_json_picks_largest_brace_block():
    text = 'Small: {"a": 1}. Larger and correct: {"verdict": "ok", "rationale": "longer text here"}.'
    value, err = extract_json_from_output(text)
    assert err is None
    assert value == {"verdict": "ok", "rationale": "longer text here"}


def test_extract_json_array_top_level():
    value, err = extract_json_from_output("[1, 2, 3]")
    assert err is None
    assert value == [1, 2, 3]


def test_extract_json_no_json_returns_error():
    value, err = extract_json_from_output("Just prose, no JSON anywhere.")
    assert value is None
    assert err is not None and "no JSON" in err


def test_extract_json_empty_output_returns_error():
    value, err = extract_json_from_output("")
    assert value is None
    assert err is not None


def test_extract_json_malformed_braces_returns_error():
    value, err = extract_json_from_output('{"verdict": missing-quotes}')
    assert value is None
    assert err is not None


# ---------------------------------------------------------------------------
# compare_outputs
# ---------------------------------------------------------------------------


def test_compare_outputs_equal_dicts():
    ok, diff = compare_outputs({"a": 1, "b": 2}, {"a": 1, "b": 2})
    assert ok is True
    assert diff == ""


def test_compare_outputs_dict_key_order_irrelevant():
    ok, _ = compare_outputs({"b": 2, "a": 1}, {"a": 1, "b": 2})
    assert ok is True


def test_compare_outputs_unequal_dicts_show_diff():
    ok, diff = compare_outputs({"class": "BUG"}, {"class": "INVALID"})
    assert ok is False
    assert "BUG" in diff
    assert "INVALID" in diff


def test_compare_outputs_unequal_marks_added_and_removed():
    ok, diff = compare_outputs({"a": 1}, {"a": 1, "b": 2})
    assert ok is False
    assert "+" in diff or "-" in diff


# ---------------------------------------------------------------------------
# --cli mode integration
# ---------------------------------------------------------------------------


def _make_cli_case(tmp_path: Path, *, expected: dict, report: str = "the report") -> tuple[Path, Path]:
    """Build a minimal fixtures dir + one case dir; return (fixtures_dir, case_dir)."""
    repo_root = _make_repo(tmp_path)
    skill_md = repo_root / "SKILL.md"
    skill_md.write_text("## Step\n\nSystem instructions.\n")
    fixtures_dir = _make_fixtures_dir(
        repo_root / "step-dir",
        step_config={"skill_md": "SKILL.md", "step_heading": "## Step"},
        user_prompt_template="Report: {report}\n",
    )
    case_dir = _make_case(fixtures_dir, "case-1", report=report, expected=expected)
    return fixtures_dir, case_dir


def test_cli_mode_pass_with_echo(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """A CLI that echoes the expected JSON should PASS."""
    expected = {"verdict": "ok"}
    fixtures_dir, _ = _make_cli_case(tmp_path, expected=expected)
    rc, stdout, _ = _run_main(
        capsys,
        ["--cli", f"echo '{json.dumps(expected)}'", str(fixtures_dir)],
    )
    assert rc == 0
    assert "PASS" in stdout
    assert "1 passed" in stdout


def test_cli_mode_fail_with_wrong_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """A CLI that returns the wrong JSON should FAIL and exit non-zero."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    rc, stdout, _ = _run_main(
        capsys,
        ["--cli", 'echo \'{"verdict": "wrong"}\'', str(fixtures_dir)],
    )
    assert rc == 1
    assert "FAIL" in stdout
    assert "1 failed" in stdout


def test_cli_mode_fail_with_wrong_jsons(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """A CLI that returns the wrong JSONS should FAIL with multiple failures and exit non-zero."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    _make_case(fixtures_dir, "case-2", report="another report", expected={"verdict": "ok"})
    rc, stdout, _ = _run_main(
        capsys,
        ["--cli", 'echo \'{"verdict": "wrong"}\'', str(fixtures_dir)],
    )
    assert rc == 1
    assert "FAIL" in stdout
    assert (
        "2 failed" in stdout
    )  # asserts that behaviour doesn't changes and outputs exactly 2 failures instead of stopping at the first one, which is tested in the next test case


def test_cli_model_with_fail_fast_and_wrong_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """With --fail-fast, the runner should stop at the first failure and not run further cases."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    # Add a second case that would FAIL if it ran, but should be skipped due to fail-fast.
    _make_case(fixtures_dir, "case-2", report="another report", expected={"verdict": "ok"})
    rc, stdout, _ = _run_main(
        capsys,
        ["--cli", 'echo \'{"verdict": "wrong"}\'', "--fail-fast", str(fixtures_dir)],
    )
    assert rc == 1
    assert "FAIL" in stdout
    assert "1 failed" in stdout
    assert "CASE: case-2" not in stdout  # second case should not run at all


def test_cli_model_with_fail_fast_and_error_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """In timeout being negative raise internal error when run_cli is called and --fail-fast is used."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "wrong"})
    _make_case(fixtures_dir, "case-2", report="another report", expected={"verdict": "ok"})
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            'echo \'{"verdict": "wrong"}\'',
            "--timeout",
            "-1",  # force an error (timeout) instead of a fail, to check that fail-fast also applies to errors
            "--exact",
            "--fail-fast",
            str(fixtures_dir),
        ],
    )
    assert rc == 1
    assert "ERROR" in stdout
    assert "1 errored" in stdout
    assert "CASE: case-2" not in stdout  # second case should not run at all


def test_cli_mode_manual_skips_structural(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Structural expected.json (has_* / mention_*) is reported MANUAL, not auto-compared."""
    fixtures_dir, _ = _make_cli_case(
        tmp_path, expected={"has_security_model_quote": True, "mention_handles": []}
    )
    rc, stdout, _ = _run_main(
        capsys,
        # CLI would return junk; runner should not even invoke it for MANUAL cases.
        # (`false` rather than `exit 1` because the runner uses shell=False;
        # `exit` is a shell builtin and would not be found as a binary.)
        ["--cli", "false", str(fixtures_dir)],
    )
    assert rc == 0
    assert "MANUAL" in stdout
    assert "1 manual" in stdout


def test_cli_mode_non_json_under_exact_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """In --exact mode, prose with no JSON returns ERROR and exits non-zero."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            "echo 'just prose, no JSON here'",
            "--exact",
            str(fixtures_dir),
        ],
    )
    assert rc == 1
    assert "ERROR" in stdout
    assert "1 errored" in stdout


def test_cli_mode_non_json_wraps_and_passes_under_field_aware(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Default field-aware mode wraps prose as {"raw_output": ...} so the
    intersection-only comparator can proceed. With expected.json declaring
    no raw_output key, the case passes."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            "echo 'just prose, no JSON here'",
            "--grader-cli",
            _GRADER_YES,  # not actually invoked; no overlapping keys
            str(fixtures_dir),
        ],
    )
    assert rc == 0
    assert "PASS" in stdout
    assert "1 passed" in stdout


def test_cli_mode_non_json_wrap_can_assert_on_raw_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Suite authors who want to gate on the prose can declare raw_output
    in expected.json; the wrapped actual carries the model's prose and a
    mismatch is a real decision-level failure."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"raw_output": "this exact prose\n"})
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            "echo 'different prose'",
            "--grader-cli",
            _GRADER_YES,
            str(fixtures_dir),
        ],
    )
    assert rc == 1
    assert "FAIL" in stdout
    assert "raw_output" in stdout


def test_cli_mode_non_zero_exit_under_exact_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """In --exact mode, a non-zero CLI exit still returns ERROR and exits non-zero."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    rc, stdout, _ = _run_main(capsys, ["--cli", "false", "--exact", str(fixtures_dir)])
    assert rc == 1
    assert "ERROR" in stdout


def test_cli_mode_non_zero_exit_wraps_under_field_aware(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """In the default field-aware mode, a non-zero CLI exit is wrapped as
    raw_output (+ stderr + exit_code) and the intersection-only comparator
    decides whether the case passes."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            "false",
            "--grader-cli",
            _GRADER_YES,
            str(fixtures_dir),
        ],
    )
    assert rc == 0
    assert "PASS" in stdout


def test_cli_mode_extracts_json_from_fenced_response(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """The runner should find JSON inside a ```json fence in the CLI's stdout."""
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    # printf interprets escapes so we get a real fenced block on stdout.
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            'printf \'Sure!\\n\\n```json\\n{"verdict": "ok"}\\n```\\n\'',
            str(fixtures_dir),
        ],
    )
    assert rc == 0
    assert "PASS" in stdout


def test_cli_mode_summary_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Multiple cases should be summarised correctly."""
    expected = {"verdict": "ok"}
    fixtures_dir, _ = _make_cli_case(tmp_path, expected=expected)
    # Add a second case that will FAIL by reusing the same fixtures dir.
    _make_case(fixtures_dir, "case-2-fail", report="x", expected={"verdict": "different"})
    rc, stdout, _ = _run_main(
        capsys,
        ["--cli", f"echo '{json.dumps(expected)}'", str(fixtures_dir)],
    )
    assert rc == 1  # because one case FAILs
    assert "1 passed" in stdout
    assert "1 failed" in stdout


def test_tag_filter_runs_only_matching_cases(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--tag should restrict discovered cases before invoking the CLI."""
    expected = {"verdict": "ok"}
    fixtures_dir, case_dir = _make_cli_case(tmp_path, expected=expected)
    _make_case(fixtures_dir, "case-2-untagged", report="x", expected={"verdict": "different"})
    (case_dir / "case-meta.json").write_text(json.dumps({"tags": ["llama"]}))

    rc, stdout, _ = _run_main(
        capsys,
        ["--tag", "llama", "--cli", f"echo '{json.dumps(expected)}'", str(fixtures_dir)],
    )
    assert rc == 0
    assert "1 passed" in stdout
    assert "case-2-untagged" not in stdout


def test_list_tags_prints_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--list-tags prints distinct tags with per-tag case counts."""
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    case1 = _make_case(fixtures_dir, "case-1")
    case2 = _make_case(fixtures_dir, "case-2")
    (case1 / "case-meta.json").write_text(json.dumps({"tags": ["llama"]}))
    (case2 / "case-meta.json").write_text(json.dumps({"tags": ["qwen", "llama"]}))

    rc, stdout, stderr = _run_main(capsys, [str(fixtures_dir), "--list-tags"])
    assert rc == 0
    assert stderr == ""
    assert stdout.strip().splitlines() == ["llama 2", "qwen 1"]


def test_list_tags_no_tags_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--list-tags exits 0 with an informational line when no tags exist."""
    fixtures_dir = tmp_path / "fixtures"
    _make_case(fixtures_dir, "case-1")

    rc, stdout, stderr = _run_main(capsys, [str(fixtures_dir), "--list-tags"])
    assert rc == 0
    assert stderr == ""
    assert stdout.strip() == "no tags found"


def test_collect_tag_counts(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    case1 = _make_case(fixtures_dir, "case-1")
    case2 = _make_case(fixtures_dir, "case-2")
    (case1 / "case-meta.json").write_text(json.dumps({"tags": ["alpha"]}))
    (case2 / "case-meta.json").write_text(json.dumps({"tags": ["alpha", "beta"]}))

    counts = collect_tag_counts(find_cases(fixtures_dir))
    assert counts == {"alpha": 2, "beta": 1}


# ---------------------------------------------------------------------------
# load_grading_schema
# ---------------------------------------------------------------------------


def test_load_grading_schema_defaults_when_no_file(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    assert load_grading_schema(fixtures_dir) == set(DEFAULT_PROSE_FIELDS)


def test_load_grading_schema_override_replaces_default(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "grading-schema.json").write_text(json.dumps({"prose_fields": ["why"]}))
    assert load_grading_schema(fixtures_dir) == {"why"}


def test_load_grading_schema_empty_list_disables_grader(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "grading-schema.json").write_text(json.dumps({"prose_fields": []}))
    assert load_grading_schema(fixtures_dir) == set()


def test_load_grading_schema_rejects_non_string_entries(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "grading-schema.json").write_text(json.dumps({"prose_fields": ["why", 7]}))
    with pytest.raises(ValueError, match="prose_fields"):
        load_grading_schema(fixtures_dir)


def test_load_grading_schema_missing_key_falls_back_to_default(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "grading-schema.json").write_text(json.dumps({"unrelated": True}))
    assert load_grading_schema(fixtures_dir) == set(DEFAULT_PROSE_FIELDS)


# ---------------------------------------------------------------------------
# grade_prose_field (single-field helper retained for callers that want
# per-field grading; the main runner path uses the batched grader below.)
# ---------------------------------------------------------------------------


def test_grade_prose_field_short_circuits_on_exact_equality():
    # Identical values should pass without invoking any CLI.
    ok, note = grade_prose_field("$.reason", "boom", "boom", grader_cli="false", timeout=5)
    assert ok is True
    assert note == ""


def test_grade_prose_field_grader_says_match():
    grader = 'echo \'{"match": true, "reason": "same meaning"}\''
    ok, note = grade_prose_field("$.reason", "the build failed", "build broke", grader_cli=grader, timeout=5)
    assert ok is True
    assert note == ""


def test_grade_prose_field_grader_says_no():
    grader = 'echo \'{"match": false, "reason": "different conclusion"}\''
    ok, note = grade_prose_field(
        "$.reason", "the build failed", "the build passed", grader_cli=grader, timeout=5
    )
    assert ok is False
    assert "$.reason" in note
    assert "different conclusion" in note


def test_grade_prose_field_grader_returns_garbage():
    ok, note = grade_prose_field("$.reason", "x", "y", grader_cli="echo 'not json at all'", timeout=5)
    assert ok is False
    assert "$.reason" in note


def test_grade_prose_field_grader_non_zero_exit():
    ok, note = grade_prose_field("$.reason", "x", "y", grader_cli="false", timeout=5)
    assert ok is False
    assert "$.reason" in note


# ---------------------------------------------------------------------------
# collect_diffs (pure walker; no grader calls)
# ---------------------------------------------------------------------------


def test_collect_diffs_no_diff_when_equal():
    d, p = collect_diffs({"verdict": "BUG"}, {"verdict": "BUG"}, prose_fields=set())
    assert d == []
    assert p == []


def test_collect_diffs_decision_scalar_mismatch_is_decision_only():
    d, p = collect_diffs({"verdict": "X"}, {"verdict": "Y"}, prose_fields={"reason"})
    assert any("verdict" in m for m in d)
    assert p == []


def test_collect_diffs_prose_mismatch_yields_pair():
    d, p = collect_diffs(
        {"verdict": "BUG", "reason": "wording A"},
        {"verdict": "BUG", "reason": "wording B"},
        prose_fields={"reason"},
    )
    assert d == []
    assert len(p) == 1
    path, exp, act = p[0]
    assert path == "$.reason"
    assert exp == "wording B"
    assert act == "wording A"


def test_collect_diffs_nested_list_of_prose_fields_yields_multiple_pairs():
    actual = {"items": [{"reason": "a"}, {"reason": "c"}]}
    expected = {"items": [{"reason": "b"}, {"reason": "d"}]}
    d, p = collect_diffs(actual, expected, prose_fields={"reason"})
    assert d == []
    assert [pair[0] for pair in p] == ["$.items[0].reason", "$.items[1].reason"]


def test_collect_diffs_missing_key_in_actual_is_skipped():
    """Expected declares 'b'; actual omits it. Skipped, not failed —
    expected.json is a description of values where the model speaks, not a
    required-keys schema."""
    d, p = collect_diffs({"a": 1}, {"a": 1, "b": 2}, prose_fields=set())
    assert d == []
    assert p == []


def test_collect_diffs_extra_keys_in_actual_are_ignored():
    """Only the intersection is asserted; extras in actual pass."""
    d, p = collect_diffs({"a": 1, "extra": "anything"}, {"a": 1}, prose_fields=set())
    assert d == []
    assert p == []


def test_collect_diffs_intersection_value_mismatch_still_fails():
    """Keys present in both that differ in value still fail."""
    d, _ = collect_diffs({"a": 2, "extra": "x"}, {"a": 1, "b": 2}, prose_fields=set())
    assert any("a" in m for m in d)


def test_collect_diffs_empty_actual_passes_against_any_expected():
    """Document the trade-off: a model returning {} matches any expected.
    Suite authors should keep expected.json focused on the keys that
    actually carry the eval's signal."""
    d, p = collect_diffs({}, {"a": 1, "b": 2, "c": [1, 2]}, prose_fields=set())
    assert d == []
    assert p == []


def test_collect_diffs_length_mismatch_is_decision():
    d, _ = collect_diffs({"items": [1, 2]}, {"items": [1, 2, 3]}, prose_fields=set())
    assert any("length mismatch" in m for m in d)


def test_collect_diffs_equal_prose_does_not_emit_pair():
    d, p = collect_diffs({"reason": "same"}, {"reason": "same"}, prose_fields={"reason"})
    assert d == []
    assert p == []


# ---------------------------------------------------------------------------
# batch_grade_prose_fields
# ---------------------------------------------------------------------------


def test_batch_grade_empty_pairs_makes_no_grader_call(tmp_path: Path):
    counter = tmp_path / "calls"
    result = batch_grade_prose_fields([], _grader_count_cli(counter), timeout=5)
    assert result == {}
    assert _count_grader_calls(counter) == 0


def test_batch_grade_single_pair_one_call(tmp_path: Path):
    counter = tmp_path / "calls"
    pairs = [("$.reason", "expected", "actual")]
    result = batch_grade_prose_fields(pairs, _grader_count_cli(counter), timeout=5)
    assert _count_grader_calls(counter) == 1
    assert result["$.reason"] == (True, "")


def test_batch_grade_many_pairs_one_call(tmp_path: Path):
    """Headline guarantee: N prose mismatches → 1 grader call."""
    counter = tmp_path / "calls"
    pairs = [
        ("$.a", "x", "y"),
        ("$.b", "x", "y"),
        ("$.c.d", "x", "y"),
        ("$.list[0].reason", "x", "y"),
    ]
    result = batch_grade_prose_fields(pairs, _grader_count_cli(counter), timeout=5)
    assert _count_grader_calls(counter) == 1
    for path, _, _ in pairs:
        assert result[path] == (True, "")


def test_batch_grade_grader_says_no():
    pairs = [("$.reason", "expected", "actual")]
    result = batch_grade_prose_fields(pairs, _GRADER_NO, timeout=5)
    ok, note = result["$.reason"]
    assert ok is False
    assert "differs" in note


def test_batch_grade_grader_failure_marks_all_fail():
    pairs = [("$.a", "x", "y"), ("$.b", "x", "y")]
    result = batch_grade_prose_fields(pairs, "false", timeout=5)
    for path, _, _ in pairs:
        ok, _ = result[path]
        assert ok is False


# ---------------------------------------------------------------------------
# compare_with_grader (uses the batched grader path)
# ---------------------------------------------------------------------------


def test_compare_with_grader_passes_when_decision_fields_match_and_prose_judged_match():
    actual = {"verdict": "BUG", "reason": "the system crashes on a null record"}
    expected = {"verdict": "BUG", "reason": "crashes on null input"}
    ok, msgs = compare_with_grader(
        actual,
        expected,
        prose_fields={"reason"},
        grader_cli=_GRADER_YES,
        timeout=5,
    )
    assert ok is True
    assert msgs == []


def test_compare_with_grader_skips_grader_when_decision_field_differs(tmp_path: Path):
    """Decision-field failure must not invoke the grader."""
    counter = tmp_path / "calls"
    actual = {"verdict": "INVALID", "reason": "wording A"}
    expected = {"verdict": "BUG", "reason": "wording B"}
    ok, msgs = compare_with_grader(
        actual,
        expected,
        prose_fields={"reason"},
        grader_cli=_grader_count_cli(counter),
        timeout=5,
    )
    assert ok is False
    assert _count_grader_calls(counter) == 0
    assert any("verdict" in m for m in msgs)


def test_compare_with_grader_multiple_prose_mismatches_one_call(tmp_path: Path):
    counter = tmp_path / "calls"
    actual = {
        "verdict": "BUG",
        "reason": "a",
        "follow_up": [{"reason": "c"}, {"reason": "e"}],
    }
    expected = {
        "verdict": "BUG",
        "reason": "b",
        "follow_up": [{"reason": "d"}, {"reason": "f"}],
    }
    ok, msgs = compare_with_grader(
        actual,
        expected,
        prose_fields={"reason"},
        grader_cli=_grader_count_cli(counter),
        timeout=5,
    )
    assert ok is True, msgs
    assert _count_grader_calls(counter) == 1


def test_compare_with_grader_fails_when_grader_says_no():
    actual = {"verdict": "BUG", "reason": "crashes on overflow"}
    expected = {"verdict": "BUG", "reason": "null pointer on init"}
    ok, msgs = compare_with_grader(
        actual,
        expected,
        prose_fields={"reason"},
        grader_cli=_GRADER_NO,
        timeout=5,
    )
    assert ok is False
    assert any("reason" in m for m in msgs)


def test_compare_with_grader_handles_nested_list_of_dicts():
    actual = {
        "overall": "fail",
        "follow_up": [
            {"skill": "install", "reason": "missing hook script"},
            {"skill": "update", "reason": "stale claude-code version"},
        ],
    }
    expected = {
        "overall": "fail",
        "follow_up": [
            {"skill": "install", "reason": "hooks/scripts not installed"},
            {"skill": "update", "reason": "claude-code is older than pinned version"},
        ],
    }
    ok, msgs = compare_with_grader(
        actual,
        expected,
        prose_fields={"reason"},
        grader_cli=_GRADER_YES,
        timeout=5,
    )
    assert ok is True
    assert msgs == []


def test_compare_with_grader_no_prose_diff_no_grader_call(tmp_path: Path):
    counter = tmp_path / "calls"
    ok, _ = compare_with_grader(
        {"verdict": "BUG", "reason": "same"},
        {"verdict": "BUG", "reason": "same"},
        prose_fields={"reason"},
        grader_cli=_grader_count_cli(counter),
        timeout=5,
    )
    assert ok is True
    assert _count_grader_calls(counter) == 0


# ---------------------------------------------------------------------------
# --grader-cli end-to-end
# ---------------------------------------------------------------------------


def test_cli_grader_mode_passes_on_wording_difference(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Same verdict, different prose in `reason` — grader-cli mode should PASS."""
    expected = {"verdict": "BUG", "reason": "crashes on null input"}
    actual = {"verdict": "BUG", "reason": "null pointer on first call"}
    fixtures_dir, _ = _make_cli_case(tmp_path, expected=expected)
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            f"echo '{json.dumps(actual)}'",
            "--grader-cli",
            _GRADER_YES,
            str(fixtures_dir),
        ],
    )
    assert rc == 0, stdout
    assert "PASS" in stdout
    assert "1 passed" in stdout


def test_cli_grader_mode_fails_on_decision_field_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Decision field (verdict) differs — must FAIL even if grader would say YES."""
    expected = {"verdict": "BUG", "reason": "same"}
    actual = {"verdict": "INVALID", "reason": "same"}
    fixtures_dir, _ = _make_cli_case(tmp_path, expected=expected)
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            f"echo '{json.dumps(actual)}'",
            "--grader-cli",
            _GRADER_YES,
            str(fixtures_dir),
        ],
    )
    assert rc == 1
    assert "FAIL" in stdout
    assert "verdict" in stdout


def test_cli_grader_mode_fails_when_grader_rejects_prose(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Decision match, but grader says prose differs."""
    expected = {"verdict": "BUG", "reason": "crashes on null input"}
    actual = {"verdict": "BUG", "reason": "totally unrelated text"}
    fixtures_dir, _ = _make_cli_case(tmp_path, expected=expected)
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            f"echo '{json.dumps(actual)}'",
            "--grader-cli",
            _GRADER_NO,
            str(fixtures_dir),
        ],
    )
    assert rc == 1
    assert "FAIL" in stdout
    assert "reason" in stdout


def test_cli_grader_mode_respects_grading_schema_override(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """grading-schema.json with prose_fields=[] forces exact compare on `reason`."""
    expected = {"verdict": "BUG", "reason": "crashes on null input"}
    actual = {"verdict": "BUG", "reason": "null pointer on first call"}
    fixtures_dir, _ = _make_cli_case(tmp_path, expected=expected)
    (fixtures_dir / "grading-schema.json").write_text(json.dumps({"prose_fields": []}))
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            f"echo '{json.dumps(actual)}'",
            "--grader-cli",
            _GRADER_YES,  # would say YES, but reason should be graded exact now
            str(fixtures_dir),
        ],
    )
    assert rc == 1
    assert "FAIL" in stdout
    assert "reason" in stdout


def test_grader_cli_requires_cli_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    with pytest.raises(SystemExit):
        main(["--grader-cli", _GRADER_YES, str(fixtures_dir)])
    err = capsys.readouterr().err
    assert "require --cli" in err


def test_exact_requires_cli_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    fixtures_dir, _ = _make_cli_case(tmp_path, expected={"verdict": "ok"})
    with pytest.raises(SystemExit):
        main(["--exact", str(fixtures_dir)])
    err = capsys.readouterr().err
    assert "require --cli" in err


def test_default_grader_constant_is_haiku():
    # Defending the documented default so a future rename doesn't silently
    # change cost characteristics for users.
    assert "haiku" in DEFAULT_GRADER_CLI


def test_exact_mode_falls_back_to_verbatim_comparison(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """With --exact, a wording-only diff on a prose field should FAIL."""
    expected = {"verdict": "BUG", "reason": "null input crash"}
    actual = {"verdict": "BUG", "reason": "different wording"}
    fixtures_dir, _ = _make_cli_case(tmp_path, expected=expected)
    rc, stdout, _ = _run_main(
        capsys,
        [
            "--cli",
            f"echo '{json.dumps(actual)}'",
            "--exact",
            str(fixtures_dir),
        ],
    )
    assert rc == 1
    assert "FAIL" in stdout


def test_default_grader_not_invoked_when_decision_field_differs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """If only decision fields differ, the grader is never called, so the
    default (claude -p --model haiku) does not need to exist on PATH."""
    expected = {"verdict": "BUG"}
    actual = {"verdict": "INVALID"}
    fixtures_dir, _ = _make_cli_case(tmp_path, expected=expected)
    # Do NOT pass --grader-cli or --exact: rely on the default grader being
    # un-invoked. If it were invoked, the test would error (claude not on PATH).
    rc, stdout, _ = _run_main(
        capsys,
        ["--cli", f"echo '{json.dumps(actual)}'", str(fixtures_dir)],
    )
    assert rc == 1
    assert "FAIL" in stdout
    assert "verdict" in stdout


# ---------------------------------------------------------------------------
# run_cli — the shell=False / shlex.split invocation contract
# ---------------------------------------------------------------------------


def test_run_cli_returns_stdout_and_zero_rc():
    stdout, _stderr, rc = run_cli("python3 -c \"print('hi')\"", "", timeout=10)
    assert rc == 0
    assert stdout.strip() == "hi"


def test_run_cli_passes_prompt_on_stdin():
    # `cat` echoes whatever arrives on stdin; the prompt must reach it.
    stdout, _stderr, rc = run_cli("cat", "hello-from-stdin", timeout=10)
    assert rc == 0
    assert stdout == "hello-from-stdin"


def test_run_cli_reports_non_zero_exit():
    _stdout, _stderr, rc = run_cli('python3 -c "import sys; sys.exit(3)"', "", timeout=10)
    assert rc == 3


def test_run_cli_bare_env_prefix_is_not_a_command():
    # Regression guard for the _grader_count_cli fix: because run_cli uses
    # shell=False with shlex.split, a leading `VAR=value` is tokenised as a
    # literal argv[0] binary name, which does not exist -> OSError. The env
    # assignment is NOT honoured by a shell. This is why the test helper must
    # wrap the inner command in `bash -c`.
    with pytest.raises(OSError):
        run_cli("FOO=bar python3 -c \"import os; print(os.environ['FOO'])\"", "", timeout=10)


def test_run_cli_bash_c_honours_env_prefix():
    # The fix: wrapping in `bash -c` lets the env assignment take effect.
    inner = "FOO=bar python3 -c \"import os; print(os.environ['FOO'])\""
    stdout, _stderr, rc = run_cli(f"bash -c {shlex.quote(inner)}", "", timeout=10)
    assert rc == 0
    assert stdout.strip() == "bar"


# ---------------------------------------------------------------------------
# Structural assertions: load_assertions
# ---------------------------------------------------------------------------


def test_load_assertions_absent_returns_empty(tmp_path: Path):
    assert load_assertions(tmp_path) == {}


def test_load_assertions_reads_specs(tmp_path: Path):
    (tmp_path / "assertions.json").write_text(
        json.dumps({"has_x": {"field": "body", "type": "contains", "substring": "x"}})
    )
    specs = load_assertions(tmp_path)
    assert specs["has_x"]["type"] == "contains"


def test_load_assertions_rejects_unknown_type(tmp_path: Path):
    (tmp_path / "assertions.json").write_text(json.dumps({"has_x": {"type": "bogus"}}))
    with pytest.raises(ValueError, match="invalid type"):
        load_assertions(tmp_path)


def test_load_assertions_rejects_non_object_spec(tmp_path: Path):
    (tmp_path / "assertions.json").write_text(json.dumps({"has_x": "nope"}))
    with pytest.raises(ValueError, match="must be an object"):
        load_assertions(tmp_path)


# ---------------------------------------------------------------------------
# Structural assertions: evaluate_deterministic_assertion
# ---------------------------------------------------------------------------


def test_assert_regex_match_and_flags():
    spec = {"field": "body", "type": "regex", "pattern": "download page.*https?://", "flags": "is"}
    holds, _ = evaluate_deterministic_assertion(spec, {"body": "Download Page\n  https://x"})
    assert holds is True


def test_assert_regex_no_match():
    spec = {"field": "body", "type": "regex", "pattern": "KEYS"}
    holds, _ = evaluate_deterministic_assertion(spec, {"body": "no link here"})
    assert holds is False


def test_assert_contains_case_insensitive():
    spec = {"field": "body", "type": "contains", "substring": "APACHE.ORG", "flags": "i"}
    holds, _ = evaluate_deterministic_assertion(spec, {"body": "from your @apache.org address"})
    assert holds is True


def test_assert_contains_all_reports_missing():
    spec = {"field": "body", "type": "contains_all", "substrings": ["a", "z"]}
    holds, note = evaluate_deterministic_assertion(spec, {"body": "a only"})
    assert holds is False
    assert "z" in note


def test_assert_empty_true_for_empty_list_and_missing():
    spec = {"field": "scope_violations", "type": "empty"}
    assert evaluate_deterministic_assertion(spec, {"scope_violations": []})[0] is True
    assert evaluate_deterministic_assertion(spec, {})[0] is True
    assert evaluate_deterministic_assertion(spec, {"scope_violations": ["x"]})[0] is False


def test_assert_field_true():
    spec = {"field": "proposed", "type": "field_true"}
    assert evaluate_deterministic_assertion(spec, {"proposed": True})[0] is True
    assert evaluate_deterministic_assertion(spec, {"proposed": False})[0] is False
    assert evaluate_deterministic_assertion(spec, {})[0] is False


def test_assert_missing_field_for_text_predicate_is_false():
    spec = {"field": "body", "type": "contains", "substring": "x"}
    holds, note = evaluate_deterministic_assertion(spec, {})
    assert holds is False
    assert "not present" in note


def test_assert_missing_pattern_is_spec_error():
    spec = {"field": "body", "type": "regex"}
    holds, note = evaluate_deterministic_assertion(spec, {"body": "x"})
    assert holds is None
    assert "pattern" in note


# ---------------------------------------------------------------------------
# Structural assertions: batch_judge_assertions
# ---------------------------------------------------------------------------


def test_batch_judge_empty_makes_no_call():
    assert batch_judge_assertions({}, {"a": 1}, "false", 10) == {}


def test_batch_judge_yes():
    specs = {"has_flag": {"type": "judge", "rubric": "is it flagged"}}
    grades = batch_judge_assertions(specs, {"body": "x"}, _JUDGE_YES, 10)
    assert grades["has_flag"][0] is True


def test_batch_judge_grader_error_returns_none():
    specs = {"has_flag": {"type": "judge", "rubric": "is it flagged"}}
    holds, note = batch_judge_assertions(specs, {"body": "x"}, "false", 10)["has_flag"]
    assert holds is None
    assert "exited" in note


# ---------------------------------------------------------------------------
# Structural assertions: compare_structural
# ---------------------------------------------------------------------------


def _assertions(deterministic_only: bool = False) -> dict:
    specs = {
        "has_keys_link": {"field": "body", "type": "regex", "pattern": r"https?://\S*KEYS", "flags": "i"},
        "has_skip_note": {"field": "body", "type": "regex", "pattern": "skip-promote-wait", "flags": "i"},
    }
    if not deterministic_only:
        specs["has_injection_flagged"] = {"type": "judge", "rubric": "flagged?"}
    return specs


def test_compare_structural_pass_mixed():
    expected = {"backend": "announce-list", "has_keys_link": True, "has_skip_note": False}
    actual = {"backend": "announce-list", "body": "Keys: https://dist.apache.org/KEYS"}
    ok, notes = compare_structural(
        actual,
        expected,
        _assertions(deterministic_only=True),
        prose_fields=set(),
        grader_cli=_GRADER_YES,
        exact=False,
        grader_timeout=10,
    )
    assert ok, notes


def test_compare_structural_fails_on_decision_field():
    expected = {"backend": "announce-list", "has_keys_link": True}
    actual = {"backend": "github-release-notes", "body": "https://x/KEYS"}
    ok, notes = compare_structural(
        actual,
        expected,
        _assertions(deterministic_only=True),
        prose_fields=set(),
        grader_cli=_GRADER_YES,
        exact=False,
        grader_timeout=10,
    )
    assert not ok
    assert any("backend" in n for n in notes)


def test_compare_structural_fails_on_assertion_mismatch():
    expected = {"has_skip_note": False}
    actual = {"body": "[SKIP-PROMOTE-WAIT: overridden]"}
    ok, notes = compare_structural(
        actual,
        expected,
        _assertions(deterministic_only=True),
        prose_fields=set(),
        grader_cli=_GRADER_YES,
        exact=False,
        grader_timeout=10,
    )
    assert not ok
    assert any("has_skip_note" in n for n in notes)


def test_compare_structural_missing_assertion_fails_loudly():
    expected = {"has_undeclared": True}
    ok, notes = compare_structural(
        {"body": "x"},
        expected,
        {},
        prose_fields=set(),
        grader_cli=_GRADER_YES,
        exact=False,
        grader_timeout=10,
    )
    assert not ok
    assert any("no assertion defined" in n for n in notes)


def test_compare_structural_judge_disagreement_fails():
    expected = {"has_injection_flagged": True}
    ok, notes = compare_structural(
        {"injection_summary": "ignored injection"},
        expected,
        _assertions(),
        prose_fields=set(),
        grader_cli=_JUDGE_NO,
        exact=False,
        grader_timeout=10,
    )
    assert not ok
    assert any("has_injection_flagged" in n for n in notes)
