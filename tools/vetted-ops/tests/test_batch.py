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
"""Batches of private-tracker writes: checked whole before anything runs, run in order, stopped at a failure.

The policy is loaded from an explicit path and handed to the entry points by
patching their `load`, so these tests never write a policy at a path the
secure sandbox denies; discovery and approval have their own tests.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
from pathlib import Path
from typing import Any, NoReturn

import pytest

from vetted_ops import batch, cli, config, ops, procedures

TRACKER = "acme/tracker"
BOARD = "PVT_board1"

POLICY = """
workspace = '{workspace}'

[repos]
tracker = "acme/tracker"
upstream = "acme/product"

[values]
labels = ["needs triage", "security issue"]
upstream_labels = ["area:core"]
board_project_id = "PVT_board1"
board_status_field_id = "PVTSSF_status"

[values.board_columns]
"Assessed" = "opt1"

[approval]
private_tracker_writes = "{mode}"

[callers]
"security-issue-import" = [
    "issue-create-labeled", "issue-add-label", "issue-comment", "rollup-append",
    "board-set-status", "repo-issue-comment", "pr-comment", "advisory-comment",
    "issue-view",
]
"""


class Gh:
    """Stands in for every `gh` the dispatcher and the privacy check run."""

    def __init__(self, *, private: bytes = b"true\n", board_public: bytes = b"false\n") -> None:
        self.private = private
        self.board_public = board_public
        self.writes: list[list[str]] = []
        self.fail_at: int | None = None

    def exec(self, argv: list[str], stdin: bytes | None) -> tuple[int, bytes, bytes]:
        if argv[:3] == ["gh", "api", f"repos/{TRACKER}"]:
            return 0, self.private, b""
        if "query=query($id:ID!){node(id:$id){... on ProjectV2{public}}}" in argv:
            return 0, self.board_public, b""
        raise AssertionError(f"unexpected read {argv}")

    def run(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        self.writes.append(argv)
        code = 1 if self.fail_at == len(self.writes) else 0
        return subprocess.CompletedProcess(argv, code, b"", b"")


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir(mode=0o700)
    return ws


def _config(tmp_path: Path, workspace: Path, mode: str = "batch") -> config.Config:
    path = tmp_path / "policy.toml"
    path.write_text(POLICY.format(workspace=workspace, mode=mode))
    return config.load(path)


@pytest.fixture()
def cfg(tmp_path: Path, workspace: Path) -> config.Config:
    return _config(tmp_path, workspace)


@pytest.fixture()
def gh(monkeypatch: pytest.MonkeyPatch) -> Gh:
    fake = Gh()
    monkeypatch.setattr(procedures, "subprocess_exec", fake.exec)
    monkeypatch.setattr(cli.subprocess, "run", fake.run)
    return fake


def _write(workspace: Path, name: str, text: str) -> str:
    path = workspace / name
    path.write_text(text)
    return str(path)


def _manifest(workspace: Path, entries: list[dict[str, object]], name: str = "batch.json") -> str:
    return _write(workspace, name, json.dumps({"version": 1, "ops": entries}))


def _three(workspace: Path) -> str:
    body = _write(workspace, "comment.md", "triage notes")
    title = _write(workspace, "title.txt", "Path traversal in the importer")
    created = _write(workspace, "created.md", "report body")
    return _manifest(
        workspace,
        [
            {"op": "issue-create-labeled", "params": [title, created, '["needs triage"]']},
            {"op": "issue-add-label", "params": ["12", "security issue"]},
            {"op": "issue-comment", "params": ["12", body]},
        ],
    )


def _check(cfg: config.Config, caller: str, manifest: str) -> batch.Batch:
    """`batch.check` with the single-call machinery the console scripts hand it."""
    return batch.check(cfg, caller, manifest, cli.BATCH_SINGLE)


def _main(cfg: config.Config, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    monkeypatch.setattr(batch, "load", lambda *_a, **_k: cfg)
    return cli.main_batch(argv)


def _nothing_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_run(*_a: object, **_k: object) -> NoReturn:
        raise AssertionError("nothing may run")

    monkeypatch.setattr(cli.subprocess, "run", no_run)


# ---- a valid batch --------------------------------------------------------


def test_a_valid_batch_runs_every_entry_in_order(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    manifest = _three(workspace)
    digest = _check(cfg, "security-issue-import", manifest).short

    code = _main(cfg, monkeypatch, ["--caller", "security-issue-import", "--expect", digest, manifest])

    assert code == 0
    assert [w[:3] for w in gh.writes] == [
        ["gh", "api", f"repos/{TRACKER}/issues"],
        ["gh", "issue", "edit"],
        ["gh", "issue", "comment"],
    ]
    out = capsys.readouterr().out
    assert f"batch {digest}: 3 private-tracker write(s) on {TRACKER} (private: confirmed)" in out
    assert json.loads(out.strip().splitlines()[-1]) == {
        "batch": "done",
        "digest": digest,
        "ran": 3,
        "total": 3,
    }
    # Published bodies, titles and the manifest itself are consumed.
    assert sorted(os.listdir(workspace)) == []


def test_the_summary_shows_bodies_and_file_titles_by_size_only(cfg: config.Config, workspace: Path) -> None:
    checked = _check(cfg, "security-issue-import", _three(workspace))
    text = batch.summary(checked, "security-issue-import", TRACKER)
    assert "title=<file, 30 chars>" in text
    assert "body=<file, 12 bytes>" in text
    assert "triage notes" not in text
    assert "Path traversal" not in text
    assert "label=security issue" in text


# ---- refused before anything runs ------------------------------------------


@pytest.mark.parametrize(
    ("bad", "code"),
    [
        # Unlisted, not malformed: its own exit code, so the skill can ask the user.
        ({"op": "issue-add-label", "params": ["12", "not-a-policy-label"]}, batch.EXIT_UNLISTED),
        ({"op": "issue-add-label", "params": ["12"]}, 3),
        ({"op": "issue-add-label", "params": ["-R", "acme/product"]}, 3),
        ({"op": "no-such-op", "params": []}, 3),
        ({"op": "issue-view", "params": ["12"]}, 3),
    ],
)
def test_one_invalid_entry_refuses_the_whole_batch(
    cfg: config.Config,
    workspace: Path,
    gh: Gh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
    bad: dict[str, object],
    code: int,
) -> None:
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}, bad])
    _nothing_writes(monkeypatch)
    with pytest.raises(batch.BatchRefused, match="entry 2"):
        _check(cfg, "security-issue-import", manifest)
    assert (
        _main(cfg, monkeypatch, ["--caller", "security-issue-import", "--expect", "0" * 16, manifest]) == code
    )
    assert "entry 2" in capsys.readouterr().err
    assert gh.writes == []


@pytest.mark.parametrize("op", ["repo-issue-comment", "pr-comment", "advisory-comment"])
def test_a_public_or_outbound_write_is_refused_even_when_granted(
    cfg: config.Config, workspace: Path, op: str
) -> None:
    body = _write(workspace, "public.md", "hello")
    target = "GHSA-abcd-efgh-ijkl" if op == "advisory-comment" else "7"
    manifest = _manifest(
        workspace,
        [
            {"op": "issue-add-label", "params": ["12", "needs triage"]},
            {"op": op, "params": [target, body]},
        ],
    )
    with pytest.raises(batch.BatchRefused, match="not a private-tracker write"):
        _check(cfg, "security-issue-import", manifest)


def test_every_batchable_operation_is_a_write_that_exists() -> None:
    for name in batch.BATCHABLE:
        assert ops.OPS[name].writes, name
    # The public and outbound writes stay out by construction.
    assert not batch.BATCHABLE & {
        "pr-comment",
        "repo-issue-comment",
        "advisory-comment",
        "cve-record-update",
        "cve-allocate",
        "tracker-publish",
    }


def test_a_command_aimed_off_the_tracker_is_refused(cfg: config.Config) -> None:
    op = ops.OPS["issue-add-label"]
    with pytest.raises(batch.BatchRefused, match="does not address the tracker"):
        batch._check_target(op, ["gh", "issue", "edit", "1", "--repo", "acme/product"], cfg)
    with pytest.raises(batch.BatchRefused, match="does not address the tracker"):
        batch._check_target(ops.OPS["issue-create"], ["gh", "api", "repos/acme/product/issues"], cfg)
    with pytest.raises(batch.BatchRefused, match="project board"):
        batch._check_target(ops.OPS["board-set-status"], ["gh", "api", "graphql", "-F", "project=PVT_x"], cfg)


def test_an_ungranted_operation_is_refused(tmp_path: Path, workspace: Path) -> None:
    cfg = _config(tmp_path, workspace)
    manifest = _manifest(workspace, [{"op": "issue-close", "params": ["12", "completed"]}])
    with pytest.raises(batch.BatchRefused, match="not permitted"):
        _check(cfg, "security-issue-import", manifest)


def test_batching_is_off_by_default(tmp_path: Path, workspace: Path) -> None:
    path = tmp_path / "default.toml"
    path.write_text(
        POLICY.format(workspace=workspace, mode="batch").replace('private_tracker_writes = "batch"', "")
    )
    cfg = config.load(path)
    assert cfg.private_tracker_writes == "each"
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    with pytest.raises(batch.BatchRefused, match="batching is off"):
        _check(cfg, "security-issue-import", manifest)


@pytest.mark.parametrize("mode", ["each", "batch", "none"])
def test_the_approval_knob_takes_its_three_values(tmp_path: Path, workspace: Path, mode: str) -> None:
    assert _config(tmp_path, workspace, mode).private_tracker_writes == mode


@pytest.mark.parametrize(
    "table", ['private_tracker_writes = "always"', 'private_tracker_writes = "each"\nother = 1']
)
def test_a_malformed_approval_table_is_refused(tmp_path: Path, workspace: Path, table: str) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        POLICY.format(workspace=workspace, mode="batch").replace('private_tracker_writes = "batch"', table)
    )
    with pytest.raises(config.ConfigError, match="approval"):
        config.load(path)


# ---- the manifest file ------------------------------------------------------


def test_a_manifest_outside_the_workspace_is_refused(cfg: config.Config, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere.json"
    outside.write_text(json.dumps({"version": 1, "ops": []}))
    with pytest.raises(batch.BatchRefused, match="manifest: body file must live under the workspace"):
        _check(cfg, "security-issue-import", str(outside))


def test_a_symlinked_manifest_is_refused(cfg: config.Config, workspace: Path, tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text(json.dumps({"version": 1, "ops": [{"op": "issue-reopen", "params": ["1"]}]}))
    (workspace / "link.json").symlink_to(real)
    with pytest.raises(batch.BatchRefused, match="manifest"):
        _check(cfg, "security-issue-import", str(workspace / "link.json"))


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"version": 2, "ops": [{"op": "issue-reopen", "params": ["1"]}]}),
        json.dumps({"version": 1, "ops": []}),
        json.dumps({"version": 1, "ops": [{"op": "issue-reopen", "params": [1]}]}),
        json.dumps({"version": 1, "ops": [{"op": "issue-reopen", "params": ["1"], "caller": "x"}]}),
        json.dumps({"version": 1, "ops": [], "caller": "privileged"}),
    ],
)
def test_a_malformed_manifest_is_refused(cfg: config.Config, workspace: Path, content: str) -> None:
    with pytest.raises(batch.BatchRefused):
        _check(cfg, "security-issue-import", _write(workspace, "m.json", content))


def test_a_manifest_must_be_json(cfg: config.Config, workspace: Path) -> None:
    with pytest.raises(batch.BatchRefused, match=r"\.json"):
        _check(cfg, "security-issue-import", _write(workspace, "m.txt", "{}"))


# ---- the digest binds what the user approved ---------------------------------


def test_a_changed_body_changes_the_digest_and_the_run_refuses(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    manifest = _three(workspace)
    seen = _check(cfg, "security-issue-import", manifest).short
    (workspace / "comment.md").write_text("something else entirely")
    code = _main(cfg, monkeypatch, ["--caller", "security-issue-import", "--expect", seen, manifest])
    assert code == 3
    assert "changed since it was checked" in capsys.readouterr().err
    assert gh.writes == []


# ---- the tracker must be private --------------------------------------------


def test_a_public_tracker_refuses_the_batch(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    gh.private = b"false\n"
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    digest = _check(cfg, "security-issue-import", manifest).short
    assert _main(cfg, monkeypatch, ["--caller", "security-issue-import", "--expect", digest, manifest]) == 3
    assert "private repository" in capsys.readouterr().err
    assert gh.writes == []


def test_a_public_board_refuses_a_batch_that_moves_cards(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    gh.board_public = b"true\n"
    manifest = _manifest(workspace, [{"op": "board-set-status", "params": ["PVTI_item1", "Assessed"]}])
    digest = _check(cfg, "security-issue-import", manifest).short
    assert _main(cfg, monkeypatch, ["--caller", "security-issue-import", "--expect", digest, manifest]) == 3
    assert "board is not public" in capsys.readouterr().err
    assert gh.writes == []


# ---- stopping at the first failure --------------------------------------------


def test_the_run_stops_at_the_first_failure_and_reports_what_ran(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    manifest = _three(workspace)
    digest = _check(cfg, "security-issue-import", manifest).short
    gh.fail_at = 2

    code = _main(cfg, monkeypatch, ["--caller", "security-issue-import", "--expect", digest, manifest])

    assert code == 4
    assert len(gh.writes) == 2  # the third entry never ran
    captured = capsys.readouterr()
    report = json.loads(captured.out.strip().splitlines()[-1])
    # The failing entry may have landed before gh reported an error: its outcome
    # is unknown, never "not run"; only the entries after it did not run.
    assert report == {
        "batch": "stopped",
        "digest": digest,
        "succeeded": [1],
        "unknown": 2,
        "op": "issue-add-label",
        "not_run": [3],
        "total": 3,
    }
    assert "outcome is unknown" in captured.err
    assert "read the tracker" in captured.err


def test_a_stopped_batch_keeps_every_file_so_the_recovery_manifest_validates(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _three(workspace)
    digest = _check(cfg, "security-issue-import", manifest).short
    gh.fail_at = 2
    assert _main(cfg, monkeypatch, ["--caller", "security-issue-import", "--expect", digest, manifest]) == 4

    # Nothing is consumed on a stop, not even the files of the entry that succeeded.
    for name in ("title.txt", "created.md", "comment.md"):
        assert (workspace / name).exists(), name
    # The spent manifest goes, so it cannot be rerun blindly (entry 1 would create a second tracker).
    assert not Path(manifest).exists()
    # A recovery manifest naming the unknown and not-run entries still checks.
    recovery = _manifest(
        workspace,
        [
            {"op": "issue-add-label", "params": ["12", "security issue"]},
            {"op": "issue-comment", "params": ["12", str(workspace / "comment.md")]},
        ],
        name="recovery.json",
    )
    assert len(_check(cfg, "security-issue-import", recovery).entries) == 2


def test_a_file_named_by_two_entries_is_consumed_once_after_full_success(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    body = _write(workspace, "shared.md", "same text twice")
    manifest = _manifest(
        workspace,
        [{"op": "issue-comment", "params": ["12", body]}, {"op": "issue-comment", "params": ["13", body]}],
    )
    digest = _check(cfg, "security-issue-import", manifest).short
    assert _main(cfg, monkeypatch, ["--caller", "security-issue-import", "--expect", digest, manifest]) == 0
    assert gh.writes[1][:4] == ["gh", "issue", "comment", "13"]
    assert os.listdir(workspace) == []
    assert "could not remove" not in capsys.readouterr().err


# ---- the digest binds the destination and the built commands -------------------


def test_a_batch_checked_under_one_policy_is_refused_under_another(
    tmp_path: Path, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    policy_a = _config(tmp_path, workspace)
    other = tmp_path / "other.toml"
    other.write_text(POLICY.format(workspace=workspace, mode="batch").replace(TRACKER, "acme/other-tracker"))
    policy_b = config.load(other)
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    seen_under_a = _check(policy_a, "security-issue-import", manifest).short

    code = _main(
        policy_b, monkeypatch, ["--caller", "security-issue-import", "--expect", seen_under_a, manifest]
    )

    assert code == 3
    assert "policy it acts under changed" in capsys.readouterr().err
    assert gh.writes == []


def test_the_digest_binds_each_policy_identity_and_destination_field(
    cfg: config.Config, workspace: Path
) -> None:
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    base = _check(cfg, "security-issue-import", manifest).digest
    for changed in (
        dataclasses.replace(cfg, policy_sha256="0" * 64),
        dataclasses.replace(cfg, values={**cfg.values, "board_project_id": "PVT_other"}),
    ):
        assert _check(changed, "security-issue-import", manifest).digest != base
    # The resolved workspace is part of the destination too (a manifest can only
    # be read from its own workspace, so this is checked on the destination itself).
    elsewhere = dataclasses.replace(cfg, workspace=workspace.parent / "other-ws")
    assert batch._destination(elsewhere) != batch._destination(cfg)
    assert (
        b'"policy_sha256"' in batch._destination(cfg)
        and cfg.policy_sha256 in batch._destination(cfg).decode()
    )


def test_the_digest_binds_the_built_command(cfg: config.Config, workspace: Path) -> None:
    # Same policy identity, same manifest; only what the builder produces differs
    # (another board column option id), so what was summarised is not what would run.
    manifest = _manifest(workspace, [{"op": "board-set-status", "params": ["PVTI_item1", "Assessed"]}])
    base = _check(cfg, "security-issue-import", manifest).digest
    moved = dataclasses.replace(cfg, values={**cfg.values, "board_columns": {"Assessed": "opt2"}})
    assert _check(moved, "security-issue-import", manifest).digest != base


# ---- the unprompted entry point -------------------------------------------------


def _unprompted(cfg: config.Config, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    monkeypatch.setattr(batch, "load", lambda *_a, **_k: cfg)
    return cli.main_batch_unprompted(argv)


@pytest.mark.parametrize("mode", ["batch", "each"])
def test_the_unprompted_entry_point_refuses_a_policy_that_asked_for_a_prompt(
    tmp_path: Path, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any, mode: str
) -> None:
    # Under `none` the adopter allows the unprompted script; selecting (by
    # --policy-from or cd) another approved policy set to `batch` must not
    # turn that allow into an unprompted run of a batch that wanted a prompt.
    asked = _config(tmp_path, workspace, mode)
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    argv = [
        "--caller",
        "security-issue-import",
        "--expect",
        "0" * 16,
        manifest,
    ]
    assert _unprompted(asked, monkeypatch, argv) == 3
    assert "private_tracker_writes = 'none'" in capsys.readouterr().err
    assert gh.writes == []


def test_the_unprompted_entry_point_runs_a_none_policy(
    tmp_path: Path, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch
) -> None:
    none = _config(tmp_path, workspace, "none")
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    digest = _check(none, "security-issue-import", manifest).short
    assert (
        _unprompted(none, monkeypatch, ["--caller", "security-issue-import", "--expect", digest, manifest])
        == 0
    )
    assert len(gh.writes) == 1


@pytest.mark.parametrize("mode", ["batch", "none"])
def test_the_prompted_entry_point_runs_batch_and_none_policies(
    tmp_path: Path, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    policy = _config(tmp_path, workspace, mode)
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    digest = _check(policy, "security-issue-import", manifest).short
    assert (
        _main(policy, monkeypatch, ["--caller", "security-issue-import", "--expect", digest, manifest]) == 0
    )


# ---- the read-side check and --policy-from ----------------------------------


def test_batch_check_on_the_read_entry_point_runs_no_write(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    manifest = _three(workspace)
    monkeypatch.setattr(batch, "load", lambda *_a, **_k: cfg)
    _nothing_writes(monkeypatch)
    assert cli.main_read(["--caller", "security-issue-import", "batch-check", manifest]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    report = json.loads(lines[-1])
    assert report["entries"] == 3
    assert report["digest"] == _check(cfg, "security-issue-import", manifest).short
    assert Path(manifest).exists()


def test_batch_check_refuses_an_explicit_config(workspace: Path, capsys: Any) -> None:
    assert (
        cli.main_read(["--caller", "x", "--config", "/tmp/p.toml", "batch-check", str(workspace / "m.json")])
        == 2
    )
    assert "--config" in capsys.readouterr().err


def _operator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, table: str) -> None:
    """The operator's own operator-git.toml, which alone decides what --policy-from may name."""
    from vetted_ops import git_ops

    home = tmp_path / "operator"
    home.mkdir()
    (home / "operator-git.toml").write_text(table)
    monkeypatch.setattr(git_ops, "approved_dir", lambda: home)


