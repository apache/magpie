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

"""Regression tests for guarded security-tracker creation (issue #1979)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vetted_ops import cli, config, ops, tracker_backends


@pytest.fixture
def policy(tmp_path: Path) -> Path:
    workspace = tmp_path / "scratch"
    workspace.mkdir(mode=0o700)
    cfg = tmp_path / "policy.toml"
    cfg.write_text(
        f'workspace = "{workspace}"\n'
        "[repos]\n"
        'upstream = "apache/public"\n'
        'tracker = "apache/private-tracker"\n'
        "[values]\n"
        'labels = ["needs triage", "security issue", "scope:core"]\n'
        "[callers]\n"
        '"security-issue-import" = ["issue-create-labeled"]\n'
    )
    return cfg


def _title_file(policy: Path, text: str) -> str:
    path = policy.parent / "scratch" / "title.txt"
    path.write_text(text)
    return str(path)


def test_creation_is_pinned_to_private_tracker(policy: Path) -> None:
    command = ops.OPS["issue-create-labeled"].build(
        config.load(policy).as_mapping(),
        title="Possible vulnerability",
        body="-",
        labels='["needs triage","security issue"]',
    )
    assert isinstance(command, list)
    assert command[:3] == ["gh", "api", "repos/apache/private-tracker/issues"]
    assert "repos/apache/public/issues" not in command
    assert "body=@-" in command
    assert ".node_id" in " ".join(command)


def test_labels_are_applied_at_creation(policy: Path) -> None:
    command = ops.OPS["issue-create-labeled"].build(
        config.load(policy).as_mapping(),
        title="Possible vulnerability",
        body="-",
        labels='["needs triage","security issue"]',
    )
    assert isinstance(command, list)
    assert "labels[]=needs triage" in command
    assert "labels[]=security issue" in command


def test_missing_tracker_refused() -> None:
    with pytest.raises(ops.ParamError, match="tracker"):
        ops.OPS["issue-create-labeled"].build(
            {"upstream_repo": "apache/public"},
            title="Report",
            body="-",
            labels='["security issue"]',
        )


def test_non_github_backends_cannot_fall_through_to_gh() -> None:
    assert "issue-create-labeled" in tracker_backends.NOT_ON_BACKEND


def test_existing_issue_create_contract_unchanged() -> None:
    assert ops.OPS["issue-create"].params == ("title", "body")


def test_unapproved_label_refused(policy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    body = policy.parent / "scratch" / "body.md"
    body.write_text("CVE vulnerability report\n")

    code = cli.main(
        [
            "--config",
            str(policy),
            "--caller",
            "security-issue-import",
            "--dry-run",
            "issue-create-labeled",
            _title_file(policy, "Security report\n"),
            str(body),
            json.dumps(["public-disclosure"]),
        ]
    )
    assert code != cli.EXIT_OK
    assert "label" in capsys.readouterr().err.lower()


def test_sensitive_body_uses_stdin(policy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Confidential text must not enter argv or target the public upstream."""
    import subprocess

    body = policy.parent / "scratch" / "report.md"
    secret = "CVE-2026-12345: vulnerability reported to security@example.org"
    body.write_text(secret)

    loaded = config.load(policy)
    monkeypatch.setattr(cli, "load", lambda _path, *, approved_only: loaded)

    observed: dict[str, list[str] | bytes] = {}

    def fake_run(argv: list[str], *, check: bool, input: bytes) -> subprocess.CompletedProcess[bytes]:
        observed["argv"] = argv
        observed["body"] = input
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = cli.main(
        [
            "--caller",
            "security-issue-import",
            "issue-create-labeled",
            _title_file(policy, "Private security report\n"),
            str(body),
            '["needs triage","security issue"]',
        ]
    )

    assert result == cli.EXIT_OK
    assert observed["body"] == secret.encode()
    assert isinstance(observed["argv"], list)
    assert all(secret not in arg for arg in observed["argv"])
    assert "repos/apache/private-tracker/issues" in observed["argv"]
    assert "repos/apache/public/issues" not in observed["argv"]
    assert "labels[]=needs triage" in observed["argv"]
    assert "labels[]=security issue" in observed["argv"]
    assert "title=Private security report" in observed["argv"]


@pytest.mark.parametrize("title", ["", "   \n", "two\nlines"])
def test_a_title_file_gets_the_title_checks(
    policy: Path, title: str, capsys: pytest.CaptureFixture[str]
) -> None:
    body = policy.parent / "scratch" / "body.md"
    body.write_text("Report\n")
    code = cli.main(
        [
            "--config",
            str(policy),
            "--caller",
            "security-issue-import",
            "--dry-run",
            "issue-create-labeled",
            _title_file(policy, title),
            str(body),
            '["needs triage"]',
        ]
    )
    assert code != cli.EXIT_OK
    assert "title" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("secret", ["hunter2", "hunter2\nsecond line", "hunter2" * 50])
