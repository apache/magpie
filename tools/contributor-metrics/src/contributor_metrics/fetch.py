# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""GitHub fetch through gh. Comment bodies never leave this module."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from contributor_metrics.model import Item, Kind

LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAINTAINER_ASSOC = {"OWNER", "MEMBER", "COLLABORATOR"}
GENERIC_PHRASES = (
    "ai-generated",
    "ai generated",
    "llm",
    "chatgpt",
    "copilot",
    "slop",
    "did you review",
    "review your own",
    "did you run",
    "unreviewed",
    "hallucinat",
    "does not exist",
    "stop posting",
)
PAGES = 3
AUTHORED_BUDGET, REVIEW_BUDGET, THREAD_BUDGET = 50, 20, 100
SUBSTANTIVE_BODY_CHARS, SUBSTANTIVE_LINE_COMMENTS = 100, 1
RETRYABLE = ("rate limit", "secondary rate", "abuse", "http 502", "http 503", "timed out", "timeout")
MAX_TRIES = 6

SEARCH_GQL = """query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    issueCount pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest { number url state merged mergedAt createdAt updatedAt labels(first: 20) { nodes { name } } }
      ... on Issue { number url state createdAt updatedAt labels(first: 20) { nodes { name } } }
    }
  }
}"""

CONTRIB_GQL = """query($login: String!, $from: DateTime!, $to: DateTime!, $cursor: String) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      pullRequestReviewContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner }
        contributions(first: 100, after: $cursor) {
          totalCount pageInfo { hasNextPage endCursor }
          nodes {
            occurredAt
            pullRequestReview { url body comments { totalCount } }
            pullRequest { url number labels(first: 20) { nodes { name } } }
          }
        }
      }
    }
  }
}"""

CONVO_GQL = """query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issueOrPullRequest(number: $number) {
      ... on PullRequest {
        comments(first: 100) { nodes { url author { login } authorAssociation body createdAt } }
        reviews(first: 50) { nodes { url author { login } authorAssociation body createdAt comments { totalCount } } }
      }
      ... on Issue { comments(first: 100) { nodes { url author { login } authorAssociation body createdAt } } }
    }
  }
}"""


class InvalidLogin(ValueError):
    pass


class InvalidRepo(ValueError):
    pass


class GhError(RuntimeError):
    pass


def _gh_graphql(gql: str, *, search: str | None = None, **fields: str | int | None) -> dict[str, Any]:
    """Run one GraphQL call, retrying rate-limit and transient errors with backoff.

    The search string goes through a tempfile (`-F q=@file`), never the command line.
    A field whose value is None or "" is omitted, so an unset cursor is sent as null.
    """
    cmd = ["gh", "api", "graphql", "-f", f"query={gql}"]
    tmp = None
    if search is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(search)
            tmp = fh.name
        cmd += ["-F", f"q=@{tmp}"]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        cmd += ["-F", f"{key}={value}"] if isinstance(value, int) else ["-f", f"{key}={value}"]
    try:
        delay = 2.0
        for attempt in range(MAX_TRIES):
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                data: dict[str, Any] = json.loads(result.stdout)
                return data
            err = result.stderr.lower()
            if attempt < MAX_TRIES - 1 and any(t in err for t in RETRYABLE):
                time.sleep(delay)
                delay = min(delay * 2, 120.0)
                continue
            raise GhError(result.stderr.strip())
        raise GhError("gh failed after retries")
    finally:
        if tmp:
            Path(tmp).unlink(missing_ok=True)


def _search(q: str) -> tuple[list[dict[str, Any]], bool]:
    nodes: list[dict[str, Any]] = []
    cursor: str | None = None
    total = 0
    for _ in range(PAGES):
        data = _gh_graphql(SEARCH_GQL, search=q, cursor=cursor)["data"]["search"]
        total = data["issueCount"]
        nodes += [n for n in data["nodes"] if n]
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return nodes, total > len(nodes)


def _labels(node: dict[str, Any]) -> tuple[str, ...]:
    return tuple(n["name"] for n in (node.get("labels") or {}).get("nodes", []))


