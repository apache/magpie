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
"""The pr-management-code-review reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from vetted_ops import cli, config, ops

POLICY = """
workspace = '{workspace}'

[repos]
upstream = "acme/product"

[callers]
"pr-management-code-review" = ["gql-cr-open", "gql-cr-pr", "cr-viewer-commits"]
"""


@pytest.fixture()
def policy(tmp_path: Path) -> config.Config:
    ws = tmp_path / "scratch"
    ws.mkdir()
    ws.chmod(0o700)
    path = tmp_path / "config.toml"
    path.write_text(POLICY.format(workspace=ws))
    return config.load(path)


def _argv(policy: config.Config, name: str, *values: str) -> list[str]:
    op = ops.resolve(name)
    params, _ = cli._validate_params(op, list(values), policy)
    built = cli.build_argv(op, params, policy)
    assert isinstance(built, list)
    return built


CODE_REVIEW_READS = [
    "gql-cr-open",
    "gql-cr-pr",
    "gql-cr-pr-stack",
    "cr-codeowners-github",
    "cr-codeowners-root",
    "cr-codeowners-docs",
    "cr-pr-template",
    "cr-viewer-commits",
    "cr-commit-files",
    "cr-path-commits",
    "cr-commit-pulls",
]


def test_every_code_review_operation_is_a_read() -> None:
    assert all(not ops.OPS[name].writes for name in CODE_REVIEW_READS)


def test_the_open_sweep_walks_every_page_of_the_policy_repo(policy: config.Config) -> None:
    argv = _argv(policy, "gql-cr-open")
    assert argv[:5] == ["gh", "api", "graphql", "--paginate", "--slurp"]
    assert "owner=acme" in argv and "repo=product" in argv


def test_the_single_pr_read_is_not_paginated(policy: config.Config) -> None:
    argv = _argv(policy, "gql-cr-pr", "42")
    assert "--paginate" not in argv and "number=42" in argv


@pytest.mark.parametrize(
    ("name", "path"),
    [
        ("cr-codeowners-github", ".github/CODEOWNERS"),
        ("cr-codeowners-root", "CODEOWNERS"),
        ("cr-codeowners-docs", "docs/CODEOWNERS"),
        ("cr-pr-template", ".github/PULL_REQUEST_TEMPLATE.md"),
    ],
)
def test_fixed_paths_stay_under_the_upstream_repo(policy: config.Config, name: str, path: str) -> None:
    assert _argv(policy, name)[2] == f"repos/acme/product/contents/{path}"


def test_viewer_commits_validate_every_parameter(policy: config.Config) -> None:
    argv = _argv(policy, "cr-viewer-commits", "alice", "2026-09-01", "main")
    assert (
        argv[2] == "repos/acme/product/commits?author=alice&since=2026-09-01T00:00:00Z&sha=main&per_page=100"
    )
    for bad in (
        ("alice&x=1", "2026-09-01", "main"),
        ("alice", "yesterday", "main"),
        ("alice", "2026-09-01", "../x"),
    ):
        with pytest.raises(ops.ParamError):
            _argv(policy, "cr-viewer-commits", *bad)


def test_path_commits_refuse_traversal(policy: config.Config) -> None:
    assert _argv(policy, "cr-path-commits", "scheduler/job.py")[6] == "path=scheduler/job.py"
    with pytest.raises(ops.ParamError):
        _argv(policy, "cr-path-commits", "../etc/passwd")


def test_commit_reads_take_a_hash(policy: config.Config) -> None:
    assert _argv(policy, "cr-commit-files", "abc1234")[2] == "repos/acme/product/commits/abc1234"
    assert _argv(policy, "cr-commit-pulls", "abc1234")[2] == "repos/acme/product/commits/abc1234/pulls"
    with pytest.raises(ops.ParamError):
        _argv(policy, "cr-commit-files", "main;rm")
