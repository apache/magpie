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
# 5. Dev scripts are documented
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
