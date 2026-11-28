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

import json
import os
import re
from collections.abc import Callable
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
    entry: Callable[[list[str]], int],
) -> None:
    _nothing_runs(monkeypatch)
    op = (
        ["issue-add-label", "7", "needs triage"] if entry is cli.main else ["body-field-get", "7", "Severity"]
    )
    assert entry(["--caller", "security-issue-sync", *op]) == cli.EXIT_POLICY
    err = capsys.readouterr().err
    assert "not an approved copy" in err and str(approved) in err
    # The copy command names the file, as the docs do: no placeholder to fill in.
    assert str(approved / "checkout.toml") in err and "NAME" not in err


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


def test_the_operator_git_file_is_never_an_approved_policy(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # It holds one operator's [git] values, not a policy; even a byte-identical
    # copy of the repository's policy under that name approves nothing.
    data = (project / config.DEFAULT_RELATIVE_PATH).read_bytes()
    (approved / config.OPERATOR_GIT_FILE).write_bytes(data)
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


def _status(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, object] | None, str]:
    code = cli.main_read(["approval-status", *argv])
    out, err = capsys.readouterr()
    return code, (json.loads(out) if out else None), err


def test_approval_status_reports_a_stale_approval(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # An approved copy from before the last policy change: the write entry points would refuse.
    data = (project / config.DEFAULT_RELATIVE_PATH).read_bytes()
    (approved / "acme.toml").write_bytes(data.replace(b"issue-comment", b"issue-comments"))
    _nothing_runs(monkeypatch)
    code, status, _ = _status(capsys)
    assert code == cli.EXIT_OK
    assert status == {
        "policy": str(project.resolve() / config.DEFAULT_RELATIVE_PATH),
        "approved": False,
        "approved_dir": str(approved),
    }


def test_approval_status_reports_an_approved_copy(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (approved / "acme.toml").write_bytes((project / config.DEFAULT_RELATIVE_PATH).read_bytes())
    _nothing_runs(monkeypatch)
    code, status, _ = _status(capsys)
    assert code == cli.EXIT_OK and status is not None
    assert status["approved"] is True
    assert set(status) == {"policy", "approved", "approved_dir"}


def test_approval_status_agrees_with_the_write_entry_point(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A symlink and the operator file approve nothing for the writes, so not here either.
    (approved / "linked.toml").symlink_to(project / config.DEFAULT_RELATIVE_PATH)
    (approved / config.OPERATOR_GIT_FILE).write_bytes((project / config.DEFAULT_RELATIVE_PATH).read_bytes())
    _nothing_runs(monkeypatch)
    _, status, _ = _status(capsys)
    assert status is not None and status["approved"] is False


def test_approval_status_never_prints_the_policy(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (approved / "acme.toml").write_bytes((project / config.DEFAULT_RELATIVE_PATH).read_bytes())
    _nothing_runs(monkeypatch)
    assert cli.main_read(["approval-status"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "acme/tracker" not in out and "security-issue-sync" not in out
    assert out.count("\n") == 1


def test_approval_status_with_no_policy(
    tmp_path: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    code, status, _ = _status(capsys)
    assert code == cli.EXIT_OK
    assert status == {"policy": None, "approved": False, "approved_dir": str(approved)}


@pytest.mark.parametrize(
    "argv",
    [
        ["--config", "/etc/hosts", "approval-status"],
        ["--caller", "security-issue-sync", "approval-status"],
        ["--save", "status.json", "approval-status"],
        ["--dry-run", "approval-status"],
        ["approval-status", "extra"],
    ],
)
def test_approval_status_takes_no_options(
    project: Path,
    approved: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    # Discovery only: `--config` would let it probe whether an arbitrary file
    # exists or matches an approved policy.
    _nothing_runs(monkeypatch)
    code = cli.main_read(argv)
    out, err = capsys.readouterr()
    assert code == cli.EXIT_USAGE
    assert out == "" and "refused" in err


def test_approval_status_refuses_a_symlinked_policy(
    tmp_path: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The committed path redirected to a file the agent can write: refused, as on the writes.
    root = tmp_path / "checkout"
    target = root / config.DEFAULT_RELATIVE_PATH
    target.parent.mkdir(parents=True)
    elsewhere = tmp_path / "planted.toml"
    elsewhere.write_text("workspace = '/tmp'\n")
    target.symlink_to(elsewhere)
    monkeypatch.chdir(root)
    code, status, err = _status(capsys)
    assert code == cli.EXIT_POLICY and status is None
    assert "refusing" in err


def test_approval_status_is_only_on_the_read_entry_point(
    project: Path, approved: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (approved / "acme.toml").write_bytes((project / config.DEFAULT_RELATIVE_PATH).read_bytes())
    _nothing_runs(monkeypatch)
    assert cli.main(["--caller", "security-issue-sync", "approval-status"]) == cli.EXIT_POLICY
    assert "approved" not in capsys.readouterr().out


REPO_ROOT = Path(__file__).resolve().parents[3]
# The copy command names the approved file; capture the placeholder it uses.
APPROVAL_TARGET = re.compile(r"(?:apache-magpie/vetted-ops|<approved_dir>)/<([^>]+)>\.toml")


def test_rendered_approval_command_names_the_defined_placeholder() -> None:
    """Every approval command uses `<project>`, the one name the README defines.

    The sandbox cannot list the approved directory, so a skill told to use
    "the earlier copy's name" cannot fill it in and hands the user a placeholder.
    """
    found: dict[str, str] = {}
    for path in sorted(REPO_ROOT.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith((".git/", ".apache-magpie/")) or "/node_modules/" in rel:
            continue
        for match in APPROVAL_TARGET.finditer(path.read_text(encoding="utf-8")):
            found[f"{rel}: <{match.group(1)}>"] = match.group(1)
    assert found, "no approval command found; the pattern no longer matches the docs"
    assert {k for k, v in found.items() if v != "project"} == set()
    readme = (REPO_ROOT / "tools" / "vetted-ops" / "README.md").read_text(encoding="utf-8")
    assert "`<project>` is the project's slug" in readme


def _manifest(root: Path, short_name: str) -> None:
    manifest = root / ".apache-magpie-overrides" / "project.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        f"| Key | Value |\n|---|---|\n| `short_name` | `{short_name}` (derived from repo name) |\n"
    )


def test_approved_copy_name_is_the_lowercased_short_name(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    _manifest(root, "Magpie")
    assert config.approved_copy_name(root) == "magpie.toml"


def test_approved_copy_name_falls_back_to_the_checkout_name(tmp_path: Path) -> None:
    root = tmp_path / "Foo-Project"
    root.mkdir()
    assert config.approved_copy_name(root) == "foo-project.toml"


def test_approved_copy_name_uses_the_main_checkout_from_a_linked_worktree(tmp_path: Path) -> None:
    main = tmp_path / "product"
    (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
    (main / ".git" / "worktrees" / "wt" / "commondir").write_text("../..\n")
    worktree = tmp_path / "some-branch"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'wt'}\n")
    assert config.approved_copy_name(worktree) == "product.toml"


@pytest.mark.parametrize(
    "hostile",
    ["../../.ssh/authorized_keys", ".hidden", "a b", "x/y", "operator-git", "a" * 65, "foo.bar"],
)
def test_approved_copy_name_never_suggests_an_unsafe_name(tmp_path: Path, hostile: str) -> None:
    """The manifest is agent-writable and the name lands in a `cp` the user runs."""
    root = tmp_path / "operator-git"  # the checkout name is no escape either
    _manifest(root, hostile)
    assert config.approved_copy_name(root) == config.FALLBACK_COPY_NAME
