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

"""Tests for ``check-doc-sync.py``.

Every test builds a miniature repository in ``tmp_path`` and runs one check
against it. The point of each is the **red** case: a gate that cannot fail is
worse than no gate, because a green run reads as evidence while measuring
nothing. So each check is exercised in both directions — drift is reported, and
the corrected tree is silent.

The script's filename is hyphenated, which is not an importable module name, so
it is loaded through ``importlib.util``.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "check-doc-sync.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_doc_sync", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    """A miniature repo, cd'd into — the script resolves paths relative to cwd."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "tools" / "spec-loop" / "specs").mkdir(parents=True)
    (tmp_path / "tools" / "dev").mkdir(parents=True)
    (tmp_path / "docs" / "setup").mkdir(parents=True)
    prev = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(prev)


def _skill(repo: Path, name: str, family: str, mode: str) -> None:
    d = repo / "skills" / name
    d.mkdir()
    (d / "SKILL.md").write_text(
        f"---\nname: magpie-{name}\nfamily: {family}\nmode: {mode}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def _errors(fn, *args) -> list[str]:
    errs: list[str] = []
    fn(errs, *args)
    return errs


# ---------------------------------------------------------------------------
# 1. Spec-index completeness
# ---------------------------------------------------------------------------


def _specs(repo: Path, names: list[str], listed_in_overview: list[str], listed_in_readme: list[str]) -> None:
    specs = repo / "tools" / "spec-loop" / "specs"
    for n in names:
        (specs / n).write_text(f"# {n}\n", encoding="utf-8")
    (specs / "overview.md").write_text(
        "\n".join(f"| Area | [{n}]({n}) |" for n in listed_in_overview), encoding="utf-8"
    )
    (specs / "README.md").write_text(
        "\n".join(f"- [`{n}`]({n})," for n in listed_in_readme), encoding="utf-8"
    )


def test_spec_listed_in_both_indexes_is_silent(repo: Path) -> None:
    _specs(repo, ["adapters.md"], ["adapters.md"], ["adapters.md"])
    assert _errors(mod.check_spec_index) == []


def test_spec_missing_from_overview_is_reported(repo: Path) -> None:
    _specs(repo, ["adapters.md"], [], ["adapters.md"])
    errs = _errors(mod.check_spec_index)
    assert len(errs) == 1
    assert "overview.md" in errs[0] and "adapters.md" in errs[0]


def test_spec_missing_from_readme_is_reported(repo: Path) -> None:
    """Listed in one index is not listed. This is the real-world shape: ten
    specs were in neither, and a spec in only one reads as indexed."""
    _specs(repo, ["adapters.md"], ["adapters.md"], [])
    errs = _errors(mod.check_spec_index)
    assert len(errs) == 1
    assert "README.md" in errs[0]


def test_index_files_are_not_themselves_specs(repo: Path) -> None:
    _specs(repo, [], [], [])
    assert _errors(mod.check_spec_index) == []


# ---------------------------------------------------------------------------
# 2. Per-family counts in README.md
# ---------------------------------------------------------------------------


def _readme_family(repo: Path, family: str, declared: int) -> None:
    (repo / "README.md").write_text(
        "| Family | Type | Modes | Purpose | Detail |\n|---|---|---|---|---|\n"
        f"| [**{family}**](docs/{family}/README.md) | opt-in | Triage | Does things. "
        f"| {declared} skills, [`docs/{family}/`](docs/{family}/) |\n",
        encoding="utf-8",
    )


def test_matching_family_count_is_silent(repo: Path) -> None:
    _skill(repo, "a", "security", "Triage")
    _skill(repo, "b", "security", "Triage")
    _readme_family(repo, "security", 2)
    assert _errors(mod.check_readme_family_counts) == []


def test_stale_family_count_is_reported_with_both_numbers(repo: Path) -> None:
    _skill(repo, "a", "security", "Triage")
    _skill(repo, "b", "security", "Triage")
    _skill(repo, "c", "security", "Drafting")
    _readme_family(repo, "security", 2)
    errs = _errors(mod.check_readme_family_counts)
    assert len(errs) == 1
    assert "says 2 skills" in errs[0] and "has 3" in errs[0]


def test_table_row_that_is_not_a_family_is_ignored(repo: Path) -> None:
    """The table carries rows whose bolded cell names no skill family. Those
    must not be read as a family with a wrong count."""
    _skill(repo, "a", "security", "Triage")
    _readme_family(repo, "not-a-family", 99)
    assert _errors(mod.check_readme_family_counts) == []


# ---------------------------------------------------------------------------
# 3. Per-mode counts in docs/modes.md
# ---------------------------------------------------------------------------


def _modes(repo: Path, rows: list[tuple[str, int]]) -> None:
    body = "\n".join(f"| **{m}** | *(Agentic {m})* Does things. | stable | {n} |" for m, n in rows)
    (repo / "docs" / "modes.md").write_text(
        "# Modes\n\n## Modes at a glance\n\n"
        "| Mode | Purpose | Status | Skill count |\n|---|---|---|---|\n" + body + "\n\n## Triage\n",
        encoding="utf-8",
    )


def test_matching_mode_count_is_silent(repo: Path) -> None:
    _skill(repo, "a", "security", "Triage")
    _modes(repo, [("Triage", 1)])
    assert _errors(mod.check_modes_glance_counts) == []


def test_stale_mode_count_is_reported(repo: Path) -> None:
    _skill(repo, "a", "security", "Triage")
    _skill(repo, "b", "security", "Triage")
    _modes(repo, [("Triage", 1)])
    errs = _errors(mod.check_modes_glance_counts)
    assert len(errs) == 1
    assert "says 1 skills" in errs[0] and "has 2" in errs[0]


def test_mode_with_no_skills_must_declare_zero(repo: Path) -> None:
    """A deliberately-off mode declares 0. A non-zero count for a mode nothing
    uses is drift, not an exemption."""
    _skill(repo, "a", "security", "Triage")
    _modes(repo, [("Triage", 1), ("Agentic Autonomous", 0)])
    assert _errors(mod.check_modes_glance_counts) == []

    _modes(repo, [("Triage", 1), ("Agentic Autonomous", 4)])
    errs = _errors(mod.check_modes_glance_counts)
    assert len(errs) == 1
    assert "no skill declares that mode" in errs[0]


def test_missing_glance_table_is_not_an_error(repo: Path) -> None:
    (repo / "docs" / "modes.md").write_text("# Modes\n\nNo glance table here.\n", encoding="utf-8")
    assert _errors(mod.check_modes_glance_counts) == []


# ---------------------------------------------------------------------------
# 4. Catalogue totals in prose
# ---------------------------------------------------------------------------


def test_matching_total_is_silent(repo: Path) -> None:
    (repo / "docs" / "setup" / "marketplaces.md").write_text("Installs 2 skills.\n", encoding="utf-8")
    assert _errors(mod.check_total_counts, 2) == []


def test_every_stale_total_is_reported_not_just_the_first(repo: Path) -> None:
    (repo / "docs" / "setup" / "marketplaces.md").write_text(
        "Installs 71 skills.\nAll 71 skills load.\nThe 71 skills are namespaced.\n", encoding="utf-8"
    )
    errs = _errors(mod.check_total_counts, 74)
    assert len(errs) == 3
    assert all("says 71 skills" in e and "has 74" in e for e in errs)


def test_totals_check_reads_only_the_allowlist(repo: Path) -> None:
    """A doc outside the allowlist may legitimately count a subset — 'Nine
    skills cover the staged path' — so a greedy scan would flag it forever."""
    (repo / "docs" / "elsewhere.md").write_text("Nine skills cover the staged path.\n", encoding="utf-8")
    assert _errors(mod.check_total_counts, 74) == []


# ---------------------------------------------------------------------------
# 5. Per-family plugin counts in the marketplace tables
# ---------------------------------------------------------------------------


def _plugin_table(repo: Path, rows: list[str], *, path: str = "docs/setup/marketplaces.md") -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "| Family plugin | Skills | ~Always-on tokens |\n|---|---|---|\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def test_matching_plugin_counts_are_silent(repo: Path) -> None:
    _skill(repo, "a", "security", "Triage")
    _skill(repo, "b", "security", "Triage")
    _skill(repo, "c", "pairing", "Pairing")
    _plugin_table(repo, ["| `magpie-security` | 2 | ~0.6k |", "| `magpie-pairing` | 1 | ~0.3k |"])
    assert _errors(mod.check_family_plugin_counts, 3) == []


def test_stale_plugin_count_is_reported_with_both_numbers(repo: Path) -> None:
    """The drift this check was written for: `magpie-security` sat at 12 while
    three more security skills had landed."""
    _skill(repo, "a", "security", "Triage")
    _skill(repo, "b", "security", "Triage")
    _plugin_table(repo, ["| `magpie-security` | 12 | ~3.9k |"])
    errs = _errors(mod.check_family_plugin_counts, 2)
    assert len(errs) == 1
    assert "says 12 skills" in errs[0] and "has 2" in errs[0]


def test_stale_all_in_one_row_is_reported(repo: Path) -> None:
    _skill(repo, "a", "security", "Triage")
    _plugin_table(repo, ["| **`magpie`** (all) | **70** | **~21.7k** |"])
    errs = _errors(mod.check_family_plugin_counts, 1)
    assert len(errs) == 1
    assert "all-in-one" in errs[0] and "says 70" in errs[0]


def test_plugin_naming_no_live_family_is_reported(repo: Path) -> None:
    """A renamed or deleted family leaves a row pointing at nothing — silence
    there would let the table advertise an uninstallable plugin."""
    _skill(repo, "a", "security", "Triage")
    _plugin_table(repo, ["| `magpie-ghost` | 3 | ~0.9k |"])
    errs = _errors(mod.check_family_plugin_counts, 1)
    assert len(errs) == 1
    assert "names no live family" in errs[0]


def test_plugin_counts_are_checked_in_the_quick_start_too(repo: Path) -> None:
    _skill(repo, "a", "setup", "Triage")
    _plugin_table(repo, ["| `magpie-setup` | 9 | Sandbox, install |"], path="docs/quick-start.md")
    errs = _errors(mod.check_family_plugin_counts, 1)
    assert len(errs) == 1
    assert "docs/quick-start.md" in errs[0]


def test_prose_mentioning_a_plugin_is_not_a_table_row(repo: Path) -> None:
    """Only a leading table cell counts — `magpie-security` named mid-sentence,
    or in a bulleted trade-off list, carries no count to check."""
    _skill(repo, "a", "security", "Triage")
    (repo / "docs" / "setup" / "marketplaces.md").write_text(
        "Install `magpie-security` for 12 reasons.\n"
        "- \u2705 `magpie-security` \u2248 3.9k always-on tokens.\n",
        encoding="utf-8",
    )
    assert _errors(mod.check_family_plugin_counts, 1) == []


# ---------------------------------------------------------------------------
# 6. Per-family skill counts in the family READMEs
# ---------------------------------------------------------------------------


def _family_readme(repo: Path, directory: str, plugin_family: str, declared: int) -> None:
    target = repo / "docs" / directory / "README.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# {directory}\n\n## Install & first runs\n\n"
        f"Install just this family — one plugin, {declared} skills.\n\n"
        f"```text\n/plugin install magpie-{plugin_family}@apache-magpie\n```\n",
        encoding="utf-8",
    )


