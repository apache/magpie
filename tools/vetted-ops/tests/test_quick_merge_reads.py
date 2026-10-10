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
"""The pr-management-quick-merge reads."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from vetted_ops import cli, config, ops

POLICY = """
workspace = '{workspace}'

[repos]
upstream = "acme/product"

[values]
upstream_labels = ["ready for maintainer review"]

[callers]
"pr-management-quick-merge" = [
    "gql-pr-express-ready", "gql-pr-express-one", "gql-pr-review-decision", "pr-live-state",
]
"""

NAMES = ("gql-pr-express-ready", "gql-pr-express-one", "gql-pr-review-decision", "pr-live-state")


@pytest.fixture()
def policy(tmp_path: Path) -> config.Config:
    ws = tmp_path / "scratch"
    ws.mkdir(mode=0o700)
    path = tmp_path / "config.toml"
    path.write_text(POLICY.format(workspace=ws))
    return config.load(path)


def _argv(policy: config.Config, name: str, *values: str) -> list[str]:
    op = ops.resolve(name)
    params, _ = cli._validate_params(op, list(values), policy)
    built = cli.build_argv(op, params, policy)
    assert isinstance(built, list)
    return built


def test_every_quick_merge_operation_is_a_read() -> None:
    assert all(name in ops.OPS and not ops.OPS[name].writes for name in NAMES)


def test_no_operation_merges() -> None:
    """quick-merge prints the merge command for the maintainer; it never runs one."""
    assert not [name for name in ops.OPS if "merge" in name]


def test_the_ready_sweep_is_pinned_to_the_policy_repo(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-express-ready", "ready for maintainer review")
    (search,) = [a.removeprefix("searchQuery=") for a in argv if a.startswith("searchQuery=")]
    assert search == 'repo:acme/product is:pr is:open label:"ready for maintainer review" sort:updated-asc'
    assert "--paginate" in argv and "--slurp" in argv


def test_the_ready_sweep_refuses_an_undeclared_label(policy: config.Config) -> None:
    with pytest.raises(ops.ParamError):
        _argv(policy, "gql-pr-express-ready", 'x" repo:evil/x "')


def test_one_pr_reads_use_the_policy_repo(policy: config.Config) -> None:
    for name in ("gql-pr-express-one", "gql-pr-review-decision"):
        argv = _argv(policy, name, "7")
        assert "owner=acme" in argv and "repo=product" in argv and "number=7" in argv
    assert _argv(policy, "pr-live-state", "7")[2] == "repos/acme/product/pulls/7"


def test_merge_state_refuses_a_non_number(policy: config.Config) -> None:
    with pytest.raises(ops.ParamError):
        _argv(policy, "pr-live-state", "7/merge")


def _fragment(name: str) -> str:
    text = (ops.QUERIES_DIR / f"{name}.graphql").read_text()
    match = re.search(r"^fragment TriagePR on PullRequest \{.*", text, flags=re.MULTILINE | re.DOTALL)
    assert match
    return match.group(0)


def test_the_quick_merge_shapes_share_the_triage_fragment() -> None:
    assert _fragment("pr-express-ready") == _fragment("pr-triage-search")
    assert _fragment("pr-express-one") == _fragment("pr-triage-search")


def test_the_ready_document_has_one_page_info() -> None:
    text = (ops.QUERIES_DIR / "pr-express-ready.graphql").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert code.count("pageInfo") == 1
