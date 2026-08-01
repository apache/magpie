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

"""Tests for the spec-scope deterministic mapper."""

from __future__ import annotations

from pathlib import Path

from spec_inventory import (
    _changed_path_candidates,
    extract_path_patterns,
    scope_main,
    scope_map,
)


def _spec_text(where_bullets: str) -> str:
    return (
        "\n---\ntitle: Test Spec\nstatus: experimental\nkind: feature\n"
        "mode: infra\nsource: tests\n---\n\n## Where it lives\n\n" + where_bullets + "\n"
    )


def test_extract_path_patterns_tool_path() -> None:
    bullets = ["`tools/gmail/` — private-mail read/draft."]
    assert "tools/gmail" in extract_path_patterns(bullets)


def test_extract_path_patterns_skill_name() -> None:
    bullets = ["Skill: `pr-management-triage` — first-pass sweep of the PR queue."]
    patterns = extract_path_patterns(bullets)
    assert "skills/pr-management-triage" in patterns


def test_extract_path_patterns_doc_path() -> None:
    bullets = ["`docs/education/` — landing page for the education stream."]
    assert "docs/education" in extract_path_patterns(bullets)


def test_extract_path_patterns_ignores_no_slash_tokens() -> None:
    # A backtick-quoted token with no slash is not treated as a path.
    bullets = ["Some bullet with `SKILL.md` and `README.md` tokens."]
    patterns = extract_path_patterns(bullets)
    assert "SKILL.md" not in patterns
    assert "README.md" not in patterns


def test_extract_path_patterns_strips_trailing_slash() -> None:
    bullets = ["`tools/example/` — example tool directory."]
    patterns = extract_path_patterns(bullets)
    # trailing slash must be stripped so prefix matching works
    assert "tools/example" in patterns
    assert "tools/example/" not in patterns


def test_extract_path_patterns_empty() -> None:
    assert extract_path_patterns([]) == frozenset()


def test_extract_path_patterns_multiple_bullets() -> None:
    bullets = [
        "`tools/gmail/` — private-mail read.",
        "Skill: `pr-management-triage` — sweep.",
        "`docs/modes.md` — modes documentation.",
    ]
    patterns = extract_path_patterns(bullets)
    assert "tools/gmail" in patterns
    assert "skills/pr-management-triage" in patterns
    assert "docs/modes.md" in patterns


def test_changed_path_candidates_normal() -> None:
    assert _changed_path_candidates("tools/gmail/tool.md") == ["tools/gmail/tool.md"]


def test_changed_path_candidates_leading_slash_stripped() -> None:
    candidates = _changed_path_candidates("/tools/gmail/tool.md")
    assert "tools/gmail/tool.md" in candidates


def test_changed_path_candidates_skill_symlink() -> None:
    candidates = _changed_path_candidates(".claude/skills/magpie-pr-management-triage")
    assert ".claude/skills/magpie-pr-management-triage" in candidates
    assert "skills/pr-management-triage" in candidates


def test_changed_path_candidates_skill_symlink_non_magpie_prefix_unchanged() -> None:
    # A .claude/skills/ entry without the magpie- prefix is not synthesised.
    candidates = _changed_path_candidates(".claude/skills/some-other-skill")
    assert len(candidates) == 1
    assert candidates[0] == ".claude/skills/some-other-skill"


def test_scope_map_matches_tool_path(tmp_path: Path) -> None:
    specs_dir = tmp_path / "tools" / "spec-loop" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "adapters.md").write_text(
        _spec_text("- `tools/gmail/` — private-mail read/draft.\n- `tools/ponymail/` — archive.\n")
    )
    (specs_dir / "other.md").write_text(_spec_text("- `tools/something-else/`\n"))

    result = scope_map(["tools/gmail/tool.md"], tmp_path)

    assert "tools/spec-loop/specs/adapters.md" in result
    assert "tools/spec-loop/specs/other.md" not in result


def test_scope_map_matches_skill_symlink(tmp_path: Path) -> None:
    specs_dir = tmp_path / "tools" / "spec-loop" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "pr-management-family.md").write_text(
        _spec_text("- Skill: `pr-management-triage` — sweep.\n")
    )

    result = scope_map([".claude/skills/magpie-pr-management-triage"], tmp_path)

    assert "tools/spec-loop/specs/pr-management-family.md" in result


def test_scope_map_empty_paths(tmp_path: Path) -> None:
    specs_dir = tmp_path / "tools" / "spec-loop" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "example.md").write_text(_spec_text("- `tools/example/`\n"))

    assert scope_map([], tmp_path) == []


def test_scope_map_no_match(tmp_path: Path) -> None:
    specs_dir = tmp_path / "tools" / "spec-loop" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "example.md").write_text(_spec_text("- `tools/example/`\n"))

    assert scope_map(["tools/other-tool/main.py"], tmp_path) == []


