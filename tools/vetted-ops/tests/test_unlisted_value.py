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
"""A value the policy's [values] does not list: exit 5, one JSON line per value, nothing run.

The allowlist is unchanged; what these tests pin is the recovery path. The
refusal names the ``[values]`` key a reviewed policy change would add the value
to, on every entry point, and the value never reaches ``gh``, the HTTP client,
a tracker backend or a batch. Every other refusal keeps exit 3 and prints no
JSON line. The policy is loaded from an explicit path and handed to the write
entry point by patching its `load`, so nothing here writes a policy at a path
the secure sandbox denies.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, NoReturn

import pytest

from vetted_ops import batch, cli, config, ops, procedures, tracker_backends

UNLISTED = "not-listed-x"
CALLER = "skill"

#: Enum-gated operations, each with the [values] key gating each enum parameter.
ENUM_OPS = sorted(name for name, op in ops.OPS.items() if op.enums)

#: A valid value for every parameter an enum-gated operation takes besides its enums.
OTHER_PARAMS = {
    "number": "7",
    "item_id": "PVTI_item1",
    "package_name": "jinja2",
    "version": "1.0.0",
    # The Vulnogram operations refuse on `pmc`, their first parameter, before
    # the record id or a title / record file is read.
    "cve_id": "CVE-2026-12345",
    "title": "title.txt",
    "body": "record.json",
}

POLICY = """
workspace = '{workspace}'

[repos]
tracker = "acme/tracker"
upstream = "acme/product"

[values]
labels = ["needs triage"]
upstream_labels = ["area:core"]
milestones = ["1.2.3"]
{patterns}
assignees = ["alice"]
issue_states = ["open"]
pr_states = ["open"]
close_reasons = ["completed"]
ecosystems = ["PyPI"]
pmcs = ["airflow"]
board_project_id = "PVT_board1"
board_status_field_id = "PVTSSF_status"

[values.board_columns]
"Assessed" = "opt1"

[approval]
private_tracker_writes = "batch"

