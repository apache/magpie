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

#: A named GraphQL query. Narrow by construction: the name is only ever used to
#: look up a file that ships *inside this package*, so it can address nothing
#: else even before the containment check below.
_QUERY_NAME = re.compile(r"^[a-z][a-z0-9-]{0,60}$")

#: Where the allowlisted GraphQL documents live. Shipping them as files inside
#: the package — rather than accepting query text as a parameter — is what keeps
#: the GraphQL surface closed: a caller selects a query, it never supplies one.
QUERIES_DIR = Path(__file__).parent / "queries"


class ParamError(ValueError):
    """Raised when a parameter fails validation."""


def _check(pattern: re.Pattern[str], value: str, what: str) -> str:
    if not pattern.match(value):
        raise ParamError(f"invalid {what}: {value!r}")
    return value


def number(value: str) -> str:
    return _check(_NUMBER, value, "number")


def ref(value: str) -> str:
    # Refs are interpolated into API paths (`compare`, `repo-file`, `tags`,
    # `repo-tree`), so a ref containing `..` could walk out of the
    # policy-pinned repository once a client normalises the URL — defeating
    # "the repo is not addressable". Git itself forbids `..` in ref names, so
    # refusing it here costs nothing legitimate.
    if ".." in value:
        raise ParamError(f"path traversal in git ref: {value!r}")
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


def query_name(value: str) -> str:
    """
    Resolve a named GraphQL query to the document shipped with this package.

    ``gh api graphql`` normally takes the query as text, which is precisely the
    unbounded surface this catalogue exists to remove. Instead the caller names
    one of the documents in :data:`QUERIES_DIR` and the dispatcher supplies the
    text. Adding a query is a reviewed change to this package, exactly like
    adding an operation.
    """
    _check(_QUERY_NAME, value, "query name")
    path = (QUERIES_DIR / f"{value}.graphql").resolve()
    # Belt and braces: the name pattern already forbids separators and dots, so
    # this cannot trigger — but the containment check is cheap and the cost of
    # being wrong here is reading an arbitrary file.
    if QUERIES_DIR.resolve() not in path.parents:
        raise ParamError(f"query {value!r} resolves outside the query directory")
    if not path.is_file():
        known = ", ".join(sorted(q.stem for q in QUERIES_DIR.glob("*.graphql"))) or "(none)"
        raise ParamError(f"unknown query: {value!r}; available: {known}")
    return str(path)


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


def _owner_name(repo: str) -> tuple[str, str]:
    """Split ``owner/name``. The value comes from policy, validated on load."""
    owner, _, name = repo.partition("/")
    return owner, name


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


# ---- pull-request family ---------------------------------------------------
#
# The catalogue above is issue-shaped because the security lifecycle is where
# the sweep volume first showed up. PR management makes the same shape of many
# small forge writes, so it gets the same treatment.
#
# One operation is deliberately absent: there is no `pr-merge`. Merging is the
# framework's deliberately-deferred Agentic Autonomous mode — `quick-merge`
# prints a merge command for the maintainer to run rather than merging itself —
# and adding a vetted merge op would quietly hand the agent the one capability
# the surrounding design withholds. Widening the catalogue must not widen the
# posture.

_register(
    Op(
        name="pr-list",
        params=("state",),
        summary="List upstream PRs in a given state.",
        enums={"state": "pr_states"},
        build=lambda cfg, state: [
            "gh",
            "pr",
            "list",
            "--repo",
            _upstream(cfg),
            "--state",
            state,
            "--limit",
            "1000",
            "--json",
            "number,title,state,isDraft,author,labels,milestone,updatedAt,"
            "createdAt,reviewDecision,mergeable,headRefName,baseRefName",
        ],
    )
)

_register(
    Op(
        name="pr-diff",
        params=("number",),
        summary="Read one upstream PR's diff.",
        build=lambda cfg, number: ["gh", "pr", "diff", number, "--repo", _upstream(cfg)],
    )
)

_register(
    Op(
        name="pr-comments",
        params=("number",),
        summary="Read every issue-level comment on one upstream PR.",
        build=lambda cfg, number: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/issues/{number}/comments",
            "--paginate",
        ],
    )
)

_register(
    Op(
        name="pr-reviews",
        params=("number",),
        summary="Read the submitted reviews on one upstream PR.",
        build=lambda cfg, number: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/pulls/{number}/reviews",
            "--paginate",
        ],
    )
)

_register(
    Op(
        name="pr-comment",
        params=("number", "body"),
        writes=True,
        summary="Post a comment on an upstream PR from a body file.",
        body_files=("body",),
        build=lambda cfg, number, body: [
            "gh",
            "pr",
            "comment",
            number,
            "--repo",
            _upstream(cfg),
            "--body-file",
            body,
        ],
    )
)