def test_matching_family_readme_count_is_silent(repo: Path) -> None:
    _skill(repo, "a", "pairing", "Pairing")
    _skill(repo, "b", "pairing", "Pairing")
    _family_readme(repo, "pairing", "pairing", 2)
    assert _errors(mod.check_family_readme_counts) == []


def test_stale_family_readme_count_is_reported(repo: Path) -> None:
    _skill(repo, "a", "pairing", "Pairing")
    _family_readme(repo, "pairing", "pairing", 9)
    errs = _errors(mod.check_family_readme_counts)
    assert len(errs) == 1
    assert "says 9 skills" in errs[0] and "has 1" in errs[0]


def test_family_is_read_from_the_install_command_not_the_directory(repo: Path) -> None:
    """`issue` documents itself under docs/issue-management/, so keying on the
    directory name would report every one of its skills as missing."""
    _skill(repo, "a", "issue", "Triage")
    _family_readme(repo, "issue-management", "issue", 1)
    assert _errors(mod.check_family_readme_counts) == []


def test_readme_without_an_install_section_is_skipped(repo: Path) -> None:
    (repo / "docs" / "education").mkdir(parents=True)
    (repo / "docs" / "education" / "README.md").write_text(
        "# education\n\nNine skills cover the staged path.\n", encoding="utf-8"
    )
    assert _errors(mod.check_family_readme_counts) == []


