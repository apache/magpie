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

"""Tests for the append-only eval run journal and the tables rendered from it."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest

from skill_evals import journal
from skill_evals.journal import (
    EVALS_REL,
    JOURNAL_NAME,
    append_record,
    check_append_only,
    journal_path_for,
    legacy_records_from_rows,
    model_from_cli,
    parse_readme_table,
    read_records,
    redact_cli,
    render_readme,
    render_table,
    skill_dir_for,
)
from skill_evals.runner import main as runner_main

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _record(**overrides: object) -> dict:
    base: dict = {
        "schema": 1,
        "skill": "issue-triage",
        "date": "2026-10-16",
        "timestamp": "2026-10-16T10:00:00Z",
        "ref": "399ab1bc",
        "branch": "main",
        "dirty": False,
        "model": "claude-opus-5-5",
        "cli": "claude -p --model claude-opus-5-5",
        "grader_cli": "claude -p --model haiku",
        "path": "tools/skill-evals/evals/issue-triage",
        "tags": [],
        "cases": 3,
        "passed": 3,
        "failed": 0,
        "manual": 0,
        "errored": 0,
        "failed_cases": [],
        "errored_cases": [],
        "cost": {"wall_seconds": 12.5, "cli_calls": 3, "grader_calls": 1},
        "notes": "",
    }
    base.update(overrides)
    return base


def _make_evals_tree(tmp_path: Path, skill: str = "issue-triage") -> tuple[Path, Path]:
    """A fake repo root with the real evals layout under it."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    skill_dir = root / EVALS_REL / skill
    skill_dir.mkdir(parents=True)
    return root, skill_dir


README_WITH_TABLE = """\
# issue-triage evals

Some prose.

## Adversarial case

Notes about a case.

## Run history

Live model runs over this whole eval directory, newest first.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-10-16 | `399ab1bc` | `claude-opus-5-5` | 10 | `step-3-classify/case-4-duplicate` failed 3 of 10 | see [#1688](https://github.com/apache/magpie/issues/1688) |
| 2026-10-13 | `dadb315c` | `claude-fable-5-1` | 4 | pass |  |
"""


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------


def test_skill_dir_for_resolves_any_depth(tmp_path: Path) -> None:
    root, skill_dir = _make_evals_tree(tmp_path)
    evals_root = root / EVALS_REL
    case = skill_dir / "step-1" / "fixtures" / "case-1"
    case.mkdir(parents=True)
    assert skill_dir_for(case, evals_root) == skill_dir
    assert skill_dir_for(skill_dir, evals_root) == skill_dir
    assert journal_path_for(case, evals_root) == skill_dir / JOURNAL_NAME


def test_skill_dir_for_rejects_paths_outside_and_the_root_itself(tmp_path: Path) -> None:
    root, _skill_dir = _make_evals_tree(tmp_path)
    evals_root = root / EVALS_REL
    assert skill_dir_for(evals_root, evals_root) is None
    assert skill_dir_for(tmp_path, evals_root) is None


# ---------------------------------------------------------------------------
# append / read
# ---------------------------------------------------------------------------


def test_append_record_writes_one_line_per_record_and_read_round_trips(tmp_path: Path) -> None:
    path = tmp_path / JOURNAL_NAME
    append_record(path, _record())
    append_record(path, _record(date="2026-10-17", notes="rerun"))
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line) for line in lines)
    records = read_records(path)
    assert [r["date"] for r in records] == ["2026-10-16", "2026-10-17"]


def test_append_record_refuses_wrong_schema(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="schema"):
        append_record(tmp_path / JOURNAL_NAME, _record(schema=2))


def test_read_records_names_the_bad_line(tmp_path: Path) -> None:
    path = tmp_path / JOURNAL_NAME
    path.write_text(json.dumps(_record()) + "\nnot json\n")
    with pytest.raises(ValueError, match=r":2: not valid JSON"):
        read_records(path)


