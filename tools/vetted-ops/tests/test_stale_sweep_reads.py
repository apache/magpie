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
"""The pr-stale-sweep reads."""

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
upstream_labels = ["kind/feature"]

[callers]
"pr-stale-sweep" = ["gql-pr-stale-open", "gql-pr-stale-label", "gql-pr-stale-one"]
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


def _search(argv: list[str]) -> str:
    (value,) = [a for a in argv if a.startswith("searchQuery=")]
    return value.removeprefix("searchQuery=")


def test_open_sweep_is_pinned_to_the_policy_repo_and_excludes_drafts(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-stale-open")
    assert "--paginate" in argv and "--slurp" in argv
    assert _search(argv) == "repo:acme/product is:pr is:open draft:false sort:updated-asc"


def test_label_sweep_takes_a_policy_label_only(policy: config.Config) -> None:
    assert _search(_argv(policy, "gql-pr-stale-label", "kind/feature")).endswith(' label:"kind/feature"')
    with pytest.raises(ops.ParamError):
        _argv(policy, "gql-pr-stale-label", 'x" repo:evil/repo "')


def test_one_pr_uses_the_policy_owner_and_name(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-stale-one", "42")
    assert "owner=acme" in argv and "repo=product" in argv and "number=42" in argv


def test_the_stale_reads_are_reads() -> None:
    assert not any(ops.OPS[n].writes for n in ("gql-pr-stale-open", "gql-pr-stale-label", "gql-pr-stale-one"))


def _fragment(name: str) -> str:
    text = (ops.QUERIES_DIR / f"{name}.graphql").read_text()
    match = re.search(r"^fragment StalePR on PullRequest \{.*", text, flags=re.MULTILINE | re.DOTALL)
    assert match
    return match.group(0)


def test_the_search_and_single_pr_shapes_are_one_fragment() -> None:
    assert _fragment("pr-stale-search") == _fragment("pr-stale-one")


def test_comments_carry_the_raw_body_for_the_nudge_marker() -> None:
    frag = _fragment("pr-stale-one")
    comments = frag[frag.index("comments(last: 20)") :]
    assert "createdAt body bodyText" in comments.splitlines()[1]


def test_the_search_document_has_exactly_one_page_info() -> None:
    text = (ops.QUERIES_DIR / "pr-stale-search.graphql").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert code.count("pageInfo") == 1 and "$endCursor" in code
