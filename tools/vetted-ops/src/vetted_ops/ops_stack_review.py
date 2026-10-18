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
The pr-management-stack-review reads.

The stack a member PR belongs to, the open-PR scan that finds a stack by its
number, and the open PRs whose head is one branch (the trunk walk). Every
query names the policy-pinned upstream repository; parameters only select
within it. The per-layer CI rollup and the comment list reuse the existing
`pr-checks` and `pr-comments` operations.
"""

from __future__ import annotations

from .ops import GRAPHQL_QUERIES, Op, _owner_name, _register, _upstream, query_name


def _policy_vars(cfg: dict[str, str]) -> list[str]:
    owner, name = _owner_name(_upstream(cfg))
    return ["-F", f"owner={owner}", "-F", f"repo={name}"]


_register(
    Op(
        name="gql-stack-of-pr",
        params=("number",),
        summary="The stack one upstream PR belongs to, with every entry (stack review, Step 1).",
        build=lambda cfg, number: [
            "gh",
            "api",
            "graphql",
            *_policy_vars(cfg),
            "-F",
            f"number={number}",
            "-F",
            f"query=@{query_name('stack-of-pr')}",
        ],
    )
)

_register(
    Op(
        name="gql-stack-scan",
        params=(),
        summary="Every open upstream PR's stack number, all pages (find a stack by its number).",
        build=lambda cfg: [
            "gh",
            "api",
            "graphql",
            "--paginate",
            "--slurp",
            *_policy_vars(cfg),
            "-F",
            f"query=@{query_name('stack-scan')}",
        ],
    )
)

_register(
    Op(
        name="gql-pr-by-head",
        params=("head",),
        summary="The open upstream PRs whose head is one branch (the stack trunk walk).",
        # `-f`, not `-F`: a branch named `123` or `true` must stay a string.
        build=lambda cfg, head: [
            "gh",
            "api",
            "graphql",
            *_policy_vars(cfg),
            "-f",
            f"head={head}",
            "-F",
            f"query=@{query_name('pr-by-head')}",
        ],
    )
)

# The documents above are registered by their own builders; listing them here
# keeps the catalogue test's "every shipped query is an operation" honest.
GRAPHQL_QUERIES.setdefault("stack-of-pr", ("number",))
GRAPHQL_QUERIES.setdefault("stack-scan", ())
GRAPHQL_QUERIES.setdefault("pr-by-head", ("head",))
