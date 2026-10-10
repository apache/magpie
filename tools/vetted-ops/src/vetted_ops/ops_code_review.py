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
The pr-management-code-review reads.

All reads. Posting a review stays a confirmed `gh pr review` /
`gh api graphql --input` write, run by the maintainer's agent behind the
harness's confirmation; nothing here writes.

The ownership file and the PR template live under `.github/`, which the
generic `repo-file` path validator refuses (no leading dot), so each is its
own operation with a fixed path.
"""

from __future__ import annotations

from collections.abc import Callable

from . import ops as _ops
from .ops import Op, _register, _upstream

#: Owner/repo-scoped documents, registered like ops.GRAPHQL_QUERIES.
_QUERIES: dict[str, tuple[str, ...]] = {
    "cr-open": (),
    "cr-pr": ("number",),
    "cr-pr-stack": ("number",),
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

# The open sweep walks every page of the pullRequests connection.
_ops.PAGINATED_QUERIES = _ops.PAGINATED_QUERIES | {"cr-open"}

#: Fixed-path content reads: operation name -> repository path.
_FIXED_FILES: dict[str, str] = {
    "cr-codeowners-github": ".github/CODEOWNERS",
    "cr-codeowners-root": "CODEOWNERS",
    "cr-codeowners-docs": "docs/CODEOWNERS",
    "cr-pr-template": ".github/PULL_REQUEST_TEMPLATE.md",
}


def _fixed_file_builder(path: str) -> Callable[[dict[str, str]], list[str]]:
    def build(cfg: dict[str, str]) -> list[str]:
        return ["gh", "api", f"repos/{_upstream(cfg)}/contents/{path}", "--jq", ".content"]

    return build


for _name, _path in _FIXED_FILES.items():
    _register(
        Op(
            name=_name,
            params=(),
            summary=f"Fetch the upstream {_path} on the default branch (base64, as the contents API returns it).",
            build=_fixed_file_builder(_path),
        )
    )

_register(
    Op(
        name="cr-viewer-commits",
        params=("login", "date", "ref"),
        summary="Every commit one user authored on one upstream branch since a date (all pages): touching-mine.",
        build=lambda cfg, login, date, ref: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/commits?author={login}&since={date}T00:00:00Z&sha={ref}&per_page=100",
            "--paginate",
            "--slurp",
        ],
    )
)

_register(
    Op(
        name="cr-commit-files",
        params=("commit_hash",),
        summary="The paths one upstream commit changed: touching-mine's base-branch source.",
        build=lambda cfg, commit_hash: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/commits/{commit_hash}",
            "--jq",
            "{sha: .sha, files: [.files[].filename]}",
        ],
    )
)

_register(
    Op(
        name="cr-path-commits",
        params=("path",),
        summary="Who committed to one upstream path recently, with dates: reviewer suggestions.",
        build=lambda cfg, path: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/commits",
            "-X",
            "GET",
            "-F",
            f"path={path}",
            "-F",
            "per_page=30",
            "--jq",
            "[.[] | {login: .author.login, date: .commit.author.date, sha: .sha}]",
        ],
    )
)

_register(
    Op(
        name="cr-commit-pulls",
        params=("commit_hash",),
        summary="The merged upstream PRs one commit belongs to: reviewers of prior changes.",
        build=lambda cfg, commit_hash: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/commits/{commit_hash}/pulls",
            "--jq",
            "[.[] | select(.merged_at != null) | {number: .number, merged_at: .merged_at}]",
        ],
    )
)
