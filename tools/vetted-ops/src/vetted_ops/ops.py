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
The fixed operation catalogue.

Every operation is a *closed* shape: a name, a list of typed parameters, and a
builder that returns an **argv list**. No operation accepts pass-through
arguments, and no builder ever produces a shell string — the argv list is handed
to ``subprocess.run`` without a shell, so no amount of hostile content in a
parameter can become a command.

Adding an operation here is the only way to widen the surface, and doing so is a
reviewed code change rather than a runtime decision.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Parameter types
# --------------------------------------------------------------------------

#: Issue / PR / comment numbers. Bounded length so a parameter cannot smuggle a
#: long payload even in a numeric-looking field.
_NUMBER = re.compile(r"^[0-9]{1,10}$")

#: A git ref or tag name. Deliberately narrow: no whitespace, no shell
#: metacharacters, no leading dash.
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")

#: A repo-relative path used for content probes. No absolute paths, no `..`.
_REPO_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,300}$")

#: A GitHub login.
_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

#: A GHSA identifier.
_GHSA = re.compile(r"^GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}$")

#: A ProjectV2 node id, as returned by the GraphQL API.
_NODE_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


class ParamError(ValueError):
    """Raised when a parameter fails validation."""


def _check(pattern: re.Pattern[str], value: str, what: str) -> str:
    if not pattern.match(value):
        raise ParamError(f"invalid {what}: {value!r}")
    return value


def number(value: str) -> str:
    return _check(_NUMBER, value, "number")


def ref(value: str) -> str:
    return _check(_REF, value, "git ref")


def repo_path(value: str) -> str:
    if ".." in value:
        raise ParamError(f"path traversal in repo path: {value!r}")
    return _check(_REPO_PATH, value, "repo path")


def login(value: str) -> str:
    return _check(_LOGIN, value, "login")


def ghsa(value: str) -> str:
    return _check(_GHSA, value, "GHSA id")


def node_id(value: str) -> str:
    return _check(_NODE_ID, value, "node id")


def body_file(value: str, *, workspace: Path) -> str:
    """
    Validate a path holding body text.

    Content is passed to ``gh`` by *file reference*, never interpolated, so the
    body may contain anything at all — backticks, ``$(…)``, newlines, NUL-free
    binary. What is constrained is *which* file may be read: it must resolve
    inside the caller's declared workspace, so an operation cannot be talked into
    publishing ``~/.ssh/id_rsa`` or a credential file.
    """
    path = Path(value).expanduser().resolve()
    root = workspace.expanduser().resolve()
    if not path.is_file():
        raise ParamError(f"body file does not exist: {value!r}")
    if root not in path.parents and path != root:
        raise ParamError(f"body file must live under the workspace {str(root)!r}: {value!r}")
    return str(path)


def enum(allowed: Sequence[str]) -> Callable[[str], str]:
    """Build a validator accepting only one of ``allowed``."""
    permitted = tuple(allowed)

    def _validate(value: str) -> str:
        if value not in permitted:
            raise ParamError(f"value {value!r} is not one of the configured values: {list(permitted)}")
        return value

    return _validate


# --------------------------------------------------------------------------
# Operation catalogue
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Op:
    """One fixed operation."""

    name: str
    #: Parameter names, in positional order.
    params: tuple[str, ...]
    #: Builds the argv. Receives resolved config plus validated parameters.
    build: Callable[..., list[str]]
    #: True when the operation changes state visible outside the machine.
    writes: bool = False
    #: Human-readable one-liner for `list-ops`.
    summary: str = ""
    #: Parameters that must be one of a configured enum, mapped to the config key
    #: holding the permitted values (e.g. "labels", "milestones").
    enums: dict[str, str] = field(default_factory=dict)
    #: Parameters holding a path to body content.
    body_files: tuple[str, ...] = ()


def _tracker(cfg: dict[str, str]) -> str:
    return cfg["tracker_repo"]


