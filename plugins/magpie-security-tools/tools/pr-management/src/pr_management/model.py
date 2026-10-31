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
"""PR records, normalised from the `TriagePR` GraphQL shape.

The input is what `vetted-op-read --save` wrote: `gh api graphql --paginate
--slurp` output (a list of `{"data": {"search": …}}` pages) for a sweep, or
one `{"data": {"repository": {"pullRequest": …}}}` object for a single PR.
Every field the classification reads is lifted into a plain dataclass here,
so the rules never index raw JSON.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COLLABORATOR_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
FIRST_TIME_ASSOCIATIONS = frozenset({"FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER"})


def parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def _login(node: dict[str, Any] | None) -> str:
    author = (node or {}).get("author") or {}
    return str(author.get("login") or "ghost")


@dataclass(frozen=True)
class Comment:
    author: str
    association: str
    created: dt.datetime | None
    body: str
    url: str | None = None
    #: "issue" for a PR comment, "thread" for a review-thread reply.
    source: str = "issue"


@dataclass(frozen=True)
class Thread:
    resolved: bool
    comments: tuple[Comment, ...]

    @property
    def first(self) -> Comment | None:
        return self.comments[0] if self.comments else None


@dataclass(frozen=True)
class Review:
    state: str
    author: str
    association: str
    submitted: dt.datetime | None
    body: str


@dataclass(frozen=True)
class Context:
    """One status-check context: a CheckRun or a StatusContext."""

    name: str
    kind: str
    conclusion: str | None
    status: str | None
    started: dt.datetime | None
    completed: dt.datetime | None


@dataclass(frozen=True)
class Commit:
    oid: str
    committed: dt.datetime | None
    message: str


@dataclass(frozen=True)
class LabelEvent:
    added: bool
    label: str
    at: dt.datetime | None


@dataclass
class PR:
    number: int
    title: str
    url: str
    node_id: str
    created: dt.datetime | None
    updated: dt.datetime | None
    is_draft: bool
    body: str
    mergeable: str
    base: str
    head_ref: str
    head_sha: str
    additions: int
    deletions: int
    changed_files: int
    author: str
    association: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    commits: tuple[Commit, ...]
    commit_count: int
    head_committed: dt.datetime | None
    rollup_state: str | None
    contexts: tuple[Context, ...]
    contexts_total: int
    threads: tuple[Thread, ...]
    threads_total: int
    reviews: tuple[Review, ...]
    comments: tuple[Comment, ...]
    label_events: tuple[LabelEvent, ...]
    #: Filled in by follow-up reads, when they were needed and supplied.
    rest_failed_checks: list[str] | None = None
    commits_behind: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def short_sha(self) -> str:
        return self.head_sha[:7]

    @property
    def contexts_truncated(self) -> bool:
        return self.contexts_total > len(self.contexts)

    def all_comments(self) -> list[Comment]:
        """Issue comments and review-thread comments together, oldest first."""
        found = [*self.comments, *(c for t in self.threads for c in t.comments)]
        return sorted(found, key=lambda c: c.created or dt.datetime.min.replace(tzinfo=dt.UTC))

    def label_added_at(self, label: str) -> dt.datetime | None:
        """When `label` was last added, if the timeline window shows it."""
        added = [e.at for e in self.label_events if e.added and e.label == label and e.at]
        return max(added) if added else None


def _comment(node: dict[str, Any], source: str) -> Comment:
    return Comment(
        author=_login(node),
        association=str(node.get("authorAssociation") or "NONE"),
        created=parse_time(node.get("createdAt")),
        body=str(node.get("bodyText") or node.get("body") or ""),
        url=node.get("url"),
        source=source,
    )


def _context(node: dict[str, Any]) -> Context:
    if node.get("__typename") == "StatusContext":
        state = node.get("state")
        return Context(
            name=str(node.get("context") or ""),
            kind="StatusContext",
            conclusion=state,
            status="COMPLETED" if state not in (None, "PENDING", "EXPECTED") else state,
            started=parse_time(node.get("createdAt")),
            completed=None,
        )
    return Context(
        name=str(node.get("name") or ""),
        kind="CheckRun",
        conclusion=node.get("conclusion"),
        status=node.get("status"),
        started=parse_time(node.get("startedAt")),
        completed=parse_time(node.get("completedAt")),
    )


def _nodes(connection: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [n for n in ((connection or {}).get("nodes") or []) if n]


def from_node(node: dict[str, Any]) -> PR:
    head_nodes = _nodes(node.get("head"))
    head_commit = (head_nodes[-1].get("commit") if head_nodes else None) or {}
    rollup = head_commit.get("statusCheckRollup") or {}
    contexts_conn = rollup.get("contexts") or {}
    commits_conn = node.get("commits") or {}
    commits = tuple(
        Commit(
            oid=str((n.get("commit") or {}).get("oid") or ""),
            committed=parse_time((n.get("commit") or {}).get("committedDate")),
            message=str((n.get("commit") or {}).get("message") or ""),
        )
        for n in _nodes(commits_conn)
    )
    threads_conn = node.get("reviewThreads") or {}
    events: list[LabelEvent] = []
    for event in _nodes(node.get("timelineItems")):
        kind = event.get("__typename")
        if kind in ("LabeledEvent", "UnlabeledEvent"):
            events.append(
                LabelEvent(
                    added=kind == "LabeledEvent",
                    label=str((event.get("label") or {}).get("name") or ""),
                    at=parse_time(event.get("createdAt")),
                )
            )
    return PR(
        number=int(node["number"]),
        title=str(node.get("title") or ""),
        url=str(node.get("url") or ""),
        node_id=str(node.get("id") or ""),
        created=parse_time(node.get("createdAt")),
        updated=parse_time(node.get("updatedAt")),
        is_draft=bool(node.get("isDraft")),
        body=str(node.get("body") or ""),
        mergeable=str(node.get("mergeable") or "UNKNOWN"),
        base=str(node.get("baseRefName") or ""),
        head_ref=str(node.get("headRefName") or ""),
        head_sha=str(node.get("headRefOid") or head_commit.get("oid") or ""),
        additions=int(node.get("additions") or 0),
        deletions=int(node.get("deletions") or 0),
        changed_files=int(node.get("changedFiles") or 0),
        author=_login(node),
        association=str(node.get("authorAssociation") or "NONE"),
        labels=tuple(str(n.get("name")) for n in _nodes(node.get("labels"))),
        assignees=tuple(str(n.get("login")) for n in _nodes(node.get("assignees"))),
        commits=commits,
        commit_count=int(commits_conn.get("totalCount") or len(commits)),
        head_committed=parse_time(head_commit.get("committedDate")),
        rollup_state=rollup.get("state") if rollup else None,
        contexts=tuple(_context(n) for n in _nodes(contexts_conn)),
        contexts_total=int(contexts_conn.get("totalCount") or len(_nodes(contexts_conn))),
        threads=tuple(
            Thread(
                resolved=bool(t.get("isResolved")),
                comments=tuple(_comment(c, "thread") for c in _nodes(t.get("comments"))),
            )
            for t in _nodes(threads_conn)
        ),
        threads_total=int(threads_conn.get("totalCount") or 0),
        reviews=tuple(
            Review(
                state=str(r.get("state") or ""),
                author=_login(r),
                association=str(r.get("authorAssociation") or "NONE"),
                submitted=parse_time(r.get("submittedAt")),
                body=str(r.get("body") or ""),
            )
            for r in _nodes(node.get("latestReviews"))
        ),
        comments=tuple(_comment(c, "issue") for c in _nodes(node.get("comments"))),
        label_events=tuple(events),
    )


def _pr_nodes(document: Any) -> Iterator[dict[str, Any]]:
    pages = document if isinstance(document, list) else [document]
    for page in pages:
        data = (page or {}).get("data") or {}
        search = data.get("search")
        if search is not None:
            for node in search.get("nodes") or []:
                if node and "number" in node:
                    yield node
            continue
        pr = (data.get("repository") or {}).get("pullRequest")
        if pr:
            yield pr


def load_pages(paths: Iterable[Path]) -> tuple[list[PR], int]:
    """Every PR in the saved pages, deduplicated by number (last page wins), and the page count."""
    seen: dict[int, PR] = {}
    pages = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        pages += len(document) if isinstance(document, list) else 1
        for node in _pr_nodes(document):
            pr = from_node(node)
            seen[pr.number] = pr
    return list(seen.values()), pages
