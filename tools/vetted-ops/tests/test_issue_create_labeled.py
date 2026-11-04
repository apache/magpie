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
            "Security report",
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
            "Private security report",
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
            "Private security report",
            str(body),
            '["needs triage","security issue"]',
        ]
    )

    assert result == cli.EXIT_COMMAND
    assert len(calls) == 1
    assert calls[0][0] == "gh"
