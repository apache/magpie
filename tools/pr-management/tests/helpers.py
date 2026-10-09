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
"""Build `TriagePR` nodes the way `gql-pr-triage-*` returns them."""

from __future__ import annotations

import datetime as dt
from typing import Any

NOW = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.UTC)


def ago(**delta: float) -> str:
    return (NOW - dt.timedelta(**delta)).isoformat().replace("+00:00", "Z")


def comment(
    author: str, assoc: str = "CONTRIBUTOR", when: str | None = None, body: str = "ok"
) -> dict[str, Any]:
    return {
        "author": {"login": author},
        "authorAssociation": assoc,
        "createdAt": when or ago(days=1),
        "bodyText": body,
        "url": f"https://github.com/acme/product/pull/1#issuecomment-{abs(hash((author, when, body))) % 10**6}",
    }


def thread(*comments: dict[str, Any], resolved: bool = False) -> dict[str, Any]:
    return {"isResolved": resolved, "comments": {"nodes": list(comments)}}


def review(
    author: str, state: str, assoc: str = "MEMBER", when: str | None = None, body: str = ""
) -> dict[str, Any]:
    return {
        "state": state,
        "author": {"login": author},
        "authorAssociation": assoc,
        "submittedAt": when or ago(days=1),
        "body": body,
    }


def check(
    name: str, conclusion: str | None = "SUCCESS", status: str = "COMPLETED", started: str | None = None
) -> dict[str, Any]:
    return {
        "__typename": "CheckRun",
        "name": name,
        "conclusion": conclusion,
        "status": status,
        "startedAt": started or ago(days=3),
        "completedAt": started or ago(days=3),
    }


def pr(
    number: int = 1,
    *,
    author: str = "nina-contributor",
    assoc: str = "CONTRIBUTOR",
    created: str | None = None,
    updated: str | None = None,
    committed: str | None = None,
    draft: bool = False,
    body: str = "A change.",
    mergeable: str = "MERGEABLE",
    rollup: str | None = "SUCCESS",
    checks: list[dict[str, Any]] | None = None,
    contexts_total: int | None = None,
    threads: list[dict[str, Any]] | None = None,
    reviews: list[dict[str, Any]] | None = None,
    comments: list[dict[str, Any]] | None = None,
    labels: list[str] | None = None,
    label_events: list[dict[str, Any]] | None = None,
    title: str = "Fix a thing",
    head: str = "abc1234def5678",
    commit_messages: list[str] | None = None,
) -> dict[str, Any]:
    checks = [check("Tests (unit)")] if checks is None else checks
    messages = commit_messages or ["Fix a thing"]
    return {
        "number": number,
        "title": title,
        "url": f"https://github.com/acme/product/pull/{number}",
        "id": f"PR_{number}",
        "createdAt": created or ago(days=10),
        "updatedAt": updated or ago(days=2),
        "isDraft": draft,
        "body": body,
        "mergeable": mergeable,
        "baseRefName": "main",
        "headRefName": "fix",
        "headRefOid": head,
        "additions": 10,
        "deletions": 2,
        "changedFiles": 1,
        "author": {"login": author},
        "authorAssociation": assoc,
        "labels": {"nodes": [{"name": n} for n in labels or []]},
        "assignees": {"nodes": []},
        "commits": {
            "totalCount": len(messages),
            "nodes": [
                {
                    "commit": {
                        "oid": head if i == len(messages) - 1 else f"{i:07d}",
                        "committedDate": committed or ago(days=3),
                        "message": m,
                    }
                }
                for i, m in enumerate(messages)
            ],
        },
        "head": {
            "nodes": [
                {
                    "commit": {
                        "oid": head,
                        "committedDate": committed or ago(days=3),
                        "statusCheckRollup": None
                        if rollup is None
                        else {
                            "state": rollup,
                            "contexts": {
                                "totalCount": len(checks) if contexts_total is None else contexts_total,
                                "nodes": checks,
                            },
                        },
                    }
                }
            ]
        },
        "reviewThreads": {"totalCount": len(threads or []), "nodes": threads or []},
        "latestReviews": {"nodes": reviews or []},
        "comments": {"nodes": comments or []},
        "timelineItems": {"nodes": label_events or []},
    }


def page(*nodes: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"data": {"search": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": list(nodes)}}}
    ]
