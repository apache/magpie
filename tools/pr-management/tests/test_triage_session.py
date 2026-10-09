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
"""The session cache and the Step 6 summary."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from pr_management import cli
from pr_management.triage import session as S

from .helpers import page, pr

T0 = dt.datetime(2026, 4, 22, 9, 42, tzinfo=dt.UTC)


def test_record_writes_the_schema_classify_reads(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    S.record(path, pr=12, head="abc", action="draft", classification="deterministic_flag", now=T0)
    data = json.loads(path.read_text())
    assert data["prs"]["12"] == {
        "head_sha": "abc",
        "classification": "deterministic_flag",
        "action_taken": "draft",
        "action_at": "2026-04-22T09:42:00Z",
        "terminal": True,
    }
    assert data["started_at"] == "2026-04-22T09:42:00Z"


def test_a_skip_is_not_terminal(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    assert S.record(path, pr=1, head="a", action="skip", reason="bot", now=T0)["terminal"] is False


def test_recorded_pr_is_suppressed_by_classify(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    (saved / "triage-pages.json").write_text(json.dumps(page(pr(5, mergeable="CONFLICTING"))))
    session = tmp_path / "s.json"
    assert (
        cli.main(
            [
                "triage",
                "session",
                "record",
                "--session",
                str(session),
                "--pr",
                "5",
                "--head",
                "abc1234def5678",
                "--action",
                "draft",
            ]
        )
        == 0
    )
    capsys.readouterr()
    cli.main(
        [
            "--config-dir",
            str(tmp_path),
            "triage",
            "classify",
            "--saved-dir",
            str(saved),
            "--viewer",
            "v",
            "--session",
            str(session),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert out["counts"]["suppressed"] == 1


def test_summary_matches_the_step_6_format(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    for n, action in enumerate(["draft", "draft", "close", "rerun", "mark-ready"]):
        S.record(path, pr=n, head="h", action=action, now=T0)
    classify = {
        "filtered": {"F1": 1, "F2": 2},
        "skipped": [{"number": 90, "row": "3"}, {"number": 91, "row": "grace"}],
        "groups": [{"prs": [{"number": 0}, {"number": 50}, {"number": 51}]}],
    }
    out = S.summary(path, classify=classify, now=T0 + dt.timedelta(minutes=25))
    lines = out["text"].splitlines()
    assert lines[0] == "Session summary — 2026-04-22 09:42 UTC → 10:07 UTC (25m)"
    assert "PRs acted on:    5" in lines
    assert "  - drafted:            2" in lines
    assert "  - reruns triggered:   1" in lines
    assert out["skipped"] == {"collaborator": 1, "bot": 2, "already triaged / inside grace": 2}
    assert out["pending"] == [50, 51]
    assert lines[-1] == "Throughput: 5 actions / 25m = 12 PRs/h"
    assert json.loads(path.read_text())["last_summary"]["acted_total"] == 5


def test_the_cache_write_is_atomic(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    S.record(path, pr=1, head="h", action="draft", now=T0)
    assert [p.name for p in tmp_path.iterdir()] == ["s.json"]


def test_cli_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    session = tmp_path / "s.json"
    cli.main(
        [
            "triage",
            "session",
            "record",
            "--session",
            str(session),
            "--pr",
            "1",
            "--head",
            "h",
            "--action",
            "ping",
            "--now",
            "2026-04-22T09:00:00Z",
        ]
    )
    capsys.readouterr()
    cli.main(["triage", "session", "summary", "--session", str(session), "--now", "2026-04-22T10:00:00Z"])
    out = json.loads(capsys.readouterr().out)
    assert out["acted"] == {"pings posted": 1}
    assert out["text"].startswith("Session summary — 2026-04-22 09:00 UTC → 10:00 UTC (60m)")