def test_read_records_rejects_missing_required_key(tmp_path: Path) -> None:
    path = tmp_path / JOURNAL_NAME
    rec = _record()
    del rec["model"]
    path.write_text(json.dumps(rec) + "\n")
    with pytest.raises(ValueError, match="'model'"):
        read_records(path)


def test_read_records_missing_file_is_empty(tmp_path: Path) -> None:
    assert read_records(tmp_path / "nope.jsonl") == []


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def test_render_table_groups_runs_and_counts_failures_per_case() -> None:
    records = [
        _record(timestamp="2026-10-16T10:00:00Z"),
        _record(timestamp="2026-10-16T10:05:00Z", failed=1, passed=2, failed_cases=["step-3/case-4"]),
        _record(timestamp="2026-10-16T10:10:00Z", failed=1, passed=2, failed_cases=["step-3/case-4"]),
        _record(timestamp="2026-10-16T10:15:00Z", errored=1, passed=2, errored_cases=["step-3/case-1"]),
    ]
    table = render_table(records)
    rows = [line for line in table.splitlines() if line.startswith("| 2026")]
    assert len(rows) == 1
    assert "| 4 |" in rows[0]
    assert "`step-3/case-4` failed 2 of 4" in rows[0]
    assert "`step-3/case-1` errored 1 of 4" in rows[0]


def test_render_table_all_pass_reads_pass_and_joins_notes() -> None:
    records = [_record(notes="warm-up"), _record(timestamp="2026-10-16T11:00:00Z", notes="warm-up")]
    table = render_table(records)
    row = next(line for line in table.splitlines() if line.startswith("| 2026"))
    assert "| pass |" in row
    assert row.count("warm-up") == 1


def test_render_table_newest_first_and_separates_models_and_refs() -> None:
    records = [
        _record(date="2026-10-13", ref="dadb315c", timestamp="2026-10-13T09:00:00Z"),
        _record(date="2026-10-16", model="claude-sonnet-5-5", timestamp="2026-10-16T09:00:00Z"),
        _record(date="2026-10-16", timestamp="2026-10-16T09:30:00Z"),
    ]
    rows = [line for line in render_table(records).splitlines() if line.startswith("| 2026")]
    assert len(rows) == 3
    assert rows[0].startswith("| 2026-10-16 | `399ab1bc` | `claude-opus-5-5`")
    assert rows[1].startswith("| 2026-10-16 | `399ab1bc` | `claude-sonnet-5-5`")
    assert rows[2].startswith("| 2026-10-13 | `dadb315c`")


def test_render_table_marks_branch_runs_and_unrecorded_model() -> None:
    records = [_record(branch="fix-grader", model=None)]
    row = next(line for line in render_table(records).splitlines() if line.startswith("| 2026"))
    assert "`399ab1bc` (fix-grader)" in row
    assert "(unrecorded, `claude -p --model claude-opus-5-5`)" in row


def test_render_table_keeps_unrecorded_models_of_different_clis_apart() -> None:
    records = [
        _record(model=None, cli="claude -p", failed=1, passed=2, failed_cases=["s/a"]),
        _record(model=None, cli="opencode run"),
    ]
    rows = [line for line in render_table(records).splitlines() if line.startswith("| 2026")]
    assert len(rows) == 2
    assert any("(unrecorded, `claude -p`)" in r and "failed 1 of 1" in r for r in rows)
    assert any("(unrecorded, `opencode run`)" in r and "| pass |" in r for r in rows)


def test_render_table_counts_each_case_against_the_runs_that_graded_it() -> None:
    # A full run where A fails, then a rerun of B alone: A ran once, not twice.
    full = _record(graded_cases=["s/a", "s/b"], failed=1, passed=1, failed_cases=["s/a"])
    rerun = _record(graded_cases=["s/b"], cases=1, passed=1, timestamp="2026-10-16T11:00:00Z")
    row = next(line for line in render_table([full, rerun]).splitlines() if line.startswith("| 2026"))
    assert "`s/a` failed 1 of 1" in row
    # A record from before graded_cases existed still counts every case.
    old = _record(failed=1, passed=2, failed_cases=["s/a"])
    row = next(line for line in render_table([old, rerun]).splitlines() if line.startswith("| 2026"))
    assert "`s/a` failed 1 of 1" in row


