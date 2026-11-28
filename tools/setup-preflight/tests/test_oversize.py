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

"""The oversize check: a branch that grows a skill or AGENTS.md past its budget."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from setup_preflight import cli, sections
from setup_preflight.oversize import findings, main, measure_skill

from .conftest import write_stamp

ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, **ENV},
    )
    return done.stdout


def skill(body_chars: int, description: str = "Short.") -> str:
    return f"---\nname: demo\ndescription: {description}\n---\n\n" + "x" * body_chars + "\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository on `main` with one small skill and a small AGENTS.md, then a feature branch."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "skills" / "demo").mkdir(parents=True)
    (root / "skills" / "demo" / "SKILL.md").write_text(skill(100))
    (root / "AGENTS.md").write_text("# rules\n" + "y" * 1000)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    git(root, "switch", "-q", "-c", "feature")
    return root


def codes(root: Path) -> list[dict[str, object]]:
    found = findings(root)
    assert all(f.section == "oversize" for f in found)
    files: list[dict[str, object]] = []
    for f in found:
        listed = f.facts["files"]
        assert isinstance(listed, list)
        files.extend(listed)
    return files


def test_an_untouched_branch_reports_nothing(repo: Path) -> None:
    assert findings(repo) == []


def test_a_skill_body_grown_past_the_budget_is_reported(repo: Path) -> None:
    (repo / "skills" / "demo" / "SKILL.md").write_text(skill(5001 * 4))
    [file] = codes(repo)
    assert file["path"] == "skills/demo/SKILL.md"
    assert file["over"] == ["body_tokens"]
    assert file["optimizer"] == "optimize-skill"
    assert file["base"]["body_tokens"] < 5000  # type: ignore[index]


def test_a_committed_change_counts_as_well_as_a_working_tree_one(repo: Path) -> None:
    (repo / "skills" / "demo" / "SKILL.md").write_text(skill(5001 * 4))
    git(repo, "commit", "-q", "-am", "grow")
    assert [f["path"] for f in codes(repo)] == ["skills/demo/SKILL.md"]


def test_an_always_on_description_past_200_tokens_is_reported(repo: Path) -> None:
    (repo / "skills" / "demo" / "SKILL.md").write_text(skill(100, "d" * 900))
    [file] = codes(repo)
    assert file["over"] == ["always_on_tokens"]


def test_the_preflight_block_is_not_counted_in_the_body(repo: Path) -> None:
    block = "<!-- BEGIN MAGPIE PREFLIGHT -->\n" + "p" * 30000 + "\n<!-- END MAGPIE PREFLIGHT -->\n"
    (repo / "skills" / "demo" / "SKILL.md").write_text(skill(100) + block)
    assert findings(repo) == []
    assert measure_skill(skill(100) + block)[0] < 100


def test_agents_md_grown_past_40k_characters_is_reported(repo: Path) -> None:
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 40001)
    [file] = codes(repo)
    assert file["kind"] == "instructions"
    assert file["optimizer"] == "optimize-agents-md"


def test_a_new_oversized_skill_is_reported(repo: Path) -> None:
    (repo / "skills" / "new").mkdir()
    (repo / "skills" / "new" / "SKILL.md").write_text(skill(6000 * 4))
    [file] = codes(repo)
    assert file["path"] == "skills/new/SKILL.md"
    assert file["base"] == {}


def test_shrinking_an_already_oversized_file_is_left_alone(repo: Path) -> None:
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 50000)
    git(repo, "switch", "-q", "main")
    git(repo, "commit", "-q", "-am", "big on main")
    git(repo, "switch", "-q", "feature")
    git(repo, "rebase", "-q", "main")
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 45000)
    assert findings(repo) == []


def test_growing_an_already_oversized_file_further_is_reported(repo: Path) -> None:
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 50000)
    git(repo, "switch", "-q", "main")
    git(repo, "commit", "-q", "-am", "big on main")
    git(repo, "switch", "-q", "feature")
    git(repo, "rebase", "-q", "main")
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 50100)
    assert [f["path"] for f in codes(repo)] == ["AGENTS.md"]


def test_an_acknowledged_digest_suppresses_until_the_file_changes_again(repo: Path) -> None:
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 40001)
    [file] = codes(repo)
    write_stamp(repo, {"acknowledged": {"oversize": {"AGENTS.md": file["digest"]}}})
    assert findings(repo) == []
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 40002)
    assert [f["path"] for f in codes(repo)] == ["AGENTS.md"]


def test_the_framework_snapshot_and_symlinks_are_skipped(repo: Path) -> None:
    snap = repo / ".apache-magpie" / "skills" / "x"
    snap.mkdir(parents=True)
    (snap / "SKILL.md").write_text(skill(6000 * 4))
    (repo / "CLAUDE.md").symlink_to("AGENTS.md")
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 900)
    assert findings(repo) == []


def test_a_tree_that_is_not_a_git_checkout_reports_nothing(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("y" * 50000)
    assert findings(tmp_path) == []


def test_a_repository_without_a_base_branch_reports_nothing(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "trunk")
    (tmp_path / "AGENTS.md").write_text("y" * 50000)
    assert findings(tmp_path) == []


def test_the_cli_emits_the_rules_and_can_skip_the_check(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 40001)
    monkeypatch.chdir(repo)
    argv = ["--skill", "demo", "--plugin-list", "-", "--verify-interval-days", "0", "--no-welcome"]
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("[]"))
    assert cli.main(argv) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [f["code"] for f in payload["findings"]] == ["oversize"]
    assert payload["rules"]["oversize"].startswith("## oversize")

    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("[]"))
    assert cli.main([*argv, "--no-oversize"]) == 0
    assert "oversize" not in capsys.readouterr().out


def test_the_section_ships() -> None:
    assert "oversize" in sections.available()


def test_the_ci_command_fails_on_growth_and_reports_markdown(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "skills" / "demo" / "SKILL.md").write_text(skill(5001 * 4))
    git(repo, "commit", "-q", "-am", "grow")
    assert main(["--project-root", str(repo), "--base", "HEAD^", "--format", "markdown"]) == 1
    out = capsys.readouterr().out
    assert "| `skills/demo/SKILL.md` | body |" in out
    assert "`optimize-skill`" in out


def test_the_ci_command_ignores_acknowledgements(repo: Path) -> None:
    assert main(["--project-root", str(repo), "--base", "main"]) == 0
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 40001)
    [file] = codes(repo)
    write_stamp(repo, {"acknowledged": {"oversize": {"AGENTS.md": file["digest"]}}})
    assert findings(repo) == []
    assert main(["--project-root", str(repo), "--base", "main"]) == 1


def test_an_unknown_base_reports_nothing(repo: Path) -> None:
    (repo / "AGENTS.md").write_text("# rules\n" + "y" * 40001)
    assert main(["--project-root", str(repo), "--base", "no-such-ref"]) == 0