def test_install_section_naming_a_dead_family_is_reported(repo: Path) -> None:
    _skill(repo, "a", "pairing", "Pairing")
    _family_readme(repo, "ghost", "ghost", 3)
    errs = _errors(mod.check_family_readme_counts)
    assert len(errs) == 1
    assert "no live family" in errs[0]


# ---------------------------------------------------------------------------
# 7. No plugin-name stutter in the docs
# ---------------------------------------------------------------------------


def test_stuttering_invocation_is_reported(repo: Path) -> None:
    """`/magpie-security:security-issue-triage` is a command nobody can run —
    the family plugin advertises the alias `issue-triage`."""
    _skill(repo, "security-issue-triage", "security", "Triage")
    (repo / "docs" / "guide.md").write_text(
        "Run `/magpie-security:security-issue-triage` to triage.\n", encoding="utf-8"
    )
    errs = _errors(mod.check_no_plugin_name_stutter)
    assert len(errs) == 1
    assert "repeats the family name" in errs[0]


def test_first_segment_stutter_is_caught_too(repo: Path) -> None:
    """`release-*` skills sit in `release-management`, so the repeated token is
    the family's first segment."""
    _skill(repo, "release-vote-tally", "release-management", "Drafting")
    (repo / "docs" / "guide.md").write_text(
        "Run `/magpie-release-management:release-vote-tally`.\n", encoding="utf-8"
    )
    assert len(_errors(mod.check_no_plugin_name_stutter)) == 1