def test_render_table_shows_a_manual_only_batch_as_manual() -> None:
    manual_only = _record(graded_cases=[], cases=2, passed=0, manual=2)
    row = next(line for line in render_table([manual_only]).splitlines() if line.startswith("| 2026"))
    assert "| manual |" in row
    assert "| pass |" not in row


def test_render_table_escapes_pipes_in_notes() -> None:
    records = [_record(notes="a | b")]
    row = next(line for line in render_table(records).splitlines() if line.startswith("| 2026"))
    assert "a \\| b" in row


def test_render_readme_replaces_only_the_run_history_table() -> None:
    new_table = render_table([_record()])
    out = render_readme(README_WITH_TABLE, new_table)
    assert "## Adversarial case\n\nNotes about a case." in out
    assert "Live model runs over this whole eval directory, newest first." in out
    assert "dadb315c" not in out
    assert "| 2026-10-16 | `399ab1bc` | `claude-opus-5-5` | 1 | pass |  |" in out
    assert out.endswith("\n")


def test_render_readme_appends_a_section_when_missing() -> None:
    out = render_readme("# evals\n\nbody\n", render_table([_record()]))
    assert "## Run history" in out
    assert "runs.jsonl" in out
    assert out.index("body") < out.index("## Run history")


def test_render_readme_adds_a_table_to_an_empty_section() -> None:
    text = "# evals\n\n## Run history\n\nNo runs yet.\n\n## Later\n\nmore\n"
    out = render_readme(text, render_table([_record()]))
    assert out.index("No runs yet.") < out.index("| Date |") < out.index("## Later")


def test_render_is_idempotent() -> None:
    table = render_table([_record()])
    once = render_readme(README_WITH_TABLE, table)
    assert render_readme(once, table) == once


# ---------------------------------------------------------------------------
# legacy import reproduces the hand-written table byte for byte
# ---------------------------------------------------------------------------


def test_import_of_hand_written_table_round_trips() -> None:
    rows = parse_readme_table(README_WITH_TABLE)
    assert [r["Date"] for r in rows] == ["2026-10-16", "2026-10-13"]
    records = legacy_records_from_rows(rows, "issue-triage")
    assert [r["date"] for r in records] == ["2026-10-13", "2026-10-16"]  # chronological
    assert all(r["legacy"] for r in records)
    assert records[1]["runs"] == 10
    assert render_readme(README_WITH_TABLE, render_table(records)) == README_WITH_TABLE


def test_live_records_append_after_legacy_rows() -> None:
    legacy = legacy_records_from_rows(parse_readme_table(README_WITH_TABLE), "issue-triage")
    live = _record(date="2026-10-31", ref="28f31f6a", timestamp="2026-10-31T12:00:00Z")
    rows = [line for line in render_table([*legacy, live]).splitlines() if line.startswith("| 2026")]
    assert rows[0].startswith("| 2026-10-31 | `28f31f6a`")
    assert rows[0].endswith("| 1 | pass |  |")
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# append-only check
# ---------------------------------------------------------------------------


def test_check_append_only_accepts_growth_and_names_edits() -> None:
    a = json.dumps(_record()) + "\n"
    b = a + json.dumps(_record(date="2026-10-17")) + "\n"
    assert check_append_only(a, b) is None
    assert check_append_only("", b) is None
    assert check_append_only(b, a) == "line 2 was removed"
    assert check_append_only(a, b.replace("2026-10-16", "2026-10-15", 1)) == "line 1 was changed"


def test_model_from_cli() -> None:
    assert model_from_cli("claude -p --model claude-opus-5-5") == "claude-opus-5-5"
    assert model_from_cli("claude -p --model=haiku") == "haiku"
    assert model_from_cli("claude -p") is None