_register(
    Op(
        name="pr-add-label",
        params=("number", "label"),
        writes=True,
        summary="Add a configured label to an upstream PR.",
        enums={"label": "upstream_labels"},
        build=lambda cfg, number, label: [
            "gh",
            "pr",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--add-label",
            label,
        ],
    )
)

_register(
    Op(
        name="pr-remove-label",
        params=("number", "label"),
        writes=True,
        summary="Remove a configured label from an upstream PR.",
        enums={"label": "upstream_labels"},
        build=lambda cfg, number, label: [
            "gh",
            "pr",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--remove-label",
            label,
        ],
    )
)

_register(
    Op(
        name="pr-set-milestone",
        params=("number", "milestone"),
        writes=True,
        summary="Set a configured milestone on an upstream PR.",
        enums={"milestone": "milestones"},
        build=lambda cfg, number, milestone: [
            "gh",
            "pr",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--milestone",
            milestone,
        ],
    )
)

_register(
    Op(
        name="pr-add-assignee",
        params=("number", "login"),
        writes=True,
        summary="Assign a configured user to an upstream PR.",
        enums={"login": "assignees"},
        build=lambda cfg, number, login: [
            "gh",
            "pr",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--add-assignee",
            login,
        ],
    )
)

_register(
    Op(
        name="pr-request-reviewer",
        params=("number", "login"),
        writes=True,
        summary="Request a review from a configured user on an upstream PR.",
        enums={"login": "assignees"},
        build=lambda cfg, number, login: [
            "gh",
            "pr",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--add-reviewer",
            login,
        ],
    )
)

_register(
    Op(
        name="pr-review-approve",
        params=("number", "body"),
        writes=True,
        summary="Submit an approving review on an upstream PR from a body file.",
        body_files=("body",),
        build=lambda cfg, number, body: [
            "gh",
            "pr",
            "review",
            number,
            "--repo",
            _upstream(cfg),
            "--approve",
            "--body-file",
            body,
        ],
    )
)

_register(
    Op(
        name="pr-review-request-changes",
        params=("number", "body"),
        writes=True,
        summary="Submit a request-changes review on an upstream PR from a body file.",
        body_files=("body",),
        build=lambda cfg, number, body: [
            "gh",
            "pr",
            "review",
            number,
            "--repo",
            _upstream(cfg),
            "--request-changes",
            "--body-file",
            body,
        ],
    )
)

_register(
    Op(
        name="pr-review-comment",
        params=("number", "body"),
        writes=True,
        summary="Submit a non-blocking review comment on an upstream PR from a body file.",
        body_files=("body",),
        build=lambda cfg, number, body: [
            "gh",
            "pr",
            "review",
            number,
            "--repo",
            _upstream(cfg),
            "--comment",
            "--body-file",
            body,
        ],
    )
)

_register(
    Op(
        name="pr-ready",
        params=("number",),
        writes=True,
        summary="Mark an upstream PR ready for review.",
        build=lambda cfg, number: ["gh", "pr", "ready", number, "--repo", _upstream(cfg)],
    )
)

_register(
    Op(
        name="pr-draft",
        params=("number",),
        writes=True,
        summary="Convert an upstream PR back to draft (triage's 'not ready' disposition).",
        build=lambda cfg, number: [
            "gh",
            "pr",
            "ready",
            number,
            "--repo",
            _upstream(cfg),
            "--undo",
        ],
    )
)

_register(
    Op(
        name="pr-close",
        params=("number",),
        writes=True,
        summary="Close an upstream PR without merging.",
        build=lambda cfg, number: ["gh", "pr", "close", number, "--repo", _upstream(cfg)],
    )
)

_register(
    Op(
        name="pr-update-branch",
        params=("number",),
        writes=True,
        summary="Update an upstream PR's branch from its base.",
        build=lambda cfg, number: [
            "gh",
            "pr",
            "update-branch",
            number,
            "--repo",
            _upstream(cfg),
        ],
    )
)

_register(
    Op(
        name="run-rerun-failed",
        params=("run_id",),
        writes=True,
        summary="Re-run the failed jobs of one upstream workflow run.",
        build=lambda cfg, run_id: [
            "gh",
            "run",
            "rerun",
            run_id,
            "--repo",
            _upstream(cfg),
            "--failed",
        ],
    )
)

_register(
    Op(
        name="workflow-approve",
        params=("run_id",),
        writes=True,
        summary="Approve a pending first-time-contributor workflow run.",
        build=lambda cfg, run_id: [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{_upstream(cfg)}/actions/runs/{run_id}/approve",
        ],
    )
)


