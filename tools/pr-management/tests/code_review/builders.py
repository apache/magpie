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
"""Build `gql-cr-open` / `gql-cr-pr` nodes for the code-review tests."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pr_management.code_review import data

NOW = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.UTC)


def ago(**delta: float) -> str:
    return (NOW - dt.timedelta(**delta)).isoformat().replace("+00:00", "Z")


def check(name: str, conclusion: str = "SUCCESS") -> dict[str, Any]:
    return {"__typename": "CheckRun", "name": name, "conclusion": conclusion, "status": "COMPLETED"}


def node(
    number: int = 1,
    *,
    title: str = "Fix a thing",
    author: str = "nina",
    assoc: str = "CONTRIBUTOR",
    draft: bool = False,
    body: str = "A change.",
    files: list[str] | None = None,
    requested: list[str] | None = None,
    requested_teams: list[str] | None = None,
    comments: list[tuple[str, str]] | None = None,
    reviews: list[dict[str, Any]] | None = None,
    commits: list[dict[str, Any]] | None = None,
    labels: list[str] | None = None,
    rollup: str | None = "SUCCESS",
    checks: list[dict[str, Any]] | None = None,
    unresolved: int = 0,
    mergeable: str = "MERGEABLE",
    merge_state: str = "CLEAN",
    head: str = "abc1234def",
    updated: str | None = None,
    additions: int = 10,
    deletions: int = 2,
) -> dict[str, Any]:
    files = ["src/a.py"] if files is None else files
    checks = [check("Tests")] if checks is None else checks
    requests: list[dict[str, Any]] = [
        {"requestedReviewer": {"__typename": "User", "login": u}} for u in requested or []
    ]
    for team in requested_teams or []:
        org, slug = team.split("/")
        requests.append(
            {"requestedReviewer": {"__typename": "Team", "slug": slug, "organization": {"login": org}}}
        )
    return {
        "id": f"PR_{number}",
        "number": number,
        "title": title,
        "url": f"https://github.com/acme/product/pull/{number}",
        "isDraft": draft,
        "createdAt": ago(days=10),
        "updatedAt": updated or ago(days=1),
        "headRefOid": head,
        "baseRefName": "main",
        "author": {"login": author},
        "authorAssociation": assoc,
        "mergeable": mergeable,
        "mergeStateStatus": merge_state,
        "additions": additions,
        "deletions": deletions,
        "changedFiles": len(files),
        "body": body,
        "bodyText": body,
        "labels": {"nodes": [{"name": label} for label in labels or []]},
        "reviewRequests": {"nodes": requests},
        "files": {
            "totalCount": len(files),
            "nodes": [{"path": f, "additions": 5, "deletions": 1} for f in files],
        },
        "comments": {"nodes": [{"author": {"login": a}, "bodyText": b} for a, b in comments or []]},
        "reviews": {"nodes": reviews or []},
        "commits": {"nodes": commits or [{"commit": {"oid": head, "message": "Fix a thing"}}]},
        "reviewThreads": {
            "totalCount": unresolved,
            "nodes": [{"isResolved": False} for _ in range(unresolved)],
        },
        "latest": {
            "nodes": [
                {
                    "commit": {
                        "statusCheckRollup": None
                        if rollup is None
                        else {"state": rollup, "contexts": {"nodes": checks}}
                    }
                }
            ]
        },
    }


def commit(message: str, *authors: str, at: str | None = None, oid: str = "c0ffee1") -> dict[str, Any]:
    return {
        "commit": {
            "oid": oid,
            "message": message,
            "authoredDate": at,
            "authors": {"nodes": [{"name": a, "email": f"{a}@x", "user": {"login": a}} for a in authors]},
        }
    }


def review(
    author: str, state: str, *, commit_oid: str | None = None, when: str | None = None, body: str = ""
) -> dict[str, Any]:
    return {
        "author": {"login": author},
        "state": state,
        "submittedAt": when or ago(days=2),
        "bodyText": body,
        "commit": {"oid": commit_oid} if commit_oid else None,
        "comments": {"nodes": []},
    }


def pr(**kw: Any) -> data.PR:
    return data.from_node(node(**kw))