def test_scope_map_returns_sorted_deduplicated(tmp_path: Path) -> None:
    specs_dir = tmp_path / "tools" / "spec-loop" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "aaa.md").write_text(_spec_text("- `tools/shared/`\n"))
    (specs_dir / "zzz.md").write_text(_spec_text("- `tools/shared/`\n"))

    # Two paths that both match the same two specs — result must be sorted and deduplicated.
    result = scope_map(["tools/shared/a.py", "tools/shared/b.py"], tmp_path)
    assert result == sorted(result)
    assert len(result) == len(set(result))
    assert len(result) == 2


def test_scope_map_docs_modes_md(tmp_path: Path) -> None:
    specs_dir = tmp_path / "tools" / "spec-loop" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "triage-mode.md").write_text(_spec_text("- `docs/modes.md` — modes index.\n"))

    result = scope_map(["docs/modes.md"], tmp_path)
    assert "tools/spec-loop/specs/triage-mode.md" in result


def test_scope_main_cli_reads_stdin(tmp_path: Path, monkeypatch: object) -> None:
    """scope_main reads paths from positional arguments and prints matching specs."""
    specs_dir = tmp_path / "tools" / "spec-loop" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "example.md").write_text(_spec_text("- `tools/example/`\n"))

    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    import io
    import sys as _sys

    captured = io.StringIO()
    monkeypatch.setattr(_sys, "stdout", captured)  # type: ignore[attr-defined]

    scope_main(["tools/example/main.py", "--repo-root", str(tmp_path)])

    output = captured.getvalue().strip()
    assert "tools/spec-loop/specs/example.md" in output


def test_extract_path_patterns_plural_skills_bullet() -> None:
    # Four specs in the tree write "Skills:" (plural), not "Skill:".  The
    # singular-only form silently produced no patterns for them.
    bullets = ["Skills: `write-skill` (author/update a skill), `optimize-skill`"]
    patterns = extract_path_patterns(bullets)
    assert "skills/write-skill" in patterns
    assert "skills/optimize-skill" in patterns


def test_extract_path_patterns_suffix_shorthand_replaces_last_segment() -> None:
    # agent-isolation-sandbox.md: `-update` means setup-isolated-setup-update.
    bullets = ["Skills: `setup-isolated-setup-install`, `-update`, `-verify`, `-doctor`"]
    patterns = extract_path_patterns(bullets)
    assert "skills/setup-isolated-setup-install" in patterns
    assert "skills/setup-isolated-setup-update" in patterns
    assert "skills/setup-isolated-setup-verify" in patterns
    assert "skills/setup-isolated-setup-doctor" in patterns


def test_extract_path_patterns_suffix_shorthand_appends() -> None:
    # security-issue-lifecycle.md: `-from-pr` means security-issue-import-from-pr.
    bullets = ["Skills: `security-issue-import` (+ `-from-pr`, `-from-md`)"]
    patterns = extract_path_patterns(bullets)
    assert "skills/security-issue-import" in patterns
    assert "skills/security-issue-import-from-pr" in patterns
    assert "skills/security-issue-import-from-md" in patterns


def test_extract_path_patterns_bare_top_level_dir_is_not_a_pattern() -> None:
    # Guard, not a bug fix: the trailing slash is stripped *before* the
    # slash test, so `tools/` becomes `tools`, fails the test, and is
    # dropped.  Reordering those two steps would make this spec match every
    # path under tools/, so pin the behaviour.  Real case:
    # skill-reconciler.md has "a `uv` tool under `tools/`" in Where it lives.
    bullets = ["Optional deterministic helper (not yet built): a `uv` tool under `tools/`"]
    patterns = extract_path_patterns(bullets)
    assert "tools" not in patterns


def test_scope_map_bare_top_level_dir_does_not_over_match(tmp_path: Path) -> None:
    # End-to-end companion to the guard above: a spec whose only path token
    # is a bare top-level directory must not be returned for every change
    # beneath it.
    specs = tmp_path / "tools" / "spec-loop" / "specs"
    specs.mkdir(parents=True)
    (tmp_path / ".git").mkdir()
    (specs / "broad.md").write_text(_spec_text("- a helper under `tools/`\n"))
    (specs / "narrow.md").write_text(_spec_text("- `tools/gmail/` — mail bridge.\n"))

    result = scope_map(["tools/gmail/client.py"], tmp_path)

    assert "tools/spec-loop/specs/narrow.md" in result
    assert "tools/spec-loop/specs/broad.md" not in result


def test_scope_map_matches_plural_skills_bullet(tmp_path: Path) -> None:
    specs = tmp_path / "tools" / "spec-loop" / "specs"
    specs.mkdir(parents=True)
    (tmp_path / ".git").mkdir()
    (specs / "sandbox.md").write_text(
        _spec_text("- Skills: `setup-isolated-setup-install`, `-update`, `-verify`\n")
    )

    result = scope_map(["skills/setup-isolated-setup-verify/SKILL.md"], tmp_path)

    assert "tools/spec-loop/specs/sandbox.md" in result