def test_the_dealiased_form_is_silent(repo: Path) -> None:
    _skill(repo, "security-issue-triage", "security", "Triage")
    (repo / "docs" / "guide.md").write_text(
        "Run `/magpie-security:issue-triage` to triage.\n", encoding="utf-8"
    )
    assert _errors(mod.check_no_plugin_name_stutter) == []


def test_the_portable_single_token_form_is_not_a_stutter(repo: Path) -> None:
    """Snapshot installs really do invoke `/magpie-security-issue-triage`; the
    guard must not chase the form it is documenting as correct elsewhere."""
    _skill(repo, "security-issue-triage", "security", "Triage")
    (repo / "docs" / "guide.md").write_text(
        "Snapshot installs use `/magpie-security-issue-triage`.\n", encoding="utf-8"
    )
    assert _errors(mod.check_no_plugin_name_stutter) == []


def test_eval_fixtures_are_not_scanned(repo: Path) -> None:
    """Fixtures are expected outputs, not documentation."""
    _skill(repo, "security-issue-triage", "security", "Triage")
    fixture = repo / "tools" / "skill-evals" / "evals" / "x"
    fixture.mkdir(parents=True)
    (fixture / "expected.md").write_text("`/magpie-security:security-issue-triage`\n", encoding="utf-8")
    assert _errors(mod.check_no_plugin_name_stutter) == []


def test_a_marked_line_may_show_the_stutter(repo: Path) -> None:
    """marketplaces.md documents the anti-pattern, so it has to print one."""
    _skill(repo, "security-issue-triage", "security", "Triage")
    (repo / "docs" / "guide.md").write_text(
        f"`/magpie-security:security-issue-triage` says security twice. {mod.STUTTER_ALLOW}\n",
        encoding="utf-8",
    )
    assert _errors(mod.check_no_plugin_name_stutter) == []


def test_the_marker_only_exempts_its_own_line(repo: Path) -> None:
    _skill(repo, "security-issue-triage", "security", "Triage")
    (repo / "docs" / "guide.md").write_text(
        f"bad example {mod.STUTTER_ALLOW}\n`/magpie-security:security-issue-triage`\n",
        encoding="utf-8",
    )
    assert len(_errors(mod.check_no_plugin_name_stutter)) == 1


# ---------------------------------------------------------------------------
# 8. The portable single-token form must say which install it means
# ---------------------------------------------------------------------------


def _doc(repo: Path, body: str, name: str = "guide.md") -> None:
    (repo / "docs" / name).write_text(body, encoding="utf-8")


def test_portable_form_without_a_note_is_reported(repo: Path) -> None:
    """The marketplace install is the default, so a bare `/magpie-issue-triage`
    reads as a command the reader can run — and it is not."""
    _skill(repo, "issue-triage", "issue", "Triage")
    _doc(repo, "Run `/magpie-issue-triage` to triage.\n")
    errs = _errors(mod.check_portable_form_is_flagged)
    assert len(errs) == 1
    assert "snapshot-install form" in errs[0]


