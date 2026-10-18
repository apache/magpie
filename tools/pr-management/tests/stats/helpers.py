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

"""Shared fixture builders for the pr-management-stats tests.

Not a test module (no ``test_`` prefix) so pytest does not collect it.
Builds GraphQL-shaped PR node dicts that match the OPEN_PRS_QUERY /
CLOSED_PRS_QUERY schemas so they can be fed straight through
``reference.classify`` and the dashboard aggregations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pr_management.stats import reference

# Fixed "now" so age-based classification is deterministic across runs.
NOW = datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def make_ctx(**overrides):
    ctx = {
        "now": NOW,
        "cutoff": NOW - timedelta(weeks=6),
        "weeks": reference.weeks_buckets(NOW, 6),
        "triage_marker": reference.DEFAULT_TRIAGE_MARKER,
        "ai_footer": reference.DEFAULT_AI_FOOTER,
        "ready_label": reference.DEFAULT_READY_LABEL,
        "area_prefix": reference.DEFAULT_AREA_PREFIX,
        "repo": "apache/airflow",
        "viewer": "tester",
    }
    ctx.update(overrides)
    return ctx


def comment(body, *, author="maintainer", assoc="MEMBER", days_ago=3):
    return {
        "author": {"login": author, "__typename": "User"},
        "authorAssociation": assoc,
        "createdAt": _iso(days_ago),
        "body": body,
    }


def make_pr(
    number,
    *,
    author="contributor",
    assoc="NONE",
    is_draft=False,
    created_days_ago=10,
    labels=None,
    comments=None,
    reviews=None,
    review_threads=None,
    timeline=None,
    commits=None,
    closed_days_ago=None,
    merged=False,
    include_engagement=True,
):
    """Build one PR node.

    ``include_engagement=False`` simulates the reduced CLOSED_PRS_QUERY schema
    (no commits / latestReviews / reviewThreads / timelineItems).
    """
    node = {
        "number": number,
        "title": f"PR {number}",
        "isDraft": is_draft,
        "createdAt": _iso(created_days_ago),
        "author": {"login": author, "__typename": "User"} if author else None,
        "authorAssociation": assoc,
        "labels": {"nodes": [{"name": n} for n in (labels or [])]},
        "comments": {"nodes": comments or []},
    }
    if include_engagement:
        node["latestReviews"] = {"nodes": reviews or []}
        node["reviewThreads"] = {"nodes": review_threads or []}
        node["timelineItems"] = {"nodes": timeline or []}
        node["commits"] = {"nodes": commits or []}
    if closed_days_ago is not None:
        node["closedAt"] = _iso(closed_days_ago)
        node["mergedAt"] = _iso(closed_days_ago) if merged else None
        node["merged"] = merged
        node["state"] = "MERGED" if merged else "CLOSED"
    return node


def classify_all(prs, ctx, *, partial=False):
    for pr in prs:
        reference.classify(pr, ctx, partial=partial)
    return prs