# ---------------------------------------------------------------------------
# CLI: render / check / import-readme
# ---------------------------------------------------------------------------


def test_cli_render_check_and_import(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, skill_dir = _make_evals_tree(tmp_path)
    evals_root = root / EVALS_REL
    (skill_dir / "README.md").write_text(README_WITH_TABLE)

    # Nothing to do before a journal exists.
    assert journal.main(["--evals-root", str(evals_root), "check", str(evals_root)]) == 0

    assert journal.main(["--evals-root", str(evals_root), "import-readme", str(skill_dir)]) == 0
    assert (skill_dir / JOURNAL_NAME).exists()
    # Second import refuses to double up.
    assert journal.main(["--evals-root", str(evals_root), "import-readme", str(skill_dir)]) == 1

    # Imported table renders back to itself: check passes, render is a no-op.
    assert journal.main(["--evals-root", str(evals_root), "check", str(evals_root)]) == 0
    assert journal.main(["--evals-root", str(evals_root), "render", str(evals_root), "--check"]) == 0

    # A new record makes the table stale until rendered.
    append_record(skill_dir / JOURNAL_NAME, _record(date="2026-10-31", timestamp="2026-10-31T00:00:00Z"))
    assert journal.main(["--evals-root", str(evals_root), "render", str(evals_root), "--check"]) == 1
    out = capsys.readouterr().out
    assert "out of date" in out
    assert journal.main(["--evals-root", str(evals_root), "render", str(skill_dir)]) == 0
    assert "| 2026-10-31 |" in (skill_dir / "README.md").read_text()
    assert journal.main(["--evals-root", str(evals_root), "check", str(evals_root)]) == 0


def _git(cwd: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _git_evals_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    skill_dir = root / EVALS_REL / "issue-triage"
    skill_dir.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    return root, skill_dir


def test_cli_check_against_flags_a_deleted_journal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, skill_dir = _git_evals_tree(tmp_path)
    append_record(skill_dir / JOURNAL_NAME, _record())
    journal.main(["--evals-root", str(root / EVALS_REL), "render", str(skill_dir)])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "journal")
    (skill_dir / JOURNAL_NAME).unlink()
    rc = journal.main(
        ["--evals-root", str(root / EVALS_REL), "check", str(root / EVALS_REL), "--against", "HEAD"]
    )
    assert rc == 1
    assert "removed" in capsys.readouterr().err


def test_union_merge_keeps_both_branches_records(tmp_path: Path) -> None:
    # The repository's own .gitattributes line, applied to two branches that
    # each append a run after the same last line.
    repo_attrs = Path(__file__).resolve().parents[3] / ".gitattributes"
    line = next(x for x in repo_attrs.read_text().splitlines() if "runs.jsonl" in x and "merge=union" in x)
    root, skill_dir = _git_evals_tree(tmp_path)
    (root / ".gitattributes").write_text(line + "\n")
    append_record(skill_dir / JOURNAL_NAME, _record(timestamp="2026-10-16T09:00:00Z"))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "checkout", "-q", "-b", "a")
    append_record(skill_dir / JOURNAL_NAME, _record(timestamp="2026-10-16T10:00:00Z"))
    _git(root, "commit", "-q", "-am", "a")
    _git(root, "checkout", "-q", "main")
    _git(root, "checkout", "-q", "-b", "b")
    append_record(skill_dir / JOURNAL_NAME, _record(timestamp="2026-10-16T11:00:00Z"))
    _git(root, "commit", "-q", "-am", "b")
    _git(root, "checkout", "-q", "main")
    _git(root, "merge", "-q", "a")
    _git(root, "merge", "-q", "--no-edit", "b")
    stamps = [r["timestamp"] for r in read_records(skill_dir / JOURNAL_NAME)]
    assert sorted(stamps) == ["2026-10-16T09:00:00Z", "2026-10-16T10:00:00Z", "2026-10-16T11:00:00Z"]