def _upstream(cfg: dict[str, str]) -> str:
    return cfg["upstream_repo"]


# ---- reads ----------------------------------------------------------------

OPS: dict[str, Op] = {}


def _register(op: Op) -> None:
    OPS[op.name] = op


_register(
    Op(
        name="issue-view",
        params=("number",),
        summary="Read one tracker issue as JSON.",
        build=lambda cfg, number: [
            "gh",
            "issue",
            "view",
            number,
            "--repo",
            _tracker(cfg),
            "--json",
            "number,title,state,body,labels,milestone,assignees,author,url,createdAt,closedAt",
        ],
    )
)

_register(
    Op(
        name="issue-list",
        params=("state",),
        summary="List tracker issues in a given state.",
        enums={"state": "issue_states"},
        build=lambda cfg, state: [
            "gh",
            "issue",
            "list",
            "--repo",
            _tracker(cfg),
            "--state",
            state,
            "--limit",
            "1000",
            "--json",
            "number,title,state,labels,milestone,assignees,updatedAt,closedAt",
        ],
    )
)

_register(
    Op(
        name="issue-comments",
        params=("number",),
        summary="Read every comment on one tracker issue.",
        build=lambda cfg, number: [
            "gh",
            "api",
            f"repos/{_tracker(cfg)}/issues/{number}/comments",
            "--paginate",
        ],
    )
)

_register(
    Op(
        name="label-list",
        params=(),
        summary="List the tracker's labels.",
        build=lambda cfg: [
            "gh",
            "label",
            "list",
            "--repo",
            _tracker(cfg),
            "--limit",
            "200",
            "--json",
            "name",
        ],
    )
)

_register(
    Op(
        name="milestone-list",
        params=(),
        summary="List the tracker's milestones.",
        build=lambda cfg: ["gh", "api", f"repos/{_tracker(cfg)}/milestones", "--paginate"],
    )
)

_register(
    Op(
        name="collaborators",
        params=(),
        summary="List tracker collaborators (the security-team roster).",
        build=lambda cfg: [
            "gh",
            "api",
            f"repos/{_tracker(cfg)}/collaborators",
            "--paginate",
            "--jq",
            ".[].login",
        ],
    )
)

_register(
    Op(
        name="pr-view",
        params=("number",),
        summary="Read one upstream PR as JSON.",
        build=lambda cfg, number: [
            "gh",
            "pr",
            "view",
            number,
            "--repo",
            _upstream(cfg),
            "--json",
            "number,title,state,isDraft,mergedAt,mergeCommit,baseRefName,headRefName,"
            "author,url,files,labels,milestone,reviewDecision,mergeable,mergeStateStatus",
        ],
    )
)

_register(
    Op(
        name="pr-checks",
        params=("number",),
        summary="Read the CI rollup for one upstream PR.",
        build=lambda cfg, number: [
            "gh",
            "pr",
            "view",
            number,
            "--repo",
            _upstream(cfg),
            "--json",
            "statusCheckRollup",
        ],
    )
)

_register(
    Op(
        name="repo-file",
        params=("path", "ref"),
        summary="Fetch one upstream file at a ref (the content probe).",
        build=lambda cfg, path, ref: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/contents/{path}",
            "-F",
            f"ref={ref}",
            "--jq",
            ".content",
        ],
    )
)

_register(
    Op(
        name="compare",
        params=("base", "head"),
        summary="Compare two upstream refs (ancestry check).",
        build=lambda cfg, base, head: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/compare/{base}...{head}",
            "--jq",
            ".status",
        ],
    )
)

_register(
    Op(
        name="tags",
        params=("prefix",),
        summary="List upstream tags under a prefix (release detection).",
        build=lambda cfg, prefix: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/git/matching-refs/tags/{prefix}",
            "--jq",
            ".[].ref",
        ],
    )
)

