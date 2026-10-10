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
"""
The pr-management-quick-merge reads.

All reads: the skill's one mutation, the APPROVE review, goes through
`gh pr review` behind the harness's confirmation, and merging is a command the
maintainer runs themselves — there is deliberately no merge operation here.
"""

from __future__ import annotations

from . import ops as _ops
from .ops import Op, _register, _upstream

#: Owner/repo-scoped documents, registered like ops.GRAPHQL_QUERIES.
_QUERIES: dict[str, tuple[str, ...]] = {
    "pr-express-one": ("number",),
    "pr-review-decision": ("number",),
}

for _name, _params in _QUERIES.items():
    _ops.GRAPHQL_QUERIES[_name] = _params
    _register(
        Op(
            name=f"gql-{_name}",
            params=_params,
            summary=f"Run the allowlisted GraphQL query {_name!r} against the upstream repo.",
            build=_ops._graphql_builder(_name),
        )
    )

# The ready-queue sweep takes no owner/repo variables: the builder writes the
# repository into the search string, like the triage sweeps.
_ops.SEARCH_DOCUMENTS = _ops.SEARCH_DOCUMENTS | {"pr-express-ready"}


def _ready_builder(cfg: dict[str, str], label: str) -> list[str]:
    search = f'repo:{_upstream(cfg)} is:pr is:open label:"{label}" sort:updated-asc'
    return [
        "gh",
        "api",
        "graphql",
        "--paginate",
        "--slurp",
        "-f",
        f"searchQuery={search}",
        "-F",
        f"query=@{_ops.query_name('pr-express-ready')}",
    ]


_register(
    Op(
        name="gql-pr-express-ready",
        params=("label",),
        summary="Open upstream PRs carrying one configured label, with their changed files (all pages).",
        enums={"label": "upstream_labels"},
        build=_ready_builder,
    )
)

_register(
    Op(
        name="pr-live-state",
        params=("number",),
        summary="Force and read one upstream PR's live mergeability (REST computes it on demand).",
        build=lambda cfg, number: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/pulls/{number}",
            "--jq",
            "{number: .number, head_sha: .head.sha, mergeable: .mergeable, mergeable_state: .mergeable_state}",
        ],
    )
)