def _recording_load(cfg: config.Config, seen: list[dict[str, object]]) -> Any:
    def fake_load(path: object, *, cwd: object = None, approved_only: bool = False) -> config.Config:
        seen.append({"path": path, "cwd": cwd, "approved_only": approved_only})
        return cfg

    return fake_load


@pytest.mark.parametrize("entry", ["main_batch", "main_batch_unprompted", "batch-check"])
def test_policy_from_on_a_batch_names_only_a_listed_checkout(
    cfg: config.Config,
    workspace: Path,
    gh: Gh,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: Any,
    entry: str,
) -> None:
    # The same confinement as vetted-op: an unlisted directory is refused before
    # anything on disk is looked at, so a batch cannot probe the host or read
    # through another project's policy.
    _operator(monkeypatch, tmp_path, '["acme/product"]\ncheckouts = ["/somewhere/else"]\n')
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(batch, "load", _recording_load(cfg, seen))
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    for probe in (tmp_path, Path("/etc"), tmp_path / "missing"):
        if entry == "batch-check":
            argv = ["--caller", "security-issue-import", "--policy-from", str(probe), "batch-check", manifest]
            code = cli.main_read(argv)
        else:
            argv = [
                "--caller",
                "security-issue-import",
                "--policy-from",
                str(probe),
                "--expect",
                "0" * 16,
                manifest,
            ]
            code = getattr(cli, entry)(argv)
        assert code == 3
        assert "is not a checkout your" in capsys.readouterr().err
    assert seen == []
    assert gh.writes == []