# ---- upstream-issue family -------------------------------------------------
#
# The `issue-*` operations above address the *tracker* — the private repository
# the security lifecycle runs in. The issue family works on the project's own
# public issues, which is a different repository and therefore a different set
# of operations: `repo-` here means upstream, matching `repo-file`.
#
# Two shapes the family uses are deliberately absent:
#
#   * `gh search issues` — the search query is free text with no fixed shape, so
#     wrapping it would re-introduce the unbounded surface the catalogue exists
#     to remove.
#   * `gh issue create` / `gh pr create` — `gh` has `--body-file` but no
#     `--title-file`, so a title could only arrive as a free-text parameter.
#     Creation is also a genuinely novel action, which the spec's non-goals
#     already say keeps its confirmation.
#
# Both keep their `ask` rule. The catalogue covers the sweep, not everything.

_register(
    Op(
        name="repo-issue-view",
        params=("number",),
        summary="Read one upstream issue as JSON.",
        build=lambda cfg, number: [
            "gh",
            "issue",
            "view",
            number,
            "--repo",
            _upstream(cfg),
            "--json",
            "number,title,state,body,labels,milestone,assignees,author,url,"
            "createdAt,updatedAt,closedAt,comments",
        ],
    )
)

_register(
    Op(
        name="repo-issue-list",
        params=("state",),
        summary="List upstream issues in a given state.",
        enums={"state": "issue_states"},
        build=lambda cfg, state: [
            "gh",
            "issue",
            "list",
            "--repo",
            _upstream(cfg),
            "--state",
            state,
            "--limit",
            "1000",
            "--json",
            "number,title,state,labels,milestone,assignees,author,createdAt,updatedAt,closedAt",
        ],
    )
)

_register(
    Op(
        name="repo-issue-comments",
        params=("number",),
        summary="Read every comment on one upstream issue.",
        build=lambda cfg, number: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/issues/{number}/comments",
            "--paginate",
        ],
    )
)

_register(
    Op(
        name="repo-issue-comment",
        params=("number", "body"),
        writes=True,
        summary="Post a comment on an upstream issue from a body file.",
        body_files=("body",),
        build=lambda cfg, number, body: [
            "gh",
            "issue",
            "comment",
            number,
            "--repo",
            _upstream(cfg),
            "--body-file",
            body,
        ],
    )
)

_register(
    Op(
        name="repo-issue-add-label",
        params=("number", "label"),
        writes=True,
        summary="Add a configured label to an upstream issue.",
        enums={"label": "upstream_labels"},
        build=lambda cfg, number, label: [
            "gh",
            "issue",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--add-label",
            label,
        ],
    )
)

_register(
    Op(
        name="repo-issue-remove-label",
        params=("number", "label"),
        writes=True,
        summary="Remove a configured label from an upstream issue.",
        enums={"label": "upstream_labels"},
        build=lambda cfg, number, label: [
            "gh",
            "issue",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--remove-label",
            label,
        ],
    )
)

_register(
    Op(
        name="repo-issue-set-milestone",
        params=("number", "milestone"),
        writes=True,
        summary="Set a configured milestone on an upstream issue.",
        enums={"milestone": "milestones"},
        build=lambda cfg, number, milestone: [
            "gh",
            "issue",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--milestone",
            milestone,
        ],
    )
)

_register(
    Op(
        name="repo-issue-add-assignee",
        params=("number", "login"),
        writes=True,
        summary="Assign a configured user to an upstream issue.",
        enums={"login": "assignees"},
        build=lambda cfg, number, login: [
            "gh",
            "issue",
            "edit",
            number,
            "--repo",
            _upstream(cfg),
            "--add-assignee",
            login,
        ],
    )
)

_register(
    Op(
        name="repo-issue-close",
        params=("number", "reason"),
        writes=True,
        summary="Close an upstream issue with a configured reason.",
        enums={"reason": "close_reasons"},
        build=lambda cfg, number, reason: [
            "gh",
            "issue",
            "close",
            number,
            "--repo",
            _upstream(cfg),
            "--reason",
            reason,
        ],
    )
)

_register(
    Op(
        name="repo-issue-reopen",
        params=("number",),
        writes=True,
        summary="Reopen an upstream issue (the stale-sweep reversal).",
        build=lambda cfg, number: [
            "gh",
            "issue",
            "reopen",
            number,
            "--repo",
            _upstream(cfg),
        ],
    )
)


