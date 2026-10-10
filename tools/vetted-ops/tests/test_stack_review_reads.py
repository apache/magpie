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
"""The pr-management-stack-review reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from vetted_ops import cli, config, ops

POLICY = """
workspace = '{workspace}'

[repos]
upstream = "acme/product"

[callers]
"pr-management-stack-review" = ["gql-stack-of-pr", "gql-stack-scan", "gql-pr-by-head", "pr-checks", "pr-comments"]
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


def test_stack_of_pr_is_pinned_to_the_policy_repo(policy: config.Config) -> None:
    argv = _argv(policy, "gql-stack-of-pr", "1001")
    assert "owner=acme" in argv and "repo=product" in argv and "number=1001" in argv
    assert argv[-1].endswith("stack-of-pr.graphql")


def test_stack_scan_reads_every_page(policy: config.Config) -> None:
    argv = _argv(policy, "gql-stack-scan")
    assert argv[:5] == ["gh", "api", "graphql", "--paginate", "--slurp"]


def test_pr_by_head_passes_the_branch_as_a_raw_string(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-by-head", "123")
    assert argv[argv.index("head=123") - 1] == "-f"


@pytest.mark.parametrize("hostile", ["main;rm", "a b", "../x", "-x"])
def test_pr_by_head_refuses_a_hostile_branch(policy: config.Config, hostile: str) -> None:
    with pytest.raises(ops.ParamError):
        _argv(policy, "gql-pr-by-head", hostile)


def test_the_stack_reads_are_reads() -> None:
    assert not any(ops.OPS[n].writes for n in ("gql-stack-of-pr", "gql-stack-scan", "gql-pr-by-head"))


def test_the_scan_document_has_one_page_info() -> None:
    text = (ops.QUERIES_DIR / "stack-scan.graphql").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert code.count("pageInfo") == 1 and "$endCursor" in code