def test_a_title_file_is_never_echoed(policy: Path, secret: str, capsys: pytest.CaptureFixture[str]) -> None:
    """A dry run takes any --config, so its output must not disclose a file it read."""
    body = policy.parent / "scratch" / "body.md"
    body.write_text("Report\n")
    cli.main(
        [
            "--config",
            str(policy),
            "--caller",
            "security-issue-import",
            "--dry-run",
            "issue-create-labeled",
            _title_file(policy, secret),
            str(body),
            '["needs triage"]',
        ]
    )
    captured = capsys.readouterr()
    assert "hunter2" not in captured.out + captured.err


def test_a_title_file_must_live_in_the_workspace(
    policy: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path / "title.txt"
    outside.write_text("Report\n")
    body = policy.parent / "scratch" / "body.md"
    body.write_text("Report\n")
    code = cli.main(
        [
            "--config",
            str(policy),
            "--caller",
            "security-issue-import",
            "--dry-run",
            "issue-create-labeled",
            str(outside),
            str(body),
            '["needs triage"]',
        ]
    )
    assert code != cli.EXIT_OK
    assert "workspace" in capsys.readouterr().err.lower()


def test_github_failure_returns_command_error(policy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    body = policy.parent / "scratch" / "report.md"
    body.write_text("Private security report")

    loaded = config.load(policy)
    monkeypatch.setattr(cli, "load", lambda _path, *, approved_only: loaded)

    calls = []

    def fake_run(argv: list[str], *, check: bool, input: bytes) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = cli.main(
        [
            "--caller",
            "security-issue-import",
            "issue-create-labeled",
            _title_file(policy, "Private security report\n"),
            str(body),
            '["needs triage","security issue"]',
        ]
    )

    assert result == cli.EXIT_COMMAND
    assert len(calls) == 1
    assert calls[0][0] == "gh"


# --------------------------------------------------------------------------- #
# Published body and title files are removed from the workspace
# --------------------------------------------------------------------------- #


def _create(
    policy: Path, monkeypatch: pytest.MonkeyPatch, gh_exit: int, *extra: str
) -> tuple[int, Path, Path]:
    import subprocess

    loaded = config.load(policy)
    monkeypatch.setattr(cli, "load", lambda _path, *, approved_only: loaded)

    def fake_run(argv: list[str], *, check: bool, input: bytes) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, gh_exit)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    title = Path(_title_file(policy, "A report\n"))
    body = policy.parent / "scratch" / "body.md"
    body.write_text("report text")
    rc = cli.main(
        [
            *extra,
            "--caller",
            "security-issue-import",
            "issue-create-labeled",
            str(title),
            str(body),
            '["needs triage"]',
        ]
    )
    return rc, title, body


def test_a_successful_write_removes_its_body_and_title_files(
    policy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc, title, body = _create(policy, monkeypatch, 0)
    assert rc == cli.EXIT_OK
    assert not title.exists()
    assert not body.exists()


def test_a_failed_write_keeps_its_files_for_a_retry(policy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rc, title, body = _create(policy, monkeypatch, 1)
    assert rc == cli.EXIT_COMMAND
    assert title.exists()
    assert body.exists()


def test_a_dry_run_keeps_its_files(policy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rc, title, body = _create(policy, monkeypatch, 0, "--dry-run")
    assert rc == cli.EXIT_OK
    assert title.exists()
    assert body.exists()


def test_consume_leaves_links_and_files_outside_the_workspace(policy: Path, tmp_path: Path) -> None:
    loaded = config.load(policy)
    op = ops.resolve("issue-create-labeled")
    outside = tmp_path / "outside.md"
    outside.write_text("keep")
    target = loaded.workspace / "target.md"
    target.write_text("keep too")
    link = loaded.workspace / "link.md"
    link.symlink_to(target)
    cli._consume(op, [str(outside), str(link), "[]"], loaded)
    assert outside.read_text() == "keep"
    assert link.is_symlink()
    assert target.read_text() == "keep too"


def test_consume_does_not_follow_a_directory_swapped_for_a_link(policy: Path, tmp_path: Path) -> None:
    """A directory below the workspace replaced by a link after the read stops the delete."""
    loaded = config.load(policy)
    op = ops.resolve("issue-create-labeled")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    secret = elsewhere / "body.md"
    secret.write_text("not the workspace's")
    (loaded.workspace / "sub").symlink_to(elsewhere, target_is_directory=True)
    cli._consume(op, ["[]", str(loaded.workspace / "sub" / "body.md"), "[]"], loaded)
    assert secret.read_text() == "not the workspace's"


def test_consume_removes_a_file_in_a_real_subdirectory(policy: Path) -> None:
    loaded = config.load(policy)
    op = ops.resolve("issue-create-labeled")
    sub = loaded.workspace / "sub"
    sub.mkdir()
    body = sub / "body.md"
    body.write_text("x")
    cli._consume(op, ["[]", str(body), "[]"], loaded)
    assert not body.exists()