[callers]
"skill" = {ops}
"""


def _policy(tmp_path: Path, *, patterns: bool = False, extra: str = "") -> Path:
    workspace = tmp_path / "ws"
    workspace.mkdir(mode=0o700, exist_ok=True)
    path = tmp_path / "policy.toml"
    grants = json.dumps(sorted(ops.OPS))
    pattern_line = r"milestones_patterns = ['Providers \d{4}-\d{2}-\d{2}']" if patterns else ""
    path.write_text(POLICY.format(workspace=workspace, ops=grants, patterns=pattern_line) + extra)
    return path


@pytest.fixture()
def policy(tmp_path: Path) -> Path:
    return _policy(tmp_path)


@pytest.fixture()
def nothing_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail on any subprocess, procedure call or HTTP request: an unlisted value reaches none."""

    def refuse(*_a: object, **_k: object) -> NoReturn:
        raise AssertionError("an unlisted value reached a command")

    monkeypatch.setattr(cli.subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(procedures, "subprocess_exec", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(tracker_backends, "translate", refuse)


def _args(name: str, *, enum_value: str = UNLISTED) -> tuple[list[str], str, str]:
    """The positional parameters for ``name``, its first enum parameter set to ``enum_value``."""
    op = ops.OPS[name]
    param, key = next(iter(op.enums.items()))
    listed = {
        "labels": "needs triage",
        "upstream_labels": "area:core",
        "milestones": "1.2.3",
        "assignees": "alice",
        "issue_states": "open",
        "pr_states": "open",
        "close_reasons": "completed",
        "ecosystems": "PyPI",
        "pmcs": "airflow",
        "board_columns": "Assessed",
    }
    values = []
    for p in op.params:
        if p == param:
            values.append(enum_value)
        elif p in op.enums:
            values.append(listed[op.enums[p]])
        else:
            values.append(OTHER_PARAMS[p])
    return values, param, key


def _records(err: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in err.splitlines() if line.startswith("{")]


def _run(name: str, values: list[str], cfg: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Run ``name`` for real (no dry run) on its own entry point, policy handed to `load`."""
    loaded = config.load(cfg)
    monkeypatch.setattr(cli, "load", lambda *_a, **_k: loaded)
    entry = cli.main if ops.OPS[name].writes else cli.main_read
    return entry(["--caller", CALLER, name, *values])


def test_the_catalogue_has_enum_gated_ops() -> None:
    # Guards the parametrisation below against silently covering nothing.
    assert len(ENUM_OPS) >= 20
    assert {"issue-add-label", "pr-add-label", "issue-set-milestone", "issue-add-assignee"} <= set(ENUM_OPS)


@pytest.mark.parametrize("name", ENUM_OPS)
def test_every_enum_gated_op_refuses_with_exit_5_and_its_values_key(
    name: str, policy: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    values, param, key = _args(name)
    assert _run(name, values, policy, monkeypatch) == cli.EXIT_UNLISTED == 5
    err = capsys.readouterr().err
    assert f"vetted-op: refused: value {UNLISTED!r} is not in [values] {key}" in err
    [record] = _records(err)
    assert record["refused"] == "unlisted-value"
    assert record["operation"] == name
    assert record["caller"] == CALLER
    assert record["parameter"] == param
    assert record["value"] == UNLISTED
    assert record["key"] == key == ops.OPS[name].enums[param]
    assert record["policy"] == str(policy.resolve())
    assert str(record["approved_copy"]).endswith(".toml")
    assert "entry" not in record


@pytest.mark.parametrize("name", ENUM_OPS)
def test_a_dry_run_refuses_the_same_way(name: str, policy: Path, capsys: Any, nothing_runs: None) -> None:
    values, _, key = _args(name)
    argv = ["--config", str(policy), "--caller", CALLER, "--dry-run", name, *values]
    entry = cli.main if ops.OPS[name].writes else cli.main_read
    assert entry(argv) == cli.EXIT_UNLISTED
    assert _records(capsys.readouterr().err)[0]["key"] == key


@pytest.mark.parametrize("name", ["issue-set-milestone", "pr-set-milestone", "milestone-create"])
def test_milestone_patterns_keep_matching_and_refuse_in_the_same_shape(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    cfg = _policy(tmp_path, patterns=True)
    values, _, _ = _args(name)
    assert _run(name, values, cfg, monkeypatch) == cli.EXIT_UNLISTED
    [record] = _records(capsys.readouterr().err)
    assert (record["key"], record["value"]) == ("milestones", UNLISTED)
    # A pattern match is still accepted (dry run: nothing runs).
    matched, _, _ = _args(name, enum_value="Providers 2026-11-17")
    assert cli.main(["--config", str(cfg), "--caller", CALLER, "--dry-run", name, *matched]) == cli.EXIT_OK


def test_issue_create_labeled_reports_every_unlisted_label(
    policy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    ws = tmp_path / "ws"
    (ws / "title.txt").write_text("A title\n")
    (ws / "body.md").write_text("body\n")
    labels = json.dumps(["needs triage", "scope:core", "scope:ui"])
    code = _run(
        "issue-create-labeled", [str(ws / "title.txt"), str(ws / "body.md"), labels], policy, monkeypatch
    )
    assert code == cli.EXIT_UNLISTED
    err = capsys.readouterr().err
    assert "values 'scope:core', 'scope:ui' are not in [values] labels" in err
    records = _records(err)
    assert [r["value"] for r in records] == ["scope:core", "scope:ui"]
    assert {(r["operation"], r["parameter"], r["key"]) for r in records} == {
        ("issue-create-labeled", "labels", "labels")
    }
    # The files stay for the retry the user may approve.
    assert (ws / "title.txt").exists() and (ws / "body.md").exists()


def test_a_label_that_is_not_a_plain_name_stays_a_malformed_refusal(
    policy: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    assert _run("issue-add-label", ["7", "bad​label"], policy, monkeypatch) == cli.EXIT_POLICY
    assert _records(capsys.readouterr().err) == []


@pytest.mark.parametrize(
    ("argv", "needle"),
    [
        (["no-such-op"], "unknown"),
        (["issue-add-label", "7"], "takes 2 parameter"),
        (["--", "issue-add-label", "7", "-R"], "may not start with '-'"),
        (["issue-add-label", "seven", "needs triage"], "invalid number"),
    ],
)
def test_other_refusals_keep_exit_3_and_print_no_json(
    argv: list[str],
    needle: str,
    policy: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
    nothing_runs: None,
) -> None:
    loaded = config.load(policy)
    monkeypatch.setattr(cli, "load", lambda *_a, **_k: loaded)
    assert cli.main(["--caller", CALLER, *argv]) == cli.EXIT_POLICY
    err = capsys.readouterr().err
    assert needle in err
    assert _records(err) == []


def test_a_caller_not_permitted_keeps_exit_3(
    policy: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    loaded = config.load(policy)
    monkeypatch.setattr(cli, "load", lambda *_a, **_k: loaded)
    assert cli.main(["--caller", "nobody", "issue-add-label", "7", UNLISTED]) == cli.EXIT_POLICY
    assert _records(capsys.readouterr().err) == []


def test_the_tracker_entry_point_refuses_a_non_procedure_before_any_value_check(
    policy: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    loaded = config.load(policy)
    monkeypatch.setattr(cli, "load", lambda *_a, **_k: loaded)
    assert cli.main_tracker(["--caller", CALLER, "issue-add-label", "7", UNLISTED]) == cli.EXIT_POLICY
    assert _records(capsys.readouterr().err) == []


def test_a_missing_values_key_stays_a_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    cfg = _policy(tmp_path)
    cfg.write_text(cfg.read_text().replace('assignees = ["alice"]\n', ""))
    assert _run("issue-add-assignee", ["7", UNLISTED], cfg, monkeypatch) == cli.EXIT_POLICY
    err = capsys.readouterr().err
    assert "declares no 'assignees' list" in err
    assert _records(err) == []


@pytest.mark.parametrize(
    "tracker",
    [
        '\n[tracker]\nplatform = "jira"\njira_url = "https://issues.example.org/jira"\n'
        'jira_project = "FOOSEC"\njira_security_level = "Security Team"\n',
    ],
)
def test_a_non_github_tracker_checks_the_value_before_translating(
    tracker: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    cfg = _policy(tmp_path, extra=tracker)
    assert _run("issue-add-label", ["FOOSEC-12", UNLISTED], cfg, monkeypatch) == cli.EXIT_UNLISTED
    [record] = _records(capsys.readouterr().err)
    assert (record["key"], record["value"]) == ("labels", UNLISTED)


# ---- batches ----------------------------------------------------------------


def _manifest(policy: Path, entries: list[dict[str, object]]) -> str:
    path = policy.parent / "ws" / "batch.json"
    path.write_text(json.dumps({"version": 1, "ops": entries}))
    return str(path)


BAD_BATCH: list[dict[str, object]] = [
    {"op": "issue-add-label", "params": ["12", "needs triage"]},
    {"op": "issue-add-label", "params": ["12", UNLISTED]},
    {"op": "issue-set-milestone", "params": ["12", "9.9.9"]},
]


@pytest.mark.parametrize("entry_point", ["batch-check", "main_batch", "main_batch_unprompted"])
@pytest.mark.parametrize("patterns", [False, True])
def test_a_batch_names_every_entry_with_an_unlisted_value(
    entry_point: str,
    patterns: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
    nothing_runs: None,
) -> None:
    cfg = _policy(tmp_path, patterns=patterns)
    if entry_point == "main_batch_unprompted":
        cfg.write_text(
            cfg.read_text().replace('private_tracker_writes = "batch"', 'private_tracker_writes = "none"')
        )
    loaded = config.load(cfg)
    monkeypatch.setattr(batch, "load", lambda *_a, **_k: loaded)
    manifest = _manifest(cfg, BAD_BATCH)
    if entry_point == "batch-check":
        code = cli.main_read(["--caller", CALLER, "batch-check", manifest])
    else:
        code = getattr(cli, entry_point)(["--caller", CALLER, "--expect", "0" * 16, manifest])
    assert code == batch.EXIT_UNLISTED == cli.EXIT_UNLISTED
    err = capsys.readouterr().err
    assert "entry 2 (issue-add-label)" in err
    records = _records(err)
    assert [(r["entry"], r["operation"], r["key"], r["value"]) for r in records] == [
        (2, "issue-add-label", "labels", UNLISTED),
        (3, "issue-set-milestone", "milestones", "9.9.9"),
    ]


def test_a_batch_with_another_fault_keeps_exit_3(
    policy: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, nothing_runs: None
) -> None:
    loaded = config.load(policy)
    monkeypatch.setattr(batch, "load", lambda *_a, **_k: loaded)
    manifest = _manifest(policy, [*BAD_BATCH, {"op": "pr-comment", "params": ["7", "x"]}])
    assert cli.main_read(["--caller", CALLER, "batch-check", manifest]) == cli.EXIT_POLICY
    assert _records(capsys.readouterr().err) == []
