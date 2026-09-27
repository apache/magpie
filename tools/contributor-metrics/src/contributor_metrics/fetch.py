# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""GitHub fetch through gh. Comment bodies never leave this module."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from contributor_metrics.model import Item, Kind

LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
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
PAGES, CONVO_BUDGET = 3, 50

SEARCH_GQL = """query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    issueCount pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest { number url state merged createdAt labels(first: 20) { nodes { name } } }
      ... on Issue { number url state createdAt labels(first: 20) { nodes { name } } }
    }
  }
}"""

CONVO_GQL = """query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issueOrPullRequest(number: $number) {
      ... on PullRequest {
        comments(first: 100) { nodes { url author { login } authorAssociation body } }
        reviews(first: 50) { nodes { url author { login } authorAssociation body createdAt comments { totalCount } } }
      }
      ... on Issue { comments(first: 100) { nodes { url author { login } authorAssociation body } } }
    }
  }
}"""


class InvalidLogin(ValueError):
    pass


class GhError(RuntimeError):
    pass


def _gh_graphql(gql: str, *, search: str | None = None, **fields: str | int) -> dict[str, Any]:
    """Run one GraphQL call. The search string goes through a tempfile (`-F q=@file`), never the command line."""
    cmd = ["gh", "api", "graphql", "-f", f"query={gql}"]
    tmp = None
    if search is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(search)
            tmp = fh.name
        cmd += ["-F", f"q=@{tmp}"]
    for key, value in fields.items():
        cmd += ["-F", f"{key}={value}"] if isinstance(value, int) else ["-f", f"{key}={value}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    finally:
        if tmp:
            Path(tmp).unlink(missing_ok=True)
    if result.returncode != 0:
        raise GhError(result.stderr.strip())
    data: dict[str, Any] = json.loads(result.stdout)
    return data


def _search(q: str) -> tuple[list[dict[str, Any]], bool]:
    nodes: list[dict[str, Any]] = []
    cursor = ""
    total = 0
    for _ in range(PAGES):
        data = _gh_graphql(SEARCH_GQL, search=q, cursor=cursor)["data"]["search"]
        total = data["issueCount"]
        nodes += [n for n in data["nodes"] if n]
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return nodes, total > len(nodes)


def _item(kind: Kind, node: dict[str, Any], prefix: str) -> Item:
    return Item(
        id=f"{prefix}-{node['number']}",
        kind=kind,
        url=node["url"],
        thread=node["url"],
        created_at=node["createdAt"][:10],
        merged=bool(node.get("merged")),
        closed_unmerged=node.get("state") == "CLOSED" and not node.get("merged"),
        areas=tuple(n["name"] for n in node.get("labels", {}).get("nodes", [])),
    )


def _convo(repo: str, number: int) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    data = _gh_graphql(CONVO_GQL, owner=owner, repo=name, number=number)
    convo: dict[str, Any] = data["data"]["repository"]["issueOrPullRequest"] or {}
    return convo


def _pushback(convo: dict[str, Any], login: str, phrases: Iterable[str], maintainers: Iterable[str]) -> str:
    """URL of the first maintainer comment containing a pushback phrase — a candidate, not a verdict."""
    wanted = tuple(p.lower() for p in (*GENERIC_PHRASES, *phrases) if p.strip())
    maint = set(maintainers)
    comments = convo.get("comments", {}).get("nodes", []) + convo.get("reviews", {}).get("nodes", [])
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


def fetch_items(
    repo: str,
    login: str,
    *,
    since: str,
    end: str,
    review_depth: int,
    phrases: Iterable[str],
    maintainers: Iterable[str],
) -> tuple[list[Item], list[str]]:
    """Fetch the five activity streams; return the items and the names of streams that hit their cap."""
    if not LOGIN_RE.match(login):
        raise InvalidLogin(login)
    phrases, maintainers = tuple(phrases), tuple(maintainers)
    base = f"repo:{repo}"
    streams: list[tuple[str, str, Kind]] = [
        ("prs_opened", f"{base} type:pr author:{login} created:{since}..{end}", "pr"),
        ("issues_filed", f"{base} type:issue author:{login} created:{since}..{end}", "issue"),
        ("reviews_total", f"{base} type:pr reviewed-by:{login} updated:>={since}", "review"),
        (
            "issues_triaged",
            f"{base} type:issue commenter:{login} -author:{login} updated:>={since}",
            "triage",
        ),
        ("threads_commented", f"{base} commenter:{login} updated:>={since}", "thread"),
    ]
    items: list[Item] = []
    caps: list[str] = []
    for name, q, kind in streams:
        nodes, capped = _search(q)
        if capped:
            caps.append(name)
        items += [_item(kind, n, kind) for n in nodes]

    def recent(kinds: tuple[str, ...], n: int) -> list[Item]:
        return sorted((i for i in items if i.kind in kinds), key=lambda i: i.created_at, reverse=True)[:n]

    deep = {i.id for i in recent(("review",), review_depth)}
    inspect = {
        i.id for i in (*recent(("pr", "issue"), CONVO_BUDGET), *recent(("thread",), CONVO_BUDGET))
    } | deep

    out: list[Item] = []
    for i in items:
        if i.id not in inspect:
            out.append(i)
            continue
        convo = _convo(repo, int(i.url.rstrip("/").rsplit("/", 1)[1]))
        changes: dict[str, Any] = {"pushback_candidate": _pushback(convo, login, phrases, maintainers)}
        if i.id in deep:
            mine = [
                r
                for r in convo.get("reviews", {}).get("nodes", [])
                if (r.get("author") or {}).get("login") == login
            ]
            changes["substantive"] = any(
                len(r.get("body") or "") > 100 or r["comments"]["totalCount"] > 0 for r in mine
            )
        out.append(Item.from_json({**i.to_json(), **changes}))
    return out, caps