_register(
    Op(
        name="advisory-view",
        params=("ghsa",),
        summary="Read one upstream GitHub Security Advisory.",
        build=lambda cfg, ghsa: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/security-advisories/{ghsa}",
        ],
    )
)

# ---- writes ---------------------------------------------------------------

_register(
    Op(
        name="issue-add-label",
        params=("number", "label"),
        writes=True,
        summary="Add one configured label to a tracker issue.",
        enums={"label": "labels"},
        build=lambda cfg, number, label: [
            "gh",
            "issue",
            "edit",
            number,
            "--repo",
            _tracker(cfg),
            "--add-label",
            label,
        ],
    )
)

_register(
    Op(
        name="issue-remove-label",
        params=("number", "label"),
        writes=True,
        summary="Remove one configured label from a tracker issue.",
        enums={"label": "labels"},
        build=lambda cfg, number, label: [
            "gh",
            "issue",
            "edit",
            number,
            "--repo",
            _tracker(cfg),
            "--remove-label",
            label,
        ],
    )
)

_register(
    Op(
        name="issue-set-milestone",
        params=("number", "milestone"),
        writes=True,
        summary="Assign a configured milestone to a tracker issue.",
        enums={"milestone": "milestones"},
        build=lambda cfg, number, milestone: [
            "gh",
            "issue",
            "edit",
            number,
            "--repo",
            _tracker(cfg),
            "--milestone",
            milestone,
        ],
    )
)

_register(
    Op(
        name="issue-add-assignee",
        params=("number", "login"),
        writes=True,
        summary="Assign a tracker issue to a roster member.",
        enums={"login": "assignees"},
        build=lambda cfg, number, login: [
            "gh",
            "issue",
            "edit",
            number,
            "--repo",
            _tracker(cfg),
            "--add-assignee",
            login,
        ],
    )
)

_register(
    Op(
        name="issue-comment",
        params=("number", "body"),
        writes=True,
        summary="Post a comment on a tracker issue from a body file.",
        body_files=("body",),
        build=lambda cfg, number, body: [
            "gh",
            "issue",
            "comment",
            number,
            "--repo",
            _tracker(cfg),
            "--body-file",
            body,
        ],
    )
)

_register(
    Op(
        name="issue-close",
        params=("number", "reason"),
        writes=True,
        summary="Close a tracker issue with a configured reason.",
        enums={"reason": "close_reasons"},
        build=lambda cfg, number, reason: [
            "gh",
            "issue",
            "close",
            number,
            "--repo",
            _tracker(cfg),
            "--reason",
            reason,
        ],
    )
)

_register(
    Op(
        name="comment-update",
        params=("comment_id", "body"),
        writes=True,
        summary="Rewrite one existing tracker comment (the rollup upsert).",
        body_files=("body",),
        build=lambda cfg, comment_id, body: [
            "gh",
            "api",
            "-X",
            "PATCH",
            f"repos/{_tracker(cfg)}/issues/comments/{comment_id}",
            "-F",
            f"body=@{body}",
        ],
    )
)

_register(
    Op(
        name="board-set-status",
        params=("item_id", "column"),
        writes=True,
        summary="Move a project-board item to a configured column.",
        enums={"column": "board_columns"},
        build=lambda cfg, item_id, column: [
            "gh",
            "api",
            "graphql",
            "-F",
            f"project={cfg['board_project_id']}",
            "-F",
            f"item={item_id}",
            "-F",
            f"field={cfg['board_status_field_id']}",
            "-F",
            f"option={cfg['board_columns'][column]}",
            "-f",
            "query=mutation($project:ID!,$item:ID!,$field:ID!,$option:String!)"
            "{updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,"
            "fieldId:$field,value:{singleSelectOptionId:$option}}){projectV2Item{id}}}",
        ],
    )
)


def resolve(name: str) -> Op:
    try:
        return OPS[name]
    except KeyError:
        raise ParamError(f"unknown operation: {name!r}") from None
