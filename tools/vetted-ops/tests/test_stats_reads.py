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
"""The pr-management-stats reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from vetted_ops import cli, config, ops

POLICY = """
workspace = '{workspace}'

[repos]
upstream = "acme/product"

[callers]
"pr-management-stats" = ["gql-pr-stats-open", "gql-pr-stats-closed-page", "gql-pr-stats-closed-search"]
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


def test_open_sweep_is_pinned_to_the_policy_repo(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-stats-open")
    assert "--paginate" in argv and "--slurp" in argv
    assert _search(argv) == "repo:acme/product is:pr is:open sort:created-asc"
    assert argv[-1].endswith("pr-stats-open.graphql")


def test_fast_closed_search_takes_a_strict_date(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-stats-closed-search", "2026-03-11")
    assert _search(argv) == "repo:acme/product is:pr -is:open closed:>=2026-03-11 sort:updated-desc"


@pytest.mark.parametrize(
    "bad", ["2026-3-11", "2026-13-01", "2026-03-11 repo:evil/x", "yesterday", "2026-03-32"]
)
def test_fast_closed_search_refuses_anything_but_a_date(policy: config.Config, bad: str) -> None:
    with pytest.raises(ops.ParamError):
        _argv(policy, "gql-pr-stats-closed-search", bad)


def test_closed_page_starts_without_a_cursor(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-stats-closed-page", "start")
    assert "owner=acme" in argv and "repo=product" in argv
    assert not [a for a in argv if a.startswith("cursor=")]


def test_closed_page_passes_an_opaque_cursor(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-stats-closed-page", "Y3Vyc29yOnYyOpK5MjAyNi0wMy0xMQ==")
    assert "cursor=Y3Vyc29yOnYyOpK5MjAyNi0wMy0xMQ==" in argv


@pytest.mark.parametrize("bad", ["abc def", "abc;rm", "a" * 401, "abc$(x)"])
def test_closed_page_refuses_a_cursor_that_is_not_base64(policy: config.Config, bad: str) -> None:
    with pytest.raises(ops.ParamError):
        _argv(policy, "gql-pr-stats-closed-page", bad)


def test_the_stats_reads_are_reads() -> None:
    assert not any(
        ops.OPS[n].writes
        for n in ("gql-pr-stats-open", "gql-pr-stats-closed-page", "gql-pr-stats-closed-search")
    )


def test_each_stats_search_document_has_exactly_one_page_info() -> None:
    for name in ("pr-stats-open", "pr-stats-closed-search", "pr-stats-closed-page"):
        text = (ops.QUERIES_DIR / f"{name}.graphql").read_text()
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        assert code.count("pageInfo") == 1, name
