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

"""Tests for compute_attribution (the stats spec § Drafts & closes by person)."""

from __future__ import annotations

from pr_management.stats import dashboard, reference

from .helpers import _iso, classify_all, comment, make_ctx, make_pr


def _draft_event(actor, *, days_ago=3):
    return {
        "__typename": "ConvertToDraftEvent",
        "createdAt": _iso(days_ago),
        "actor": {"login": actor},
    }


def _labeled_event(actor, *, days_ago=3, label="area:foo"):
    return {
        "__typename": "LabeledEvent",
        "createdAt": _iso(days_ago),
        "actor": {"login": actor},
        "label": {"name": label},
    }


def _closed_pr(
    number, *, author, closed_actor, days_ago=3, merged=False, base_ref="main", title=None, assoc="NONE"
):
    pr = make_pr(
        number,
        author=author,
        assoc=assoc,
        created_days_ago=20,
        closed_days_ago=days_ago,
        merged=merged,
        include_engagement=False,
        comments=[comment("seen", author="maint", assoc="MEMBER", days_ago=days_ago + 1)],
    )
    pr["baseRefName"] = base_ref
    if title is not None:
        pr["title"] = title
    pr["timelineItems"] = {"nodes": [{"actor": {"login": closed_actor}}]}
    return pr


def test_draft_attribution_triage_vs_author_split():
    ctx = make_ctx()
    open_prs = classify_all(
        [
            # maintainer converts someone else's PR to draft → triage
            make_pr(1, author="alice", assoc="NONE", timeline=[_draft_event("maint")]),
            # author self-converts → author self-action
            make_pr(2, author="bob", assoc="NONE", timeline=[_draft_event("bob")]),
            # a LabeledEvent must NOT be counted as a draft conversion
            make_pr(3, author="carol", assoc="NONE", timeline=[_labeled_event("maint")]),
        ],
        ctx,
    )
    attr = dashboard.compute_attribution(open_prs, [], ctx)
    drafts = attr["drafts"]
    assert drafts["total"] == 2
    assert drafts["triage"] == 1
    assert drafts["author"] == 1
    assert drafts["by_person_triage"].get("maint") == 1


def test_close_attribution_triage_vs_author_split():
    ctx = make_ctx()
    closed = [
        _closed_pr(10, author="alice", closed_actor="maint"),  # triage close
        _closed_pr(11, author="bob", closed_actor="bob"),  # author self-close
        _closed_pr(12, author="carol", closed_actor="maint", merged=True),  # merged → ignored
    ]
    for pr in closed:
        reference.classify(pr, ctx, partial=True)
    attr = dashboard.compute_attribution([], closed, ctx)
    closes = attr["closes"]
    assert closes["total"] == 2  # merged PR excluded
    assert closes["triage"] == 1
    assert closes["author"] == 1
    assert closes["by_person"].get("maint") == 1


def test_bot_and_backport_prs_excluded_before_attribution():
    ctx = make_ctx()
    open_prs = classify_all(
        [
            # bot-authored draft conversion → excluded
            make_pr(20, author="dependabot", assoc="NONE", timeline=[_draft_event("maint")]),
        ],
        ctx,
    )
    closed = [
        # backport via base branch → excluded
        _closed_pr(21, author="alice", closed_actor="maint", base_ref="v3-1-test"),
        # backport via title → excluded
        _closed_pr(
            22, author="bob", closed_actor="maint", base_ref="main", title="[v2-10-stable] Fix something"
        ),
        # bot-authored close → excluded
        _closed_pr(23, author="github-actions[bot]", closed_actor="maint"),
    ]
    for pr in closed:
        reference.classify(pr, ctx, partial=True)
    attr = dashboard.compute_attribution(open_prs, closed, ctx)

    assert attr["drafts"]["total"] == 0
    assert attr["closes"]["total"] == 0
    assert attr["excluded"]["bot"] == 2  # dependabot draft + gha close
    assert attr["excluded"]["backport"] == 2  # base-branch + title


def test_maintainer_set_derived_from_comments_not_hardcoded():
    ctx = make_ctx()
    open_prs = classify_all(
        [
            make_pr(
                30,
                author="alice",
                assoc="NONE",
                comments=[comment("hi", author="reviewer1", assoc="COLLABORATOR")],
                timeline=[_draft_event("reviewer1")],
            ),
        ],
        ctx,
    )
    attr = dashboard.compute_attribution(open_prs, [], ctx)
    assert "reviewer1" in attr["maintainers"]


def test_events_before_cutoff_excluded():
    ctx = make_ctx()
    open_prs = classify_all(
        [
            make_pr(
                40, author="alice", assoc="NONE", timeline=[_draft_event("maint", days_ago=60)]
            ),  # before 6w cutoff
        ],
        ctx,
    )
    attr = dashboard.compute_attribution(open_prs, [], ctx)
    assert attr["drafts"]["total"] == 0


def test_render_attribution_table_shape():
    ctx = make_ctx()
    open_prs = classify_all(
        [
            make_pr(
                50,
                author="alice",
                assoc="NONE",
                comments=[comment("converting", author="maint", assoc="MEMBER")],
                timeline=[_draft_event("maint")],
            )
        ],
        ctx,
    )
    attr = dashboard.compute_attribution(open_prs, [], ctx)
    out = dashboard.render_attribution(attr)
    assert "Drafts &amp; closes attribution by person" in out
    assert "@maint" in out
    assert "Closing stats by person" in out
