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
"""CLI tests — exercises the live path (fake gh) and replay path."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from preflight_audit import cli

CANNED_RESPONSE = {
    "data": {
        "repository": {
            "i100": {
                "number": 100,
                "state": "OPEN",
                "closedAt": None,
                "updatedAt": "2026-05-30T08:00:00Z",
                "labels": {"nodes": [{"name": "cve allocated"}, {"name": "fix released"}]},
                "comments": {
                    "nodes": [
                        {
                            "author": {"login": "potiuk"},
                            "createdAt": "2026-05-30T08:00:00Z",
                            "body": "<!-- apache-steward: status-rollup v1 -->\nentry\n",
                        }
                    ]
                },
            },
            "i101": {
                "number": 101,
                "state": "OPEN",
                "closedAt": None,
                "updatedAt": "2026-05-31T11:00:00Z",
                "labels": {"nodes": [{"name": "needs triage"}]},
                "comments": {
                    "nodes": [
                        {
                            "author": {"login": "reporter"},
                            "createdAt": "2026-05-31T11:00:00Z",
                            "body": "this is a real problem\n",
                        }
                    ]
                },
            },
            "i102": {
                "number": 102,
                "state": "CLOSED",
                "closedAt": "2026-03-15T10:00:00Z",
                "updatedAt": "2026-03-15T10:00:00Z",
                "labels": {"nodes": [{"name": "announced"}]},
                "comments": {"nodes": []},
            },
        }
    }
}


@dataclass
class FakeResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class FakeGh:
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or CANNED_RESPONSE
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *, capture_output=False, text=False, check=False, **_):
        self.calls.append(cmd)
        return FakeResult(returncode=0, stdout=json.dumps(self.response))


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGh]:
    f = FakeGh()
    monkeypatch.setattr(subprocess, "run", f)
    yield f


# ---------------------------------------------------------------------------
# Live mode
# ---------------------------------------------------------------------------


def test_live_mode_invokes_gh_and_prints_table(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        [
            "classify",
            "--repo",
            "owner/repo",
            "--issues",
            "100,101,102",
            "--now",
            "2026-05-31T12:00:00Z",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Total trackers: 3" in out
    assert "skip-noop:" in out
    assert "Estimated savings" in out
    # One gh call to graphql.
    assert len(fake_gh.calls) == 1
    assert fake_gh.calls[0][:3] == ["gh", "api", "graphql"]


def test_live_mode_issues_with_hash_prefix(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        ["classify", "--repo", "o/r", "--issues", "#100, #101 ,#102", "--now", "2026-05-31T12:00:00Z"]
    )
    assert rc == 0


def test_live_mode_rejects_bad_repo(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["classify", "--repo", "noslash", "--issues", "1"])
    assert rc == 2
    assert "owner/name" in capsys.readouterr().err


def test_live_mode_requires_repo_when_no_load(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["classify"])
    assert rc == 2
    assert "required" in capsys.readouterr().err


def test_live_mode_rejects_empty_issues_list(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["classify", "--repo", "o/r", "--issues", ",,,"])
    assert exc.value.code == "error: --issues parsed to empty list" or exc.value.code != 0


# ---------------------------------------------------------------------------
# Replay mode
# ---------------------------------------------------------------------------


def test_replay_mode_loads_fixture(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = tmp_path / "resp.json"
    fixture.write_text(json.dumps(CANNED_RESPONSE), encoding="utf-8")
    rc = cli.main(
        [
            "classify",
            "--load",
            str(fixture),
            "--now",
            "2026-05-31T12:00:00Z",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Total trackers: 3" in out
    # #100 should be SKIP_NOOP (cve+fix released+skill-last).
    assert "#  100" in out or " 100" in out


def test_replay_mode_json_output(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = tmp_path / "resp.json"
    fixture.write_text(json.dumps(CANNED_RESPONSE), encoding="utf-8")
    rc = cli.main(
        [
            "classify",
            "--load",
            str(fixture),
            "--now",
            "2026-05-31T12:00:00Z",
            "--json",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert len(parsed) == 3
    # Sorted by number.
    assert [p["number"] for p in parsed] == [100, 101, 102]
    by_n = {p["number"]: p for p in parsed}
    assert by_n[100]["decision"] == "skip-noop"
    assert by_n[102]["decision"] == "skip-noop"
    # 101 has a non-skill comment 1 hour ago → dispatch-urgent OR dispatch
    # depending on the 1.0-day cutoff. 11:00 → 12:00 is exactly 1.0h ago.
    assert by_n[101]["decision"] in {"dispatch", "dispatch-urgent"}


def test_extra_bot_logins_flag(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    """The --bot-logins flag adds extra logins to the bot-equivalent set."""
    # Reshape #100 so its author is a personal-account bot.
    response = json.loads(json.dumps(CANNED_RESPONSE))
    response["data"]["repository"]["i100"]["comments"]["nodes"][0]["author"]["login"] = "company-bot"
    response["data"]["repository"]["i100"]["comments"]["nodes"][0]["body"] = "no marker\n"
    fixture = tmp_path / "resp.json"
    fixture.write_text(json.dumps(response), encoding="utf-8")

    # Without the flag: #100 dispatches (no skill marker, not a [bot] login).
    cli.main(["classify", "--load", str(fixture), "--now", "2026-05-31T12:00:00Z", "--json"])
    no_flag_out = capsys.readouterr().out
    no_flag = {p["number"]: p for p in json.loads(no_flag_out)}
    assert no_flag[100]["decision"] == "dispatch"

    # With the flag: #100 is recognised, classifier can fire Rule 7.
    cli.main(
        [
            "classify",
            "--load",
            str(fixture),
            "--now",
            "2026-05-31T12:00:00Z",
            "--json",
            "--bot-logins",
            "company-bot",
        ]
    )
    flag_out = capsys.readouterr().out
    with_flag = {p["number"]: p for p in json.loads(flag_out)}
    assert with_flag[100]["decision"] == "skip-noop"
