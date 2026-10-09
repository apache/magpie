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

"""Tests for the explicit partial-schema classify contract.

PR #348 review flagged the old `pr.setdefault(...)` block as silently papering
over the reduced closed-PR schema. The contract is now explicit:
classify(partial=True) reads the heavy engagement collections defensively, and
the closed-PR query selects isDraft so direct reads stay safe.
"""

from __future__ import annotations

from pr_management.stats import reference

from .helpers import comment, make_ctx, make_pr


def test_partial_closed_pr_classifies_without_engagement_collections():
    ctx = make_ctx()
    # include_engagement=False → no commits/latestReviews/reviewThreads/timelineItems
    pr = make_pr(
        1,
        assoc="NONE",
        created_days_ago=20,
        closed_days_ago=2,
        include_engagement=False,
    )
    reference.classify(pr, ctx, partial=True)

    assert pr["_author"] == "contributor"
    assert pr["_is_contrib"] is True
    assert pr["_is_engaged"] is False  # no collab signal in the comments


def test_partial_classify_tolerates_missing_isdraft_key():
    """Even if a node omits isDraft entirely, classify must not KeyError."""
    ctx = make_ctx()
    pr = make_pr(2, assoc="NONE", include_engagement=False)
    del pr["isDraft"]

    reference.classify(pr, ctx, partial=True)  # must not raise

    assert "_is_untriaged" in pr


def test_partial_classify_still_detects_collab_engagement_from_comments():
    ctx = make_ctx()
    pr = make_pr(
        3,
        assoc="NONE",
        include_engagement=False,
        closed_days_ago=1,
        comments=[comment("looks good", author="maint", assoc="MEMBER")],
    )
    reference.classify(pr, ctx, partial=True)
    assert pr["_is_engaged"] is True
