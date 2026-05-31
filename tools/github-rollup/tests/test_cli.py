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
"""CLI tests — `gh` is faked via a subprocess.run patch."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from github_rollup import cli

MARKER_LINE = (
    "<!-- airflow-s status rollup v1 — all bot-authored status updates fold into this single comment. -->"
)

ROLLUP_BODY = (
    f"{MARKER_LINE}\n"
    "<details><summary>2026-05-28 · @potiuk · Import</summary>\n\n"
    "Imported from security@.\n\n"
    "</details>"
)


@dataclass
class FakeResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class FakeGh:
    """Records every `gh` call and returns canned output for each
    pattern. Tests assert on the recorded calls."""

    def __init__(self, has_rollup: bool = True) -> None:
        self.calls: list[tuple[list[str], str | None]] = []
        self.has_rollup = has_rollup
        # Track the last patched body so tests can verify what we
        # actually wrote.
        self.patched_body: str | None = None
        self.posted_body: str | None = None

    def __call__(
        self,
        cmd: list[str],
        *,
        capture_output: bool = False,
        text: bool = False,
        input: str | None = None,
        check: bool = False,
        **_: object,
    ) -> FakeResult:
        self.calls.append((cmd, input))
        joined = " ".join(cmd)

        if "issue view" in joined and "--json comments" in joined:
            comments = []
            if self.has_rollup:
                comments.append(
                    {
                        "id": "IC_NODEID",
                        "body": ROLLUP_BODY,
                        "url": "https://github.com/o/r/issues/1#issuecomment-1",
                    }
                )
            return FakeResult(returncode=0, stdout=json.dumps({"comments": comments}))

        if "api user" in joined:
            return FakeResult(returncode=0, stdout="potiuk\n")

        if "repo view" in joined:
            return FakeResult(returncode=0, stdout="o/r\n")

        if "issues/comments?per_page=100" in joined and "node_id" in joined:
            # REST-id resolution stub.
            return FakeResult(returncode=0, stdout="98765\n")

        if "-X" in cmd and "PATCH" in cmd and "issues/comments" in joined:
            # Extract the body from -f body=<value>.
            for i, tok in enumerate(cmd):
                if tok == "-f" and i + 1 < len(cmd) and cmd[i + 1].startswith("body="):
                    self.patched_body = cmd[i + 1][len("body=") :]
                    break
            return FakeResult(returncode=0)

        if "issue comment" in joined and "--body-file" in cmd and "-" in cmd:
            self.posted_body = input
            return FakeResult(returncode=0)

        raise AssertionError(f"unexpected gh invocation: {cmd!r}")


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGh]:
    f = FakeGh()
    monkeypatch.setattr(subprocess, "run", f)
    yield f


@pytest.fixture
def fake_gh_no_rollup(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGh]:
    f = FakeGh(has_rollup=False)
    monkeypatch.setattr(subprocess, "run", f)
    yield f


# ---------------------------------------------------------------------------
# append — append path
# ---------------------------------------------------------------------------


def test_append_to_existing_rollup_patches_with_new_entry(
    fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(
        [
            "--repo",
            "o/r",
            "append",
            "1",
            "--action",
            "CVE allocated",
            "--entry-body",
            "Allocated CVE-2026-12345.",
            "--now",
            "2026-05-30T12:00:00Z",
        ]
    )
    assert rc == 0
    assert fake_gh.patched_body is not None
    # The PATCH body contains BOTH the existing Import entry and the
    # new CVE allocated entry, separated by the canonical ruler.
    assert "Import" in fake_gh.patched_body
    assert "CVE allocated" in fake_gh.patched_body
    assert "</details>\n\n---\n\n<details>" in fake_gh.patched_body
    err = capsys.readouterr().err
    assert "appended to rollup on o/r#1" in err


def test_append_uses_gh_auth_user_when_user_flag_omitted(
    fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(
        [
            "--repo",
            "o/r",
            "append",
            "1",
            "--action",
            "Sync",
            "--entry-body",
            "X",
            "--now",
            "2026-05-30T12:00:00Z",
        ]
    )
    assert fake_gh.patched_body is not None
    # FakeGh returns `potiuk` from `gh api user`.
    assert "· @potiuk ·" in fake_gh.patched_body


def test_append_explicit_user_overrides_auth(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(
        [
            "--repo",
            "o/r",
            "append",
            "1",
            "--action",
            "Sync",
            "--entry-body",
            "X",
            "--user",
            "@other-user",
            "--now",
            "2026-05-30T12:00:00Z",
        ]
    )
    assert fake_gh.patched_body is not None
    assert "· @other-user ·" in fake_gh.patched_body


def test_append_dry_run_skips_writes(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        [
            "--repo",
            "o/r",
            "append",
            "1",
            "--action",
            "Sync",
            "--entry-body",
            "X",
            "--now",
            "2026-05-30T12:00:00Z",
            "--dry-run",
        ]
    )
    assert rc == 0
    assert fake_gh.patched_body is None
    assert fake_gh.posted_body is None
    err = capsys.readouterr().err
    assert "dry-run" in err
    assert "APPEND" in err


# ---------------------------------------------------------------------------
# append — create path
# ---------------------------------------------------------------------------


def test_append_creates_new_rollup_when_none_exists(
    fake_gh_no_rollup: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(
        [
            "--repo",
            "o/r",
            "append",
            "1",
            "--action",
            "Import",
            "--entry-body",
            "Imported from security@.",
            "--now",
            "2026-05-30T12:00:00Z",
        ]
    )
    assert rc == 0
    body = fake_gh_no_rollup.posted_body
    assert body is not None
    assert body.startswith("<!-- airflow-s status rollup v1 — all bot-authored status updates fold")
    assert "· @potiuk · Import" in body
    assert "Imported from security@" in body
    err = capsys.readouterr().err
    assert "created rollup on o/r#1" in err


def test_append_dry_run_signals_create_path(
    fake_gh_no_rollup: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(
        [
            "--repo",
            "o/r",
            "append",
            "1",
            "--action",
            "Import",
            "--entry-body",
            "X",
            "--now",
            "2026-05-30T12:00:00Z",
            "--dry-run",
        ]
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "CREATE" in err


# ---------------------------------------------------------------------------
# append — argument validation
# ---------------------------------------------------------------------------


def test_append_rejects_both_entry_body_flags(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "--repo",
                "o/r",
                "append",
                "1",
                "--action",
                "Sync",
                "--entry-body",
                "x",
                "--entry-body-file",
                "/tmp/x",
            ]
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "not both" in err


def test_append_requires_an_entry_body_source(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--repo", "o/r", "append", "1", "--action", "Sync"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "required" in err


# ---------------------------------------------------------------------------
# list and latest
# ---------------------------------------------------------------------------


def test_list_prints_one_summary_per_line(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--repo", "o/r", "list", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2026-05-28 · @potiuk · Import" in out


def test_list_json(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--repo", "o/r", "list", "1", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == [{"date": "2026-05-28", "user": "@potiuk", "action": "Import"}]


def test_list_exits_3_when_no_rollup(fake_gh_no_rollup: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--repo", "o/r", "list", "1"])
    assert rc == 3
    err = capsys.readouterr().err
    assert "no rollup" in err


def test_latest_prints_last_entry_body(fake_gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--repo", "o/r", "latest", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Imported from security@" in out


def test_latest_exits_3_when_no_rollup(fake_gh_no_rollup: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--repo", "o/r", "latest", "1"])
    assert rc == 3
