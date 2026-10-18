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
The pr-stale-sweep reads.

All reads, saved with `--save` so the sweep never passes through the caller's
context. The skill's mutations — the nudge or close-notice comment and the
close — stay confirmed `gh` calls.
"""

from __future__ import annotations

from collections.abc import Callable

from . import ops as _ops
from .ops import Op, _register, _upstream

_ops.GRAPHQL_QUERIES["pr-stale-one"] = ("number",)
_register(
    Op(
        name="gql-pr-stale-one",
        params=("number",),
        summary="One upstream PR in the pr-stale-sweep shape (comment bodies raw, for the nudge marker).",
        build=_ops._graphql_builder("pr-stale-one"),
    )
)

# The sweeps take no owner/repo variables: the builder writes the repository
# into the search string, `repo:<upstream>` first, like the triage sweeps.
_ops.SEARCH_DOCUMENTS = _ops.SEARCH_DOCUMENTS | {"pr-stale-search"}


def _stale_builder(label: bool) -> Callable[..., list[str]]:
    def build(cfg: dict[str, str], **params: str) -> list[str]:
        search = f"repo:{_upstream(cfg)} is:pr is:open draft:false sort:updated-asc"
        if label:
            # A policy enum: it carries no quote of its own.
            search += f' label:"{params["label"]}"'
        return [
            "gh",
            "api",
            "graphql",
            "--paginate",
            "--slurp",
            "-f",
            f"searchQuery={search}",
            "-F",
            f"query=@{_ops.query_name('pr-stale-search')}",
        ]

    return build


_register(
    Op(
        name="gql-pr-stale-open",
        params=(),
        summary="Every open, non-draft upstream PR in the pr-stale-sweep shape (all pages).",
        build=_stale_builder(False),
    )
)

_register(
    Op(
        name="gql-pr-stale-label",
        params=("label",),
        summary="Open, non-draft upstream PRs carrying one configured label, in the pr-stale-sweep shape.",
        enums={"label": "upstream_labels"},
        build=_stale_builder(True),
    )
)