def test_a_page_that_states_the_install_is_silent(repo: Path) -> None:
    _skill(repo, "issue-triage", "issue", "Triage")
    for note in mod.PORTABLE_FORM_NOTES:
        _doc(repo, f"{note}. Run `/magpie-issue-triage`.\n")
        assert _errors(mod.check_portable_form_is_flagged) == []


def test_the_setup_mechanism_is_never_flagged(repo: Path) -> None:
    """`/magpie-setup` names the install mechanism, not a skill a marketplace
    user invokes, so it stays legal on every page."""
    _skill(repo, "setup", "setup", "Triage")
    _doc(repo, "Run `/magpie-setup upgrade` to refresh the snapshot.\n")
    assert _errors(mod.check_portable_form_is_flagged) == []


def test_a_filesystem_path_is_not_an_invocation(repo: Path) -> None:
    """`.agents/skills/magpie-<skill>/` appears in `test -f` assertions in the
    spec files; flagging those would demand breaking them."""
    _skill(repo, "issue-triage", "issue", "Triage")
    _doc(repo, "test -f .agents/skills/magpie-issue-triage/SKILL.md\n")
    assert _errors(mod.check_portable_form_is_flagged) == []


def test_allowlisted_pages_may_show_both_forms(repo: Path) -> None:
    _skill(repo, "issue-triage", "issue", "Triage")
    (repo / "docs" / "setup").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "setup" / "marketplaces.md").write_text(
        "Portable: `/magpie-issue-triage`.\n", encoding="utf-8"
    )
    assert _errors(mod.check_portable_form_is_flagged) == []


# ---------------------------------------------------------------------------
# 9. Dev scripts are documented
# ---------------------------------------------------------------------------


def _dev(repo: Path, scripts: list[str], readme_names: list[str]) -> None:
    dev = repo / "tools" / "dev"
    for s in scripts:
        (dev / s).write_text("#!/bin/sh\n", encoding="utf-8")
    (dev / "README.md").write_text(
        "\n".join(f"| [`{n}`]({n}) | does a thing |" for n in readme_names), encoding="utf-8"
    )


def test_documented_scripts_are_silent(repo: Path) -> None:
    _dev(repo, ["check-a.py", "check-b.sh"], ["check-a.py", "check-b.sh"])
    assert _errors(mod.check_dev_scripts_documented) == []


def test_undocumented_script_is_reported(repo: Path) -> None:
    _dev(repo, ["check-a.py", "check-b.sh"], ["check-a.py"])
    errs = _errors(mod.check_dev_scripts_documented)
    assert len(errs) == 1
    assert "check-b.sh" in errs[0]


def test_non_script_files_are_not_required_to_be_documented(repo: Path) -> None:
    _dev(repo, [], [])
    (repo / "tools" / "dev" / "notes.txt").write_text("scratch\n", encoding="utf-8")
    (repo / "tools" / "dev" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert _errors(mod.check_dev_scripts_documented) == []


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_exits_2_outside_a_repo_root(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "skills").rmdir()
    assert mod.main() == 2
    assert "run from the repository root" in capsys.readouterr().err


def test_main_exits_1_and_names_every_problem(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _skill(repo, "a", "security", "Triage")
    _readme_family(repo, "security", 9)
    _modes(repo, [("Triage", 9)])
    _specs(repo, ["adapters.md"], [], [])
    _dev(repo, ["check-x.sh"], [])
    (repo / "docs" / "setup" / "marketplaces.md").write_text("Installs 9 skills.\n", encoding="utf-8")

    assert mod.main() == 1
    err = capsys.readouterr().err
    for fragment in ("family 'security'", "mode 'Triage'", "adapters.md", "check-x.sh", "says 9 skills"):
        assert fragment in err


def test_main_exits_0_on_a_consistent_tree(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _skill(repo, "a", "security", "Triage")
    _readme_family(repo, "security", 1)
    _modes(repo, [("Triage", 1)])
    _specs(repo, ["adapters.md"], ["adapters.md"], ["adapters.md"])
    _dev(repo, ["check-x.sh"], ["check-x.sh"])
    (repo / "docs" / "setup" / "marketplaces.md").write_text("Installs 1 skills.\n", encoding="utf-8")

    assert mod.main() == 0
    assert "OK" in capsys.readouterr().out
