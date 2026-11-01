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
"""The write entry points run outside the sandbox and act only on an approved policy.

The working directory is the caller's choice, so discovery alone can find a
policy the agent planted (a directory renamed into place defeats any deny glob).
A policy is therefore acted on only when it is byte-for-byte a file the user
copied into `config.approved_dir()`, which no sandboxed command can write.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NoReturn

import pytest

from vetted_ops import cli, config, procedures

POLICY = """
workspace = '{workspace}'

[repos]
tracker = "acme/tracker"
upstream = "acme/product"

[values]
labels = ["needs triage"]

[callers]
"security-issue-sync" = ["issue-view", "issue-add-label", "issue-comment"]
"""


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout with a committed policy, as the working directory."""
    root = tmp_path / "checkout"
    workspace = root / "scratch"
    workspace.mkdir(parents=True)
    workspace.chmod(0o700)
    policy = root / config.DEFAULT_RELATIVE_PATH
    policy.parent.mkdir(parents=True)
    policy.write_text(POLICY.format(workspace=workspace))
    monkeypatch.chdir(root)
    return root


def _nothing_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_subprocess(*_a: object, **_k: object) -> NoReturn:
        raise AssertionError("nothing may run")

    monkeypatch.setattr(cli.subprocess, "run", no_subprocess)
    monkeypatch.setattr(procedures, "subprocess_exec", no_subprocess)


@pytest.mark.parametrize("entry", [cli.main, cli.main_tracker])
def test_an_unapproved_policy_is_refused_on_the_write_entry_points(
    project: Path,
    approved: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    entry: object,
) -> None:
    _nothing_runs(monkeypatch)
    op = (
        ["issue-add-label", "7", "needs triage"] if entry is cli.main else ["body-field-get", "7", "Severity"]
    )
    assert entry(["--caller", "security-issue-sync", *op]) == cli.EXIT_POLICY  # type: ignore[operator]
    err = capsys.readouterr().err
    assert "not an approved copy" in err and str(approved) in err


def test_an_approved_copy_lets_the_write_run(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (approved / "acme.toml").write_bytes((project / config.DEFAULT_RELATIVE_PATH).read_bytes())
    ran: list[list[str]] = []

    def fake_run(argv: list[str], **_k: object) -> object:
        ran.append(argv)
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    assert (
        cli.main(["--caller", "security-issue-sync", "issue-add-label", "7", "needs triage"]) == cli.EXIT_OK
    )
    assert ran and "acme/tracker" in ran[0]


def test_a_policy_differing_by_one_byte_is_not_approved(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A planted policy that only resembles an approved one (another workspace,
    # another repository) gains nothing.
    data = (project / config.DEFAULT_RELATIVE_PATH).read_bytes()
    (approved / "acme.toml").write_bytes(data.replace(b"acme/tracker", b"acme/trackes"))
    _nothing_runs(monkeypatch)
    assert (
        cli.main(["--caller", "security-issue-sync", "issue-add-label", "7", "needs triage"])
        == cli.EXIT_POLICY
    )


def test_a_symlink_in_the_approved_directory_does_not_approve(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A link back to the repository's policy would re-trust a path the agent can reach.
    (approved / "acme.toml").symlink_to(project / config.DEFAULT_RELATIVE_PATH)
    _nothing_runs(monkeypatch)
    assert (
        cli.main(["--caller", "security-issue-sync", "issue-add-label", "7", "needs triage"])
        == cli.EXIT_POLICY
    )


def test_reads_and_dry_runs_need_no_approval(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _nothing_runs(monkeypatch)
    argv = ["--caller", "security-issue-sync", "--dry-run", "issue-add-label", "7", "needs triage"]
    assert cli.main(argv) == cli.EXIT_OK
    assert "acme/tracker" in capsys.readouterr().out
    assert config.load().upstream_repo == "acme/product"


def test_the_home_comes_from_the_password_database_not_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `HOME=… vetted-op …` must not move the approved directory or a `~` workspace.
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    real = config.account_home()
    assert real != tmp_path / "elsewhere"
    assert config.approved_dir() == real / ".config" / "apache-magpie" / "vetted-ops"
    assert config._expand_home("~/scratch") == real / "scratch"


def test_read_regular_file_refuses_a_symlinked_parent_and_a_fifo(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "policy.toml").write_text("x")
    (tmp_path / "link").symlink_to(real)
    with pytest.raises(config.TamperedPath):
        config.read_regular_file(tmp_path / "link" / "policy.toml")
    fifo = tmp_path / "fifo.toml"
    os.mkfifo(fifo)
    with pytest.raises(config.TamperedPath):
        config.read_regular_file(fifo)
    assert config.read_regular_file(real / "policy.toml") == b"x"
    assert config.read_regular_file(real / "missing.toml") is None


@pytest.mark.parametrize("relative", [False, True])
def test_a_workspace_through_a_symlink_is_refused(tmp_path: Path, relative: bool) -> None:
    # An approved policy, planted in an agent-chosen directory, whose workspace
    # the agent swapped for a link to a private directory (~/.ssh, say): owned
    # by the user and mode 0700, it would pass every other workspace check.
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    (private / "id_ed25519").write_text("PRIVATE KEY")
    checkout = tmp_path / "planted"
    checkout.mkdir()
    (checkout / "scratch").symlink_to(private)
    workspace = "scratch" if relative else str(checkout / "scratch")
    policy = checkout / config.DEFAULT_RELATIVE_PATH
    policy.parent.mkdir(parents=True)
    policy.write_text(POLICY.format(workspace=workspace))
    with pytest.raises(config.ConfigError, match="symlink"):
        config.load(cwd=checkout)


def test_a_body_behind_a_swapped_directory_is_refused(tmp_path: Path) -> None:
    # The workspace itself is real, but a directory inside it became a link.
    from vetted_ops import ops

    workspace = tmp_path / "scratch"
    workspace.mkdir(mode=0o700)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    (private / "id_ed25519").write_text("PRIVATE KEY")
    (workspace / "bodies").symlink_to(private)
    with pytest.raises(ops.ParamError, match="symlink"):
        ops.read_body(str(workspace / "bodies" / "id_ed25519"), workspace=workspace)


def test_the_approval_hint_quotes_a_hostile_path(
    tmp_path: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The hint is meant to be pasted into a terminal; the checkout path is the agent's choice.
    root = tmp_path / "x; touch pwned #"
    workspace = root / "scratch"
    workspace.mkdir(parents=True, mode=0o700)
    policy = root / config.DEFAULT_RELATIVE_PATH
    policy.parent.mkdir(parents=True)
    policy.write_text(POLICY.format(workspace=workspace))
    monkeypatch.chdir(root)
    _nothing_runs(monkeypatch)
    assert (
        cli.main(["--caller", "security-issue-sync", "issue-add-label", "7", "needs triage"])
        == cli.EXIT_POLICY
    )
    err = capsys.readouterr().err
    assert f"cp '{root.resolve() / config.DEFAULT_RELATIVE_PATH}'" in err
