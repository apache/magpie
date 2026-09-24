#
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
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from adversarial_review import main
from adversarial_review.cli import build_parser


def test_help_lists_subcommands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "detect" in out and "run" in out


def test_no_subcommand_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


FINDING = {
    "severity": "high",
    "file": "app.py",
    "line": 2,
    "claim": "f() returns the wrong value",
    "evidence": "return 2",
}


def _stubs(make, ran: Path):
    touch = f"open({str(ran)!r} + '/' + __import__('os').path.basename(__import__('sys').argv[0]), 'w')\n"
    make(
        "codex",
        touch + "import json, sys\na = sys.argv\n"
        f"open(a[a.index('-o') + 1], 'w').write(json.dumps({{'findings': [{FINDING!r}]}}))\n",
    )
    make(
        "copilot",
        touch + "import json\n"
        f"print('Review:\\n```json\\n' + json.dumps({{'findings': [{{**{FINDING!r}, 'line': 3, "
        "'claim': 'f returns a wrong value'}]}) + '\\n```')\n",
    )
    make("gemini", touch + "import sys; sys.stderr.write('Please log in first\\n'); sys.exit(1)\n")
    make("claude", touch + "raise SystemExit('claude must not run: it is self')\n")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "adopter"
    (root / ".apache-magpie-local").mkdir(parents=True)
    (root / ".apache-magpie-local" / "adversarial-review.md").write_text(
        "```yaml\nadversarial_review:\n  reviewers: [codex, copilot, gemini, claude]\n```\n", encoding="utf-8"
    )
    return root


def test_run_end_to_end(stub_bin, git_repo, tmp_path, capsys):
    bin_dir, make = stub_bin
    ran = tmp_path / "ran"
    ran.mkdir()
    _stubs(make, ran)
    body = tmp_path / "body.md"
    body.write_text("Return 2.", encoding="utf-8")
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "CLAUDECODE": "1"}
    code = main(
        [
            "run",
            "--project-root",
            str(_project(tmp_path)),
            "--repo-dir",
            str(git_repo),
            "--base",
            "main",
            "--title",
            "Fix f",
            "--body-file",
            str(body),
        ],
        env=env,
    )
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["self"] == "claude" and report["files"] == ["app.py"]
    assert [(r["name"], r["status"]) for r in report["reviewers"]] == [
        ("codex", "ok"),
        ("copilot", "ok"),
        ("gemini", "unavailable"),
        ("claude", "skipped"),
    ]
    [finding] = report["findings"]
    assert finding["reviewers"] == ["codex", "copilot"]
    assert sorted(p.name for p in ran.iterdir()) == ["codex", "copilot", "gemini"]
    assert "untrusted" in report["note"]


def test_empty_diff_runs_no_reviewer(stub_bin, git_repo, tmp_path, capsys):
    bin_dir, make = stub_bin
    ran = tmp_path / "ran"
    ran.mkdir()
    _stubs(make, ran)
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    code = main(
        ["run", "--project-root", str(_project(tmp_path)), "--repo-dir", str(git_repo), "--base", "change"],
        env=env,
    )
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert list(ran.iterdir()) == [] and report["reviewers"] == []
    assert any("empty diff" in w for w in report["warnings"])


def test_no_reviewers_configured_warns(git_repo, tmp_path, capsys):
    code = main(
        ["run", "--project-root", str(tmp_path), "--repo-dir", str(git_repo), "--base", "main"],
        env={"PATH": os.environ["PATH"]},
    )
    assert code == 0
    assert any("no reviewers configured" in w for w in json.loads(capsys.readouterr().out)["warnings"])


def test_reviewers_flag_overrides_config_and_rejects_unknown(git_repo, tmp_path, capsys):
    code = main(
        [
            "run",
            "--reviewers",
            "codex,vim",
            "--project-root",
            str(tmp_path),
            "--repo-dir",
            str(git_repo),
            "--base",
            "main",
        ],
        env={"PATH": os.environ["PATH"]},
    )
    assert code == 2 and "unknown reviewer" in capsys.readouterr().err


def test_bad_target_is_a_usage_error(git_repo, tmp_path, capsys):
    code = main(
        ["run", "--target", "tag:v1", "--project-root", str(tmp_path), "--repo-dir", str(git_repo)],
        env={"PATH": os.environ["PATH"]},
    )
    assert code == 2 and "--target" in capsys.readouterr().err


def test_run_accepts_no_free_form_context_option():
    """The privacy boundary, at the CLI: these are the only inputs `run` takes."""
    dests = set(vars(build_parser().parse_args(["run"]))) - {"command"}
    assert dests == {
        "reviewers",
        "project_root",
        "repo_dir",
        "target",
        "base",
        "repo",
        "title",
        "body_file",
        "timeout_minutes",
        "self_name",
    }


@pytest.mark.parametrize("minutes", ["0", "-1"])
def test_non_positive_timeout_is_a_usage_error(git_repo, tmp_path, capsys, minutes):
    code = main(
        [
            "run",
            "--timeout-minutes",
            minutes,
            "--project-root",
            str(tmp_path),
            "--repo-dir",
            str(git_repo),
            "--base",
            "main",
        ],
        env={"PATH": os.environ["PATH"]},
    )
    assert code == 2 and "--timeout-minutes" in capsys.readouterr().err


def test_truncated_diff_is_flagged_in_the_report(stub_bin, tmp_path, capsys):
    bin_dir, make = stub_bin
    make(
        "codex",
        "import json, sys\na = sys.argv\nopen(a[a.index('-o') + 1], 'w').write(json.dumps({'findings': []}))\n",
    )
    diff = tmp_path / "big.diff"
    diff.write_text("diff --git a/x b/x\n" + "+" * 500_000 + "\n", encoding="utf-8")
    code = main(
        [
            "run",
            "--reviewers",
            "codex",
            "--target",
            f"diff:{diff}",
            "--project-root",
            str(tmp_path),
            "--repo-dir",
            str(tmp_path),
        ],
        env={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and report["truncated"] is True
    assert any("truncated" in w for w in report["warnings"])
    assert report["reviewers"][0]["status"] == "ok"


def test_unrunnable_git_is_a_usage_error_not_a_traceback(stub_bin, git_repo, tmp_path, capsys):
    bin_dir, _ = stub_bin
    broken = bin_dir / "git"
    broken.write_text("not a program", encoding="utf-8")
    broken.chmod(0o755)  # executable but not a valid binary: exec fails with OSError
    code = main(
        ["run", "--project-root", str(tmp_path), "--repo-dir", str(git_repo), "--base", "main"],
        env={"PATH": str(bin_dir)},
    )
    assert code == 2 and "git" in capsys.readouterr().err
