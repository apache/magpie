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

"""Unit tests for the pure aggregation functions (aggregate.md)."""
from __future__ import annotations

import dashboard
import reference
from helpers import classify_all, comment, make_ctx, make_pr

QC = reference.DEFAULT_TRIAGE_MARKER
AI = reference.DEFAULT_AI_FOOTER
READY = reference.DEFAULT_READY_LABEL


def _hero_dataset(ctx):
    prs = [
        # contributor, non-draft, untriaged, >4 weeks old
        make_pr(1, author="alice", assoc="NONE", created_days_ago=40),
        # contributor, non-draft, ready-labelled (engaged, not untriaged)
        make_pr(2, author="bob", assoc="NONE", labels=[READY]),
        # collaborator-authored
        make_pr(3, author="maint", assoc="MEMBER"),
        # contributor draft
        make_pr(4, author="carol", assoc="NONE", is_draft=True),
        # bot
        make_pr(5, author="dependabot", assoc="NONE"),
        # contributor with quality-criteria marker comment by a member → triaged
        make_pr(
            6, author="dave", assoc="NONE",
            comments=[comment(f"... {QC} ...", author="maint", assoc="MEMBER")],
        ),
    ]
    return classify_all(prs, ctx)


def test_compute_hero_counts():
    ctx = make_ctx()
    hero = dashboard.compute_hero_counts(_hero_dataset(ctx))

    assert hero["open_total"] == 5          # bot excluded
    assert hero["drafts"] == 1
    assert hero["non_drafts"] == 4
    assert hero["contribs"] == 4
    assert hero["collabs"] == 1
    assert hero["contrib_nondraft_total"] == 3
    assert hero["ready"] == 1
    assert hero["untriaged"] == 1
    assert hero["untriaged_4w"] == 1
    assert hero["qc_triaged"] == 1
    assert hero["defacto"] == 1             # PR2: engaged-via-ready, no marker
    assert hero["ai_triaged"] == 0
    assert hero["bots"] == 1
    assert hero["bots_dependabot"] == 1
    assert hero["bots_other"] == 0


def test_compute_pressure_by_area_thresholds_and_score():
    ctx = make_ctx()
    prs = classify_all(
        [
            make_pr(10, assoc="NONE", labels=["area:scheduler"], created_days_ago=40),
            make_pr(11, assoc="NONE", labels=["area:scheduler"], created_days_ago=40),
            make_pr(12, assoc="NONE", labels=["area:scheduler"], created_days_ago=12),
            # second area below the contribs>=3 cutoff → must be dropped
            make_pr(13, assoc="NONE", labels=["area:api"], created_days_ago=40),
        ],
        ctx,
    )
    rows = dashboard.compute_pressure_by_area(prs, ctx["area_prefix"])

    assert [area for area, _ in rows] == ["scheduler"]  # api dropped (<3 contribs)
    _, v = rows[0]
    assert v["contribs"] == 3
    assert v["u4w"] == 2          # two PRs >28d
    assert v["u14w"] == 1         # one PR 7<age<=28
    assert v["score"] == 5 + 5 + 3


def test_compute_recommendations_high_priority_for_4w_backlog():
    ctx = make_ctx()
    prs = classify_all(
        [make_pr(n, assoc="NONE", created_days_ago=40) for n in range(20, 23)],
        ctx,
    )
    hero = dashboard.compute_hero_counts(prs)
    recs = dashboard.compute_recommendations(prs, [], [], hero, 0)

    assert recs, "expected at least the 4-week-backlog recommendation"
    assert recs[0]["priority"] == "high"
    assert recs[0]["count"] == 3


def test_area_recommendation_count_uses_untriaged_not_total_contribs():
    """Regression for PR #348 nit: the area rec's count must reflect the
    untriaged pile (u4w), the signal that fires the rule — not total contribs."""
    pressure = [(
        "scheduler",
        {"contribs": 9, "u4w": 4, "u14w": 2, "urec": 0, "wait": 0, "ready": 0, "score": 26},
    )]
    hero = {"ready": 0}
    recs = dashboard.compute_recommendations([], [], pressure, hero, 0)

    area_recs = [r for r in recs if r["icon"] == "📍"]
    assert len(area_recs) == 1
    assert area_recs[0]["count"] == 4          # u4w, NOT contribs (9)


def test_compute_health_rating_bands():
    # 0 points → healthy
    assert dashboard.compute_health_rating(
        {"untriaged_4w": 0, "untriaged": 0, "ready": 0}, []
    )[0].startswith("✅")
    # untriaged_4w (2) + untriaged>30 (1) = 3 points → needs attention
    assert dashboard.compute_health_rating(
        {"untriaged_4w": 5, "untriaged": 40, "ready": 0}, []
    )[0].startswith("⚠️")
    # add a high-priority rec (2) → 5 points → action needed
    assert dashboard.compute_health_rating(
        {"untriaged_4w": 5, "untriaged": 40, "ready": 0},
        [{"priority": "high"}],
    )[0].startswith("🔥")


def test_weekly_velocity_counts_merged_and_closed():
    ctx = make_ctx()
    closed = [
        make_pr(30, assoc="NONE", created_days_ago=20, closed_days_ago=3,
                merged=True, include_engagement=False,
                comments=[comment(f"{QC}", author="m", assoc="MEMBER", days_ago=4)]),
        make_pr(31, assoc="NONE", created_days_ago=20, closed_days_ago=3,
                merged=False, include_engagement=False),
    ]
    weekly = reference.compute_weekly_velocity(closed, ctx["weeks"], ctx)

    assert len(weekly) == 6
    assert sum(w["merged"] for w in weekly) == 1
    assert sum(w["closed_not_merged"] for w in weekly) == 1
    assert sum(w["merged_triaged"] for w in weekly) == 1


def test_fold_channel_triage_is_counted():
    """A PR triaged via the pr-body fold block (no QC comment) must count as
    triaged + AI-drafted across classify, triage-velocity, and weekly-velocity
    — the regression that made recent-week triage velocity read as zero once
    the pr-body channel became the default."""
    from datetime import timedelta

    ctx = make_ctx()
    now = ctx["now"]
    triaged_iso = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fold_body = (
        f"Original description.\n\n"
        f"<!-- pr-triage-fold: triaged={triaged_iso} head=abc1234 action=comment -->\n"
        f"> Maintainer triage note for @alice · by `@potiuk`\n"
        f"> see the {QC}\n"
        f"<!-- /pr-triage-fold -->"
    )
    # No collaborator QC *comment* — the marker lives only in the body fold.
    pr = make_pr(50, assoc="NONE", created_days_ago=10, comments=[])
    pr["body"] = fold_body

    reference.classify(pr, ctx)
    assert pr["_is_triaged"] is True
    assert pr["_has_ai_footer"] is True  # a fold is always AI-drafted
    assert pr["_triage_at"] is not None

    events = reference.triage_marker_events(pr, ctx)
    assert len(events) == 1 and events[0][1] is True

    vel = dashboard.compute_triage_velocity([pr], ctx["weeks"], ctx)
    assert sum(w["ai"] for w in vel) == 1
    assert sum(w["manual"] for w in vel) == 0
