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

"""Tests for compute_ready_split (render.md § Ready-for-review queue split)."""
from __future__ import annotations

import dashboard
import reference
from helpers import classify_all, comment, make_ctx, make_pr

QC = reference.DEFAULT_TRIAGE_MARKER
READY = reference.DEFAULT_READY_LABEL


def _ready(number, **kw):
    labels = kw.pop("labels", [])
    return make_pr(number, labels=[READY, *labels], **kw)


def test_ready_split_classifies_each_substate_once():
    ctx = make_ctx()
    prs = classify_all(
        [
            # never reviewed: ready, no decision, no maintainer discussion
            _ready(1, author="alice", assoc="NONE", created_days_ago=5),
            # changes requested
            _ready(2, author="bob", assoc="NONE", created_days_ago=20),
            # approved
            _ready(3, author="carol", assoc="NONE", created_days_ago=40),
            # discussed-no-decision: real (non-marker) maintainer comment
            _ready(
                4, author="dave", assoc="NONE", created_days_ago=70,
                comments=[comment("can you rebase?", author="maint", assoc="MEMBER")],
            ),
        ],
        ctx,
    )
    # Inject review decisions (classify reads pr["reviewDecision"]).
    prs[1]["_review_decision"] = "CHANGES_REQUESTED"
    prs[2]["_review_decision"] = "APPROVED"

    split = dashboard.compute_ready_split(prs, ctx)
    c = split["counts"]
    assert c["never-reviewed"] == 1
    assert c["changes-requested"] == 1
    assert c["approved"] == 1
    assert c["discussed-no-decision"] == 1
    assert split["total"] == 4
    assert split["excluded_maintainer"] == 0


def test_triage_marker_comment_does_not_count_as_discussion():
    """A maintainer comment that is ONLY the triage marker must leave the PR in
    `never-reviewed`, not `discussed-no-decision`."""
    ctx = make_ctx()
    prs = classify_all(
        [
            _ready(
                10, author="alice", assoc="NONE", created_days_ago=5,
                comments=[comment(f"... {QC} ...", author="maint", assoc="MEMBER")],
            ),
        ],
        ctx,
    )
    split = dashboard.compute_ready_split(prs, ctx)
    assert split["counts"]["never-reviewed"] == 1
    assert split["counts"]["discussed-no-decision"] == 0


def test_commented_review_counts_as_discussion():
    ctx = make_ctx()
    prs = classify_all(
        [
            _ready(
                11, author="alice", assoc="NONE", created_days_ago=5,
                reviews=[{"author": {"login": "maint"}, "state": "COMMENTED",
                          "submittedAt": None}],
            ),
        ],
        ctx,
    )
    split = dashboard.compute_ready_split(prs, ctx)
    assert split["counts"]["discussed-no-decision"] == 1
    assert split["counts"]["never-reviewed"] == 0


def test_maintainer_authored_ready_prs_are_excluded():
    ctx = make_ctx()
    prs = classify_all(
        [
            _ready(20, author="maint", assoc="MEMBER", created_days_ago=5),
            _ready(21, author="alice", assoc="NONE", created_days_ago=5),
        ],
        ctx,
    )
    split = dashboard.compute_ready_split(prs, ctx)
    assert split["total"] == 1
    assert split["excluded_maintainer"] == 1


def test_age_buckets_in_timeline():
    ctx = make_ctx()
    prs = classify_all(
        [
            _ready(30, author="a", assoc="NONE", created_days_ago=3),   # 0-2w
            _ready(31, author="b", assoc="NONE", created_days_ago=20),  # 2-4w
            _ready(32, author="c", assoc="NONE", created_days_ago=50),  # 4-8w
            _ready(33, author="d", assoc="NONE", created_days_ago=70),  # 8-12w
            _ready(34, author="e", assoc="NONE", created_days_ago=120),  # >12w
        ],
        ctx,
    )
    split = dashboard.compute_ready_split(prs, ctx)
    tl = split["timeline"]
    assert tl["0-2w"]["never-reviewed"] == 1
    assert tl["2-4w"]["never-reviewed"] == 1
    assert tl["4-8w"]["never-reviewed"] == 1
    assert tl["8-12w"]["never-reviewed"] == 1
    assert tl[">12w"]["never-reviewed"] == 1


def test_render_ready_split_oldest_on_left_and_cards():
    ctx = make_ctx()
    prs = classify_all(
        [_ready(40, author="a", assoc="NONE", created_days_ago=3)], ctx
    )
    split = dashboard.compute_ready_split(prs, ctx)
    out = dashboard.render_ready_split(split)
    assert "Ready-for-review queue split" in out
    assert "Never reviewed" in out
    # Oldest-on-left: the >12w x-axis label must appear before 0-2w in the SVG.
    # esc() HTML-escapes the ">" in the bucket label to "&gt;".
    assert out.index("&gt;12w") < out.index("0-2w")


def test_render_ready_split_empty_state():
    out = dashboard.render_ready_split(
        {"counts": dict.fromkeys(
            ["never-reviewed", "discussed-no-decision", "changes-requested", "approved"], 0),
         "timeline": {}, "total": 0, "excluded_maintainer": 0}
    )
    assert "No non-maintainer ready PRs" in out
