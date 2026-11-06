# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
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
"""Author timeline activity must not hide contributor PRs awaiting triage."""

from __future__ import annotations

import pytest

from pr_management.stats import dashboard, reference

from .helpers import _iso, comment, make_ctx, make_pr

EVENT_TYPES = ("LabeledEvent", "ReadyForReviewEvent", "ConvertToDraftEvent")


def _event(kind, actor="contributor", *, label="area:docs", days_ago=1):
    event = {
        "__typename": kind,
        "createdAt": _iso(days_ago),
        "actor": {"login": actor} if actor else None,
    }
    if kind == "LabeledEvent":
        event["label"] = {"name": label}
    return event


@pytest.mark.parametrize("kind", EVENT_TYPES)
# The case variant is defensive coverage, not a claim about live API casing.
@pytest.mark.parametrize("actor", ["contributor", "CONTRIBUTOR"])
def test_author_timeline_activity_stays_in_untriaged_backlog(kind, actor):
    ctx = make_ctx()
    pr = make_pr(1, created_days_ago=40, timeline=[_event(kind, actor)])

    reference.classify(pr, ctx)

    assert pr["_is_engaged"] is False
    assert pr["_is_untriaged"] is True
    hero = dashboard.compute_hero_counts([pr], ctx["now"])
    assert hero["untriaged"] == hero["untriaged_4w"] == 1
    assert hero["defacto"] == 0
    assert dashboard.compute_health_rating(hero)[0] == "⚠️ Needs attention"
    recommendations = dashboard.compute_recommendations([pr], [], [], hero, 0, ctx["now"])
    triage = next(
        r for r in recommendations if r["action"] == "/magpie-pr-management:pr-triage all PR issues"
    )
    assert triage["priority"] == "high"
    assert triage["count"] == 1


@pytest.mark.parametrize("kind", EVENT_TYPES)
def test_other_human_timeline_activity_still_counts_as_engagement(kind):
    pr = make_pr(1, timeline=[_event(kind, "maintainer")])

    reference.classify(pr, make_ctx())

    assert pr["_is_engaged"] is True
    assert pr["_is_untriaged"] is False


@pytest.mark.parametrize("actor", ["github-actions[bot]", "Copilot", None])
def test_bot_or_missing_actor_does_not_count_as_engagement(actor):
    pr = make_pr(1, timeline=[_event(kind, actor) for kind in EVENT_TYPES])

    reference.classify(pr, make_ctx())

    assert pr["_is_engaged"] is False
    assert pr["_is_untriaged"] is True


def test_author_event_does_not_hide_other_human_event():
    pr = make_pr(
        1,
        timeline=[_event("ReadyForReviewEvent"), _event("LabeledEvent", "maintainer")],
    )

    reference.classify(pr, make_ctx())

    assert pr["_is_engaged"] is True


def test_author_event_does_not_suppress_collaborator_comment():
    pr = make_pr(1, timeline=[_event("ReadyForReviewEvent")], comments=[comment("Looking into this.")])

    reference.classify(pr, make_ctx())

    assert pr["_is_engaged"] is True


def test_ready_label_and_latest_label_timestamp_are_independent_of_actor():
    ctx = make_ctx()
    ready = ctx["ready_label"]
    pr = make_pr(
        1,
        labels=[ready],
        timeline=[
            _event("LabeledEvent", label=ready, days_ago=1),
            _event("LabeledEvent", "maintainer", label=ready, days_ago=3),
        ],
    )

    reference.classify(pr, ctx)

    assert pr["_has_ready"] is True
    assert pr["_is_engaged"] is True
    assert pr["_is_untriaged"] is False
    assert pr["_label_added_at"] == reference.parse_iso(_iso(1))


def test_ready_label_is_engagement_even_when_only_author_has_events():
    ctx = make_ctx()
    pr = make_pr(
        1,
        labels=[ctx["ready_label"]],
        timeline=[_event("LabeledEvent", label=ctx["ready_label"])],
    )

    reference.classify(pr, ctx)

    assert pr["_is_engaged"] is True
    assert pr["_is_untriaged"] is False
    assert pr["_label_added_at"] == reference.parse_iso(_iso(1))


def test_other_human_event_with_deleted_pr_author():
    pr = make_pr(1, author=None, timeline=[_event("LabeledEvent", "maintainer")])

    reference.classify(pr, make_ctx())

    assert pr["_is_engaged"] is True


@pytest.mark.parametrize("kind", EVENT_TYPES)
@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_collaborator_own_timeline_activity_remains_engagement(kind, association):
    ctx = make_ctx()
    pr = make_pr(1, author="maintainer", assoc=association, timeline=[_event(kind, "maintainer")])

    reference.classify(pr, ctx)

    assert pr["_is_engaged"] is True
    assert pr["_is_untriaged"] is False
    assert dashboard.compute_hero_counts([pr], ctx["now"])["defacto"] == 1


@pytest.mark.parametrize("association", ["CONTRIBUTOR", "MEMBER"])
@pytest.mark.parametrize("merged", [False, True])
@pytest.mark.parametrize("typed", [False, True])
def test_closed_pr_own_actor_remains_engagement(association, merged, typed):
    # Preserve legacy self-closure behavior for this limited change.
    # A separate closed-PR policy fix may revise this compatibility expectation.
    # The real closed queries select only actor.login, without __typename.
    event: dict[str, object] = {"actor": {"login": "author"}}
    if typed:
        event["__typename"] = "ClosedEvent"
    pr = make_pr(
        1,
        author="author",
        assoc=association,
        closed_days_ago=2,
        merged=merged,
        include_engagement=False,
        timeline=[event],
    )
    assert pr["timelineItems"]["nodes"] == [event]
    assert not {"commits", "latestReviews", "reviewThreads"}.intersection(pr)

    reference.classify(pr, make_ctx(), partial=True)

    assert pr["_is_engaged"] is True


def test_closed_pr_coverage_preserves_all_closure_actors():
    # Keep the legacy closed-PR metric here, including contributor self-closes.
    # This compatibility assertion does not endorse self-closure as maintainer engagement.
    ctx = make_ctx()
    closed_prs = []
    for n, (author, association, actor, merged) in enumerate(
        [
            ("member", "MEMBER", "member", True),
            ("collaborator", "COLLABORATOR", "collaborator", True),
            ("contributor", "CONTRIBUTOR", "contributor", False),
            ("other", "CONTRIBUTOR", "maintainer", False),
        ],
        start=1,
    ):
        pr = make_pr(
            n,
            author=author,
            assoc=association,
            created_days_ago=20,
            closed_days_ago=2,
            merged=merged,
            include_engagement=False,
            timeline=[{"actor": {"login": actor}}],
        )
        reference.classify(pr, ctx, partial=True)
        closed_prs.append(pr)

    coverage = dashboard.compute_triage_coverage_rate(closed_prs, ctx["weeks"])
    bucket = next(row for row in coverage if row["opened"])
    assert bucket["opened"] == bucket["engaged"] == 4
    assert bucket["rate"] == 100.0