def _authored(kind: Kind, node: dict[str, Any], end: str) -> Item:
    merged_at = (node.get("mergedAt") or "")[:10]
    merged = bool(node.get("merged")) and bool(merged_at) and merged_at <= end
    return Item(
        id=f"{kind}-{node['number']}",
        kind=kind,
        url=node["url"],
        thread=node["url"],
        created_at=node["createdAt"][:10],
        merged=merged,
        closed_unmerged=node.get("state") == "CLOSED" and not node.get("merged"),
        areas=_labels(node),
    )


def _chunks(since: str, end: str) -> list[tuple[str, str]]:
    """contributionsCollection accepts at most one year per call."""
    s, e = date.fromisoformat(since), date.fromisoformat(end)
    out = []
    while s <= e:
        stop = min(e, s + timedelta(days=364))
        out.append((s.isoformat(), stop.isoformat()))
        s = stop + timedelta(days=1)
    return out


def _reviews(
    repo: str,
    login: str,
    since: str,
    end: str,
    body_chars: int = SUBSTANTIVE_BODY_CHARS,
    line_comments: int = SUBSTANTIVE_LINE_COMMENTS,
) -> tuple[list[Item], bool]:
    """One item per reviewed PR, dated by the candidate's first review in the window.

    The PR is substantive when any of those reviews has a body longer than `body_chars`
    characters or at least `line_comments` line comments.
    """
    by_pr: dict[int, dict[str, Any]] = {}
    capped = False
    for frm, to in _chunks(since, end):
        cursor: str | None = None
        for page in range(PAGES):
            data = _gh_graphql(
                CONTRIB_GQL,
                login=login,
                cursor=cursor,
                **{"from": f"{frm}T00:00:00Z", "to": f"{to}T23:59:59Z"},
            )
            groups = data["data"]["user"]["contributionsCollection"][
                "pullRequestReviewContributionsByRepository"
            ]
            group = next(
                (g for g in groups if g["repository"]["nameWithOwner"].lower() == repo.lower()), None
            )
            if group is None:
                break
            conn = group["contributions"]
            for n in conn["nodes"]:
                day = n["occurredAt"][:10]
                if not since <= day <= end:
                    continue
                pr = n["pullRequest"]
                review = n["pullRequestReview"] or {}
                entry = by_pr.setdefault(pr["number"], {"pr": pr, "first": day, "substantive": False})
                entry["first"] = min(entry["first"], day)
                if (
                    len(review.get("body") or "") > body_chars
                    or (review.get("comments") or {}).get("totalCount", 0) >= line_comments
                ):
                    entry["substantive"] = True
            if not conn["pageInfo"]["hasNextPage"]:
                break
            if page == PAGES - 1:
                capped = True
            cursor = conn["pageInfo"]["endCursor"]
    items = [
        Item(
            id=f"review-{number}",
            kind="review",
            url=e["pr"]["url"],
            thread=e["pr"]["url"],
            created_at=e["first"],
            substantive=e["substantive"],
            areas=_labels(e["pr"]),
        )
        for number, e in sorted(by_pr.items())
    ]
    return items, capped


def _convo(repo: str, number: int) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    data = _gh_graphql(CONVO_GQL, owner=owner, repo=name, number=number)
    convo: dict[str, Any] = data["data"]["repository"]["issueOrPullRequest"] or {}
    return convo


def _pushback(convo: dict[str, Any], login: str, phrases: Iterable[str], maintainers: Iterable[str]) -> str:
    """URL of the first maintainer comment containing a pushback phrase — a candidate, not a verdict."""
    wanted = tuple(p.lower() for p in (*GENERIC_PHRASES, *phrases) if p.strip())
    maint = set(maintainers)
    comments = (convo.get("comments") or {}).get("nodes", []) + (convo.get("reviews") or {}).get("nodes", [])
    for c in comments:
        who = (c.get("author") or {}).get("login", "")
        if who == login or who.endswith("[bot]"):
            continue
        if c.get("authorAssociation") not in MAINTAINER_ASSOC and who not in maint:
            continue
        body = (c.get("body") or "").lower()
        if any(p in body for p in wanted):
            return str(c["url"])
    return ""


def _own_comment_day(convo: dict[str, Any], login: str, since: str, end: str) -> str | None:
    days = [
        c["createdAt"][:10]
        for c in (convo.get("comments") or {}).get("nodes", [])
        if (c.get("author") or {}).get("login") == login
        and c.get("createdAt")
        and since <= c["createdAt"][:10] <= end
    ]
    return min(days) if days else None