def test_runner_snapshots_the_checkout_before_the_first_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _root, skill_dir = _make_evals_tree(tmp_path, "demo-skill")
    _make_case(skill_dir, "case-1", {"verdict": "ok"})
    ran = tmp_path / "ran"
    cli = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
        f'import pathlib, sys; sys.stdin.read(); pathlib.Path({str(ran)!r}).touch(); print(\'{{"verdict": "ok"}}\')'
    )
    seen: list[bool] = []

    def fake_snapshot(cwd: Path) -> dict:
        seen.append(ran.exists())
        return {"ref": "abc1234", "branch": "main", "dirty": False}

    monkeypatch.setattr(journal, "git_snapshot", fake_snapshot)
    assert runner_main(["--cli", cli, "--exact", str(skill_dir)]) == 0
    assert seen == [False], "the snapshot must be taken once, before any case ran"
    (rec,) = read_records(skill_dir / JOURNAL_NAME)
    assert rec["ref"] == "abc1234"
    capsys.readouterr()


def test_cli_check_reports_a_corrupt_journal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, skill_dir = _make_evals_tree(tmp_path)
    evals_root = root / EVALS_REL
    (skill_dir / JOURNAL_NAME).write_text("{broken\n")
    assert journal.main(["--evals-root", str(evals_root), "check", str(evals_root)]) == 1
    assert ":1: not valid JSON" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# runner integration: a --cli run under the evals tree leaves a record
# ---------------------------------------------------------------------------

_ECHO_CLI = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
    'import sys; sys.stdin.read(); print(\'{"verdict": "ok"}\')'
)


def _make_case(skill_dir: Path, name: str, expected: dict) -> Path:
    fixtures = skill_dir / "step-1" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "system-prompt.md").write_text("system")
    case = fixtures / name
    case.mkdir()
    (case / "report.md").write_text("report")
    (case / "expected.json").write_text(json.dumps(expected))
    return case


