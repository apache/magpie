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
"""CLI tests. Shells out to `gh` are stubbed via a fake subprocess.run."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from github_body_field import cli

CANONICAL_BODY = (
    "### CVE tool link\n"
    "\n"
    "https://cveprocess.apache.org/cve5/CVE-2026-12345\n"
    "\n"
    "### Reporter credited as\n"
    "\n"
    "anonymous\n"
)


@dataclass
class FakeResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class FakeGh:
    """Records the (cmd, input) of each subprocess.run and replies with
    canned output. Tests assert on the recorded calls."""

    def __init__(self, body: str = CANONICAL_BODY) -> None:
        self.body = body
        self.calls: list[tuple[list[str], str | None]] = []
        self.next_write_returncode = 0

    def __call__(
        self,
        cmd: list[str],
        *,
        capture_output: bool = False,
        text: bool = False,
        input: str | None = None,
        check: bool = False,
    ) -> FakeResult:
        self.calls.append((cmd, input))
        # Distinguish read vs write by argv shape.
        if "view" in cmd:
            # The body comes back as JSON (`--json body`), CRs escaped.
            return FakeResult(returncode=0, stdout=json.dumps({"body": self.body}) + "\n")
        if "edit" in cmd:
            # Capture the new body so the test can assert on it.
            assert input is not None, "edit must pipe a body via stdin"
            self.body = input  # mimic the round-trip
            return FakeResult(returncode=self.next_write_returncode)
        raise AssertionError(f"unexpected gh invocation: {cmd!r}")


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGh]:
    f = FakeGh()
    monkeypatch.setattr(subprocess, "run", f)
    yield f


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_prints_field_value(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["get", "123", "--field", "Reporter credited as"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out == "anonymous\n"


def test_get_field_missing_exits_3(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["get", "123", "--field", "Nope"])
    assert rc == 3
    err = capsys.readouterr().err
    assert "not found" in err


def test_get_forwards_repo_to_gh(fake_gh: FakeGh) -> None:
    cli.main(["--repo", "foo/bar", "get", "123", "--field", "Reporter credited as"])
    read_cmd, _ = fake_gh.calls[0]
    assert "--repo" in read_cmd
    assert read_cmd[read_cmd.index("--repo") + 1] == "foo/bar"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_prints_headings_one_per_line(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["list", "123"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out == "CVE tool link\nReporter credited as\n"


def test_list_json_emits_array(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["list", "123", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"CVE tool link"' in out
    assert '"Reporter credited as"' in out


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------


def test_set_pushes_new_body(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        [
            "set",
            "123",
            "--field",
            "Reporter credited as",
            "--value",
            "Jane Doe (@jdoe)",
        ]
    )
    assert rc == 0
    # First call: view. Second call: edit with the rewritten body via stdin.
    assert len(fake_gh.calls) == 2
    edit_cmd, edit_input = fake_gh.calls[1]
    assert edit_cmd[:4] == ["gh", "issue", "edit", "123"]
    assert "--body-file" in edit_cmd
    assert "-" in edit_cmd
    assert edit_input is not None
    assert "### Reporter credited as\n\nJane Doe (@jdoe)\n" in edit_input
    # Diff summary on stderr.
    err = capsys.readouterr().err
    assert "field='Reporter credited as'" in err


def test_set_no_op_when_value_unchanged(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        [
            "set",
            "123",
            "--field",
            "Reporter credited as",
            "--value",
            "anonymous",
        ]
    )
    assert rc == 0
    # Only the view should have happened; the write must be skipped.
    assert len(fake_gh.calls) == 1
    err = capsys.readouterr().err
    assert "unchanged" in err


def test_set_dry_run_does_not_push(fake_gh: FakeGh) -> None:
    rc = cli.main(
        [
            "set",
            "123",
            "--field",
            "Reporter credited as",
            "--value",
            "Jane",
            "--dry-run",
        ]
    )
    assert rc == 0
    # Only the read; no edit call.
    assert len(fake_gh.calls) == 1


def test_set_field_missing_exits_3_without_writing(
    fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(["set", "123", "--field", "Nope", "--value", "x"])
    assert rc == 3
    # Read happened, edit did not.
    assert len(fake_gh.calls) == 1
    err = capsys.readouterr().err
    assert "not found" in err


def test_set_rejects_both_value_and_value_file(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "set",
                "123",
                "--field",
                "Reporter credited as",
                "--value",
                "x",
                "--value-file",
                "/tmp/whatever",
            ]
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "not both" in err
    # No gh call should have happened.
    assert len(fake_gh.calls) == 0


def test_set_requires_one_of_value_or_value_file(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["set", "123", "--field", "Reporter credited as"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "required" in err


def test_set_value_file_is_read(fake_gh: FakeGh, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    value_file = tmp_path / "v.txt"
    value_file.write_text("from-a-file\n", encoding="utf-8")
    rc = cli.main(
        [
            "set",
            "123",
            "--field",
            "Reporter credited as",
            "--value-file",
            str(value_file),
        ]
    )
    assert rc == 0
    edit_input = fake_gh.calls[1][1]
    assert edit_input is not None
    assert "### Reporter credited as\n\nfrom-a-file\n" in edit_input


def test_set_propagates_gh_write_failure(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    fake_gh.next_write_returncode = 1
    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "set",
                "123",
                "--field",
                "Reporter credited as",
                "--value",
                "Jane",
            ]
        )
    assert exc.value.code == 1