def fetch_items(
    repo: str,
    login: str,
    *,
    since: str,
    end: str,
    phrases: Iterable[str],
    maintainers: Iterable[str],
    substantive_body_chars: int = SUBSTANTIVE_BODY_CHARS,
    substantive_line_comments: int = SUBSTANTIVE_LINE_COMMENTS,
) -> tuple[list[Item], list[str], list[str]]:
    """Fetch the five activity streams inside [since, end].

    Returns the items, the names of streams that hit their cap, and notes for the brief.
    """
    if not REPO_RE.match(repo):
        raise InvalidRepo(repo)
    if not LOGIN_RE.match(login):
        raise InvalidLogin(login)
    phrases, maintainers = tuple(phrases), tuple(maintainers)
    base = f"repo:{repo}"
    caps: list[str] = []
    notes: list[str] = []

    items: list[Item] = []
    authored_streams: tuple[tuple[str, str, Kind], ...] = (
        ("prs_opened", f"{base} type:pr author:{login} created:{since}..{end}", "pr"),
        ("issues_filed", f"{base} type:issue author:{login} created:{since}..{end}", "issue"),
    )
    for name, q, kind in authored_streams:
        nodes, capped = _search(q)
        if capped:
            caps.append(name)
        items += [_authored(kind, n, end) for n in nodes]

    reviews, capped = _reviews(repo, login, since, end, substantive_body_chars, substantive_line_comments)
    if capped:
        caps.append("reviews_total")
    items += reviews

    thread_nodes: dict[Kind, list[dict[str, Any]]] = {}
    thread_streams: tuple[tuple[str, str, Kind], ...] = (
        (
            "issues_triaged",
            f"{base} type:issue commenter:{login} -author:{login} created:<={end} updated:>={since}",
            "triage",
        ),
        ("threads_commented", f"{base} commenter:{login} created:<={end} updated:>={since}", "thread"),
    )
    for name, q, kind in thread_streams:
        nodes, capped = _search(q)
        if capped:
            caps.append(name)
        thread_nodes[kind] = sorted(nodes, key=lambda n: n.get("updatedAt") or n["createdAt"], reverse=True)

    convos: dict[int, dict[str, Any]] = {}

    def convo(number: int) -> dict[str, Any]:
        if number not in convos:
            convos[number] = _convo(repo, number)
        return convos[number]

    def recent(kinds: tuple[str, ...], n: int) -> set[str]:
        chosen = sorted((i for i in items if i.kind in kinds), key=lambda i: i.created_at, reverse=True)[:n]
        return {i.id for i in chosen}

    inspect = recent(("pr", "issue"), AUTHORED_BUDGET) | recent(("review",), REVIEW_BUDGET)
    out: list[Item] = []
    for i in items:
        if i.id in inspect:
            number = int(i.url.rstrip("/").rsplit("/", 1)[1])
            i = Item.from_json(
                {**i.to_json(), "pushback_candidate": _pushback(convo(number), login, phrases, maintainers)}
            )
        out.append(i)

    for kind, nodes in thread_nodes.items():
        unverified = 0
        for rank, n in enumerate(nodes):
            if rank < THREAD_BUDGET:
                c = convo(n["number"])
                day = _own_comment_day(c, login, since, end)
                if day is None:
                    continue
                out.append(
                    Item(
                        id=f"{kind}-{n['number']}",
                        kind=kind,
                        url=n["url"],
                        thread=n["url"],
                        created_at=day,
                        areas=_labels(n),
                        pushback_candidate=_pushback(c, login, phrases, maintainers),
                    )
                )
            else:
                unverified += 1
                day = min((n.get("updatedAt") or n["createdAt"])[:10], end)
                out.append(
                    Item(
                        id=f"{kind}-{n['number']}",
                        kind=kind,
                        url=n["url"],
                        thread=n["url"],
                        created_at=day,
                        areas=_labels(n),
                    )
                )
        if unverified:
            notes.append(
                f"{kind}: {unverified} threads beyond the {THREAD_BUDGET} most recent were counted without checking the date of the candidate's own comment"
            )
    return out, caps, notes