# ---- repo health, releases, and people -------------------------------------
#
# The remaining families are overwhelmingly *read* surfaces: a licence audit
# walks the tree, a release check reads what is published, a contributor
# assessment reads a public profile. They need few operations, and mentoring
# needs none at all — it works on upstream issues and PRs, which the two
# families above already cover.
#
# What is deliberately absent here is larger than what is present:
#
#   * `gh release create` / `upload` / `edit` / `delete` — publishing and
#     deleting releases. Releases are vote-gated and maintainer-driven in this
#     framework; a vetted delete would hand the agent an irreversible action the
#     surrounding process deliberately keeps in human hands. Same reasoning as
#     the absent `pr-merge`.
#   * `gh search issues` / `prs`, and the GraphQL `search(...)` connection that
#     contributor-growth leans on — the query is free text with no fixed shape.
#   * `gh run download` — writes artifacts to local disk rather than to the
#     forge. That is a different risk class (filesystem paths, archive
#     extraction) and does not belong behind a forge dispatcher.
#   * `gh repo clone` / `fork` / `create` — novel actions, which the spec's
#     non-goals already say keep their confirmation.

_register(
    Op(
        name="repo-view",
        params=(),
        summary="Read upstream repository metadata.",
        build=lambda cfg: [
            "gh",
            "repo",
            "view",
            _upstream(cfg),
            "--json",
            "name,owner,description,defaultBranchRef,licenseInfo,isArchived,"
            "visibility,pushedAt,repositoryTopics",
        ],
    )
)

_register(
    Op(
        name="repo-tree",
        params=("ref",),
        summary="List every upstream path at a ref (the licence/compliance walk).",
        build=lambda cfg, ref: [
            "gh",
            "api",
            f"repos/{_upstream(cfg)}/git/trees/{ref}",
            "-F",
            "recursive=1",
            "--jq",
            ".tree[].path",
        ],
    )
)

_register(
    Op(
        name="run-list",
        params=(),
        summary="List recent upstream workflow runs.",
        build=lambda cfg: [
            "gh",
            "run",
            "list",
            "--repo",
            _upstream(cfg),
            "--limit",
            "100",
            "--json",
            "databaseId,workflowName,headBranch,event,status,conclusion,createdAt",
        ],
    )
)

_register(
    Op(
        name="run-view",
        params=("run_id",),
        summary="Read one upstream workflow run, with its jobs.",
        build=lambda cfg, run_id: [
            "gh",
            "run",
            "view",
            run_id,
            "--repo",
            _upstream(cfg),
            "--json",
            "databaseId,workflowName,headSha,status,conclusion,createdAt,jobs",
        ],
    )
)

_register(
    Op(
        name="release-list",
        params=(),
        summary="List upstream releases.",
        build=lambda cfg: [
            "gh",
            "release",
            "list",
            "--repo",
            _upstream(cfg),
            "--limit",
            "100",
            "--json",
            "tagName,name,isDraft,isPrerelease,publishedAt",
        ],
    )
)

_register(
    Op(
        name="release-view",
        params=("ref",),
        summary="Read one upstream release by tag.",
        build=lambda cfg, ref: [
            "gh",
            "release",
            "view",
            ref,
            "--repo",
            _upstream(cfg),
            "--json",
            "tagName,name,body,isDraft,isPrerelease,publishedAt,assets",
        ],
    )
)

_register(
    Op(
        name="user-profile",
        params=("login",),
        summary="Read one public GitHub profile (contributor assessment).",
        build=lambda cfg, login: ["gh", "api", f"users/{login}"],
    )
)


# ---- allowlisted GraphQL ---------------------------------------------------
#
# `gh api graphql` is the widest surface `gh` offers, and the two calls the PR
# skills actually make are narrow and repeated. Rather than exposing a generic
# escape hatch, each document in QUERIES_DIR is registered as its own operation
# taking only the variables it needs. The query text is never a parameter, and
# owner/name come from policy, so a named query cannot be re-aimed.

#: Query name -> the parameters it accepts, beyond the policy-supplied owner/repo.
GRAPHQL_QUERIES: dict[str, tuple[str, ...]] = {
    "pr-liveness": ("number",),
    "pr-review-threads": ("number",),
}


def _graphql_builder(query: str) -> Callable[..., list[str]]:
    def build(cfg: dict[str, str], **params: str) -> list[str]:
        owner, name = _owner_name(_upstream(cfg))
        argv = [
            "gh",
            "api",
            "graphql",
            "-F",
            f"owner={owner}",
            "-F",
            f"repo={name}",
            "-F",
            f"query=@{query_name(query)}",
        ]
        for key, value in params.items():
            argv += ["-F", f"{key}={value}"]
        return argv

    return build


for _query, _params in GRAPHQL_QUERIES.items():
    _register(
        Op(
            name=f"gql-{_query}",
            params=_params,
            summary=f"Run the allowlisted GraphQL query {_query!r} against the upstream repo.",
            build=_graphql_builder(_query),
        )
    )


def resolve(name: str) -> Op:
    try:
        return OPS[name]
    except KeyError:
        raise ParamError(f"unknown operation: {name!r}") from None
