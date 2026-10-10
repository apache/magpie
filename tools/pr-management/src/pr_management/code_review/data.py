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
"""The saved reads pr-management-code-review computes on, normalised.

* `cr-open.json` — `gql-cr-open`, every open PR (slurped pages).
* `cr-pr-<N>.json` — `gql-cr-pr <N>`, one PR in full.
* `diff-<N>.patch` — `pr-diff <N>`.
* `codeowners.json` — the first of `cr-codeowners-{github,root,docs}` that answered.
* `pr-template.json` — `cr-pr-template`.
* `team-<slug>.txt` — `team-members <slug>`.
* `viewer-commits.json` / `commit-files-<sha>.json` — touching-mine's base-branch source.
* `path-commits-<k>.json` / `commit-pulls-<sha>.json` — reviewer suggestions.
* `permission.txt` — `upstream-permission <viewer>`.
* `liveness-<N>.json` / `stack-<N>.json` — the SHA recheck and the stack probe.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..model import Context, parse_time


def _nodes(connection: Any) -> list[dict[str, Any]]:
    return [n for n in ((connection or {}).get("nodes") or []) if n]


def _login(node: dict[str, Any] | None) -> str:
    return str(((node or {}).get("author") or {}).get("login") or "ghost")


@dataclass
class Review:
    author: str
    state: str
    submitted: dt.datetime | None
    commit: str | None
    body: str = ""
    association: str = "NONE"
    comment_bodies: tuple[str, ...] = ()


@dataclass
class CommitInfo:
    oid: str
    message: str
    authored: dt.datetime | None = None
    #: Author identities: login when linked, else name or email.
    authors: tuple[str, ...] = ()


@dataclass
class PR:
    number: int
    title: str
    url: str
    is_draft: bool
    created: dt.datetime | None
    updated: dt.datetime | None
    head_sha: str
    base: str
    author: str
    association: str
    mergeable: str
    merge_state: str | None
    additions: int
    deletions: int
    changed_files: int
    body: str
    labels: tuple[str, ...]
    requested_users: tuple[str, ...]
    requested_teams: tuple[str, ...]
    files: tuple[str, ...]
    files_total: int
    comments: tuple[tuple[str, str], ...]
    reviews: tuple[Review, ...]
    commits: tuple[CommitInfo, ...]
    threads_total: int
    unresolved_threads: int
    rollup_state: str | None
    contexts: tuple[Context, ...]
    node_id: str | None = None
    thread_details: tuple[dict[str, Any], ...] = ()
    file_details: tuple[dict[str, Any], ...] = ()
    viewer: str | None = None
    viewer_permission: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _contexts(rollup: dict[str, Any]) -> tuple[Context, ...]:
    found: list[Context] = []
    for node in _nodes(rollup.get("contexts")):
        if node.get("__typename") == "StatusContext":
            state = node.get("state")
            found.append(Context(str(node.get("context") or ""), "StatusContext", state, state, None, None))
        else:
            found.append(
                Context(
                    str(node.get("name") or ""),
                    "CheckRun",
                    node.get("conclusion"),
                    node.get("status"),
                    None,
                    None,
                )
            )
    return tuple(found)


def _requests(node: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    users: list[str] = []
    teams: list[str] = []
    for request in _nodes(node.get("reviewRequests")):
        reviewer = request.get("requestedReviewer") or {}
        if reviewer.get("__typename") == "Team":
            org = ((reviewer.get("organization") or {}).get("login")) or ""
            teams.append(f"{org}/{reviewer.get('slug')}" if org else str(reviewer.get("slug")))
        elif reviewer.get("login"):
            users.append(str(reviewer["login"]))
    return tuple(users), tuple(teams)


def _commit_authors(commit: dict[str, Any]) -> tuple[str, ...]:
    found: list[str] = []
    for author in _nodes(commit.get("authors")):
        user = (author.get("user") or {}).get("login")
        found.append(str(user or author.get("name") or author.get("email") or ""))
    return tuple(a for a in found if a)


def from_node(node: dict[str, Any]) -> PR:
    latest = _nodes(node.get("latest"))
    rollup = ((latest[-1].get("commit") if latest else None) or {}).get("statusCheckRollup") or {}
    users, teams = _requests(node)
    threads = _nodes(node.get("reviewThreads"))
    reviews_raw = _nodes(node.get("reviews")) or _nodes(node.get("latestReviews"))
    reviews = tuple(
        Review(
            author=_login(r),
            state=str(r.get("state") or ""),
            submitted=parse_time(r.get("submittedAt")),
            commit=((r.get("commit") or {}).get("oid")),
            body=str(r.get("bodyText") or r.get("body") or ""),
            association=str(r.get("authorAssociation") or "NONE"),
            comment_bodies=tuple(str(c.get("bodyText") or "") for c in _nodes(r.get("comments"))),
        )
        for r in reviews_raw
    )
    commits = tuple(
        CommitInfo(
            oid=str((c.get("commit") or {}).get("oid") or ""),
            message=str((c.get("commit") or {}).get("message") or ""),
            authored=parse_time((c.get("commit") or {}).get("authoredDate")),
            authors=_commit_authors(c.get("commit") or {}),
        )
        for c in _nodes(node.get("commits"))
    )
    files_conn = node.get("files") or {}
    return PR(
        number=int(node["number"]),
        title=str(node.get("title") or ""),
        url=str(node.get("url") or ""),
        is_draft=bool(node.get("isDraft")),
        created=parse_time(node.get("createdAt")),
        updated=parse_time(node.get("updatedAt")),
        head_sha=str(node.get("headRefOid") or ""),
        base=str(node.get("baseRefName") or ""),
        author=_login(node),
        association=str(node.get("authorAssociation") or "NONE"),
        mergeable=str(node.get("mergeable") or "UNKNOWN"),
        merge_state=node.get("mergeStateStatus"),
        additions=int(node.get("additions") or 0),
        deletions=int(node.get("deletions") or 0),
        changed_files=int(node.get("changedFiles") or 0),
        body=str(node.get("body") if node.get("body") is not None else node.get("bodyText") or ""),
        labels=tuple(str(n.get("name")) for n in _nodes(node.get("labels"))),
        requested_users=users,
        requested_teams=teams,
        files=tuple(str(n.get("path")) for n in _nodes(files_conn)),
        files_total=int(files_conn.get("totalCount") or len(_nodes(files_conn))),
        comments=tuple((_login(c), str(c.get("bodyText") or "")) for c in _nodes(node.get("comments"))),
        reviews=reviews,
        commits=commits,
        threads_total=int((node.get("reviewThreads") or {}).get("totalCount") or len(threads)),
        unresolved_threads=sum(1 for t in threads if not t.get("isResolved")),
        rollup_state=rollup.get("state") if rollup else None,
        contexts=_contexts(rollup),
        node_id=node.get("id"),
        thread_details=tuple(threads),
        file_details=tuple(_nodes(files_conn)),
    )


def load_open(path: Path) -> list[PR]:
    """Every PR in the saved `gql-cr-open` pages."""
    document = json.loads(path.read_text(encoding="utf-8"))
    pages = document if isinstance(document, list) else [document]
    seen: dict[int, PR] = {}
    for page in pages:
        repo = ((page or {}).get("data") or {}).get("repository") or {}
        for node in _nodes(repo.get("pullRequests")):
            pr = from_node(node)
            seen[pr.number] = pr
    return list(seen.values())


def load_pr(path: Path) -> PR:
    """One PR from a saved `gql-cr-pr <N>` read."""
    data = json.loads(path.read_text(encoding="utf-8")).get("data") or {}
    repo = data.get("repository") or {}
    pr = from_node(repo.get("pullRequest") or {})
    pr.viewer = (data.get("viewer") or {}).get("login")
    pr.viewer_permission = repo.get("viewerPermission")
    return pr


def decode_content(path: Path | None) -> str | None:
    """A saved contents-API read (`--jq .content`): a JSON string holding base64."""
    if path is None or not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    if not isinstance(value, str):
        return None
    try:
        return base64.b64decode(re.sub(r"\s+", "", value)).decode("utf-8", errors="replace")
    except ValueError:
        return None


def load_lines(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path | None) -> Any:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def slug(path: str) -> str:
    """A repository path as one file-name component, for save names."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", path).strip("._")[:90] or "root"