def test_policy_from_on_a_batch_needs_the_policy_to_list_that_checkout(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    # Listed, but for another upstream than the approved policy found there names.
    site = tmp_path / "site"
    _operator(monkeypatch, tmp_path, f'["acme/other"]\ncheckouts = ["{site}"]\n')
    monkeypatch.setattr(batch, "load", _recording_load(cfg, []))
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    argv = ["--caller", "security-issue-import", "--policy-from", str(site), "--expect", "0" * 16, manifest]
    assert cli.main_batch(argv) == 3
    assert "does not list" in capsys.readouterr().err
    assert gh.writes == []


def test_policy_from_on_a_batch_loads_the_approved_policy_of_a_listed_checkout(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    site = tmp_path / "site"
    _operator(monkeypatch, tmp_path, f'["acme/product"]\ncheckouts = ["{site}"]\n')
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(batch, "load", _recording_load(cfg, seen))
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    digest = _check(cfg, "security-issue-import", manifest).short
    argv = ["--caller", "security-issue-import", "--policy-from", str(site), "--expect", digest, manifest]
    assert cli.main_batch(argv) == 0
    assert seen == [{"path": None, "cwd": site, "approved_only": True}]
    assert len(gh.writes) == 1


def test_a_repeated_policy_from_is_refused_on_a_batch(
    cfg: config.Config, workspace: Path, gh: Gh, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    # argparse keeps the last one; a rule matched on the first must not be steered by the second.
    monkeypatch.setattr(batch, "load", lambda *_a, **_k: cfg)
    manifest = _manifest(workspace, [{"op": "issue-add-label", "params": ["12", "needs triage"]}])
    argv = ["--caller", "c", "--policy-from", "/a", "--policy-from=/b", "--expect", "0" * 16, manifest]
    assert cli.main_batch(argv) == 3
    assert "--policy-from given more than once" in capsys.readouterr().err
    assert gh.writes == []


@pytest.mark.parametrize("entry", ["main_batch", "main_batch_unprompted"])
@pytest.mark.parametrize(
    "spelling",
    [
        ["--call", "security-issue-import", "--expect", "0" * 16],
        ["--caller", "security-issue-import", "--exp", "0" * 16],
        [
            "--caller",
            "security-issue-import",
            "--expect",
            "0" * 16,
            "--policy-f",
            "/tmp",
            "--policy-from",
            ".",
        ],
    ],
    ids=["caller", "expect", "policy-from"],
)
def test_abbreviated_long_options_are_not_accepted(
    entry: str, spelling: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Exact spellings only, so the repeated-option checks on the raw argv see every one."""
    with pytest.raises(SystemExit) as exc:
        getattr(cli, entry)([*spelling, "manifest.json"])
    assert exc.value.code == 2  # a usage error, before any policy is read
    assert "error:" in capsys.readouterr().err