def test_runner_journals_a_cli_run_under_the_evals_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, skill_dir = _make_evals_tree(tmp_path, "demo-skill")
    _make_case(skill_dir, "case-1-pass", {"verdict": "ok"})
    _make_case(skill_dir, "case-2-fail", {"verdict": "other"})

    rc = runner_main(["--cli", _ECHO_CLI, "--exact", "--journal-note", "smoke", str(skill_dir)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Journaled run to" in out

    records = read_records(skill_dir / JOURNAL_NAME)
    assert len(records) == 1
    rec = records[0]
    assert rec["skill"] == "demo-skill"
    assert rec["cases"] == 2 and rec["passed"] == 1 and rec["failed"] == 1
    assert rec["failed_cases"] == ["step-1/case-2-fail"]
    assert rec["errored_cases"] == []
    assert rec["notes"] == "smoke"
    assert rec["grader_cli"] is None  # --exact
    assert rec["cost"]["cli_calls"] == 2
    assert rec["cost"]["grader_calls"] == 0
    assert rec["model"] is None  # no --model in the CLI string, none given
    assert rec["path"] == f"{EVALS_REL}/demo-skill"
    # No git in the fake repo: the snapshot degrades, never fails the run.
    assert rec["ref"] == "unknown"

    # The table is generated from the record, not written by the runner.
    assert not (skill_dir / "README.md").exists()
    assert journal.main(["--evals-root", str(root / EVALS_REL), "render", str(skill_dir)]) == 0
    readme = (skill_dir / "README.md").read_text()
    assert "`step-1/case-2-fail` failed 1 of 1" in readme


def test_runner_does_not_journal_outside_the_evals_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    skill_dir = root / "elsewhere" / "demo-skill"
    _make_case(skill_dir, "case-1", {"verdict": "ok"})
    rc = runner_main(["--cli", _ECHO_CLI, "--exact", str(skill_dir)])
    assert rc == 0
    assert "Journaled run" not in capsys.readouterr().out
    assert not list(root.rglob(JOURNAL_NAME))


def test_runner_honours_no_journal_and_explicit_journal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _root, skill_dir = _make_evals_tree(tmp_path, "demo-skill")
    _make_case(skill_dir, "case-1", {"verdict": "ok"})

    assert runner_main(["--cli", _ECHO_CLI, "--exact", "--no-journal", str(skill_dir)]) == 0
    assert not (skill_dir / JOURNAL_NAME).exists()

    explicit = tmp_path / "out" / "runs.jsonl"
    assert (
        runner_main(
            [
                "--cli",
                _ECHO_CLI,
                "--exact",
                "--journal",
                str(explicit),
                "--journal-model",
                "stub-model",
                str(skill_dir),
            ]
        )
        == 0
    )
    (rec,) = read_records(explicit)
    assert rec["model"] == "stub-model"
    assert rec["skill"] == "out"
    assert not (skill_dir / JOURNAL_NAME).exists()
    capsys.readouterr()


def test_append_record_refuses_a_symlinked_journal(tmp_path: Path) -> None:
    root, skill_dir = _make_evals_tree(tmp_path, "demo-skill")
    victim = tmp_path / "victim.txt"
    victim.write_text("untouched\n")
    (skill_dir / JOURNAL_NAME).symlink_to(victim)
    with pytest.raises(OSError, match="symlink"):
        append_record(skill_dir / JOURNAL_NAME, _record(), within=root / EVALS_REL)
    assert victim.read_text() == "untouched\n"


def test_append_record_refuses_a_journal_that_resolves_outside_the_evals_tree(tmp_path: Path) -> None:
    root, _skill_dir = _make_evals_tree(tmp_path, "demo-skill")
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = root / EVALS_REL / "linked-skill"
    linked.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError, match="outside"):
        append_record(linked / JOURNAL_NAME, _record(), within=root / EVALS_REL)
    assert not (outside / JOURNAL_NAME).exists()


def test_runner_skips_the_journal_outside_any_git_checkout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A suite copied out of the repository (a git archive export, say) runs
    # to completion instead of dying in the journal step.
    from skill_evals.runner import find_repo_root

    try:
        find_repo_root(tmp_path)
    except RuntimeError:
        pass
    else:
        pytest.skip("the temp dir sits inside a git checkout")
    skill_dir = tmp_path / "export" / "demo-skill"
    _make_case(skill_dir, "case-1", {"verdict": "ok"})
    assert runner_main(["--cli", _ECHO_CLI, "--exact", str(skill_dir)]) == 0
    assert "Journaled run" not in capsys.readouterr().out
    assert not list(tmp_path.rglob(JOURNAL_NAME))


def test_runner_journal_flags_require_cli(tmp_path: Path) -> None:
    _root, skill_dir = _make_evals_tree(tmp_path, "demo-skill")
    _make_case(skill_dir, "case-1", {"verdict": "ok"})
    with pytest.raises(SystemExit):
        runner_main(["--journal-note", "x", str(skill_dir)])


@pytest.mark.parametrize(
    ("cli", "expected"),
    [
        ("claude -p --model claude-opus-5-5", "claude -p --model claude-opus-5-5"),
        ("ANTHROPIC_API_KEY=sk-ant-123 claude -p", "ANTHROPIC_API_KEY=<redacted> claude -p"),
        ("A=1 B='two words' codex exec", "A=<redacted> B=<redacted> codex exec"),
        ("tool --api-key sk-123 --model m", "tool --api-key <redacted> --model m"),
        ("tool --token=abc -p", "tool --token=<redacted> -p"),
        ("tool -H 'Authorization: Bearer x' run", "tool -H <redacted> run"),
        ("tool --model=gpt-5 -p", "tool --model=gpt-5 -p"),
        (None, None),
    ],
)
def test_redact_cli(cli: str | None, expected: str | None) -> None:
    assert redact_cli(cli) == expected
