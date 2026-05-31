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
"""Rule-by-rule tests for the pre-flight classifier.

Each rule from `bulk-mode.md` § Pre-flight no-op classifier has at
least one focused test covering the positive case (rule fires) and
one negative case (rule does not fire). When the rule table grows,
add the matching `test_rule_N_*` here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from preflight_audit.classifier import (
    Decision,
    IssueState,
    classify_issue,
    classify_response,
)

NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)


def make_issue(
    *,
    number: int = 100,
    state: str = "OPEN",
    closed_days_ago: float | None = None,
    updated_days_ago: float = 30.0,
    labels: frozenset[str] = frozenset(),
    last_comment_author: str | None = None,
    last_comment_days_ago: float | None = None,
    last_comment_body: str | None = None,
) -> IssueState:
    return IssueState(
        number=number,
        state=state,
        closed_at=(NOW - timedelta(days=closed_days_ago)) if closed_days_ago is not None else None,
        updated_at=NOW - timedelta(days=updated_days_ago),
        labels=labels,
        last_comment_author=last_comment_author,
        last_comment_created_at=(
            NOW - timedelta(days=last_comment_days_ago) if last_comment_days_ago is not None else None
        ),
        last_comment_body=last_comment_body,
    )


# ---------------------------------------------------------------------------
# Rule 1 — 7-day updatedAt safety override
# ---------------------------------------------------------------------------


def test_rule_1_dispatches_when_human_activity_in_last_7d():
    iss = make_issue(
        updated_days_ago=2.0,
        last_comment_author="someone",
        last_comment_days_ago=2.0,
        last_comment_body="real comment\n",
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.DISPATCH
    assert "recent human activity" in c.reason


def test_rule_1_skipped_when_skill_drove_recent_update():
    """A recent-only-because-the-skill-wrote update should NOT
    block downstream skip rules from firing."""
    iss = make_issue(
        state="OPEN",
        updated_days_ago=1.0,
        labels=frozenset({"cve allocated", "fix released"}),
        last_comment_author="potiuk",
        last_comment_days_ago=1.0,
        last_comment_body="<!-- apache-steward: release-manager-handoff v1 -->\nbody",
    )
    c = classify_issue(iss, now=NOW)
    # Rule 7 should fire because Rule 1 yielded.
    assert c.decision == Decision.SKIP_NOOP
    assert "fix released" in c.reason


# ---------------------------------------------------------------------------
# Rule 2 — dispatch-urgent (non-skill comment in last 24h)
# ---------------------------------------------------------------------------


def test_rule_2_urgent_when_non_skill_comment_under_24h():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=0.5,
        last_comment_author="reporter",
        last_comment_days_ago=0.5,
        last_comment_body="please re-check\n",
    )
    c = classify_issue(iss, now=NOW)
    # Rule 1 fires first (recent human activity); urgent is only
    # reachable when Rule 1 yielded — i.e., when the recent activity
    # was the skill. So the urgent path needs a non-skill comment
    # AFTER a skill update? Actually the rule is "Rule 1 yielded AND
    # Rule 2 fires" which happens when last comment is recent AND
    # not skill — but then Rule 1 ALSO doesn't yield, since it
    # requires skill-drove-recent-update. Both fail; we end up at
    # Rule 1's dispatch. That matches the prose: urgent is the
    # bot-vs-not distinction; when the last comment is a human reply
    # in the last 24h, the classifier dispatches (with the urgent
    # tag) if-and-only-if there is no other reason to dispatch.
    # In this synthetic case Rule 1 catches first → dispatch
    # without urgent. That's correct behaviour.
    assert c.decision == Decision.DISPATCH


def test_rule_2_urgent_path_after_skill_only_recent_activity():
    """Construct a case where Rule 1 yields (skill drove update) but
    the LAST comment is still a non-skill recent reply. Tricky
    construction: a non-skill last comment within 24h, but updatedAt
    older than 7d — Rule 1 won't fire at all, then Rule 2 catches."""
    iss = make_issue(
        state="OPEN",
        updated_days_ago=10.0,  # >7d so Rule 1 doesn't fire
        last_comment_author="reporter",
        last_comment_days_ago=0.5,
        last_comment_body="any update?\n",
    )
    # updated_days_ago=10 but last_comment_days_ago=0.5 is
    # internally inconsistent (a real GitHub response would have
    # updatedAt >= last comment time), but the classifier handles
    # it gracefully — Rule 1 skips, Rule 2 fires.
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.DISPATCH_URGENT
    assert "reporter" in c.reason


def test_rule_2_not_urgent_when_skill_comment():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=10.0,
        last_comment_author="potiuk",
        last_comment_days_ago=0.5,
        last_comment_body="<!-- apache-steward: status-rollup v1 -->\nentry\n",
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision != Decision.DISPATCH_URGENT


# ---------------------------------------------------------------------------
# Rule 3 — closed > 30d + announced → post-announce
# ---------------------------------------------------------------------------


def test_rule_3_skip_post_announce():
    iss = make_issue(
        state="CLOSED",
        closed_days_ago=40.0,
        updated_days_ago=40.0,
        labels=frozenset({"announced", "cve allocated"}),
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.SKIP_NOOP
    assert "post-announce" in c.reason


def test_rule_3_no_skip_recently_closed():
    iss = make_issue(
        state="CLOSED",
        closed_days_ago=10.0,
        updated_days_ago=10.0,
        labels=frozenset({"announced"}),
    )
    c = classify_issue(iss, now=NOW)
    # 10d < 30d threshold; downstream falls through to dispatch.
    assert c.decision == Decision.DISPATCH


def test_rule_3_no_skip_no_announce_label():
    iss = make_issue(
        state="CLOSED",
        closed_days_ago=40.0,
        updated_days_ago=40.0,
        labels=frozenset({"cve allocated"}),
    )
    c = classify_issue(iss, now=NOW)
    # No `announced` → Rule 3 doesn't fire; Rule 4 wants > 90d.
    assert c.decision == Decision.DISPATCH


# ---------------------------------------------------------------------------
# Rule 4 — closed > 90d no announce → stale
# ---------------------------------------------------------------------------


def test_rule_4_skip_stale_closed():
    iss = make_issue(
        state="CLOSED",
        closed_days_ago=120.0,
        updated_days_ago=120.0,
        labels=frozenset({"invalid"}),
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.SKIP_NOOP
    assert "stale closed" in c.reason


def test_rule_4_no_skip_if_announced():
    iss = make_issue(
        state="CLOSED",
        closed_days_ago=120.0,
        updated_days_ago=120.0,
        labels=frozenset({"announced"}),
    )
    c = classify_issue(iss, now=NOW)
    # Rule 3 catches first.
    assert c.decision == Decision.SKIP_NOOP
    assert "post-announce" in c.reason


# ---------------------------------------------------------------------------
# Rule 5 — open + full lifecycle + skill-last → awaiting closure
# ---------------------------------------------------------------------------


def test_rule_5_skip_full_lifecycle_skill_last():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=2.0,
        labels=frozenset({"cve allocated", "pr merged", "announced"}),
        last_comment_author="potiuk",
        last_comment_days_ago=2.0,
        last_comment_body="<!-- apache-steward: status-rollup v1 -->\nentry",
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.SKIP_NOOP
    assert "all phases done" in c.reason


def test_rule_5_no_skip_when_last_human():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=2.0,
        labels=frozenset({"cve allocated", "pr merged", "announced"}),
        last_comment_author="reporter",
        last_comment_days_ago=2.0,
        last_comment_body="real reply\n",
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.DISPATCH


# ---------------------------------------------------------------------------
# Rule 6 — open + cve+pr + skill-last → awaiting release
# ---------------------------------------------------------------------------


def test_rule_6_skip_awaiting_release():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=2.0,
        labels=frozenset({"cve allocated", "pr merged"}),
        last_comment_author="potiuk",
        last_comment_days_ago=2.0,
        last_comment_body="<!-- apache-steward: status-rollup v1 -->\n",
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.SKIP_NOOP
    assert "awaiting release" in c.reason


# ---------------------------------------------------------------------------
# Rule 7 — open + cve+fix-released + skill-last → awaiting advisory
# ---------------------------------------------------------------------------


def test_rule_7_skip_awaiting_advisory():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=1.0,
        labels=frozenset({"cve allocated", "fix released"}),
        last_comment_author="potiuk",
        last_comment_days_ago=1.0,
        last_comment_body="<!-- apache-steward: release-manager-handoff v1 -->\n",
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.SKIP_NOOP
    assert "awaiting advisory" in c.reason


# ---------------------------------------------------------------------------
# Skill-or-bot detection
# ---------------------------------------------------------------------------


def test_bot_login_detected():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=2.0,
        labels=frozenset({"cve allocated", "fix released"}),
        last_comment_author="github-actions[bot]",
        last_comment_days_ago=2.0,
        last_comment_body="CI passed\n",
    )
    c = classify_issue(iss, now=NOW)
    assert c.last_is_skill_or_bot is True
    assert c.decision == Decision.SKIP_NOOP


def test_dependabot_login_detected():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=2.0,
        labels=frozenset({"cve allocated", "fix released"}),
        last_comment_author="dependabot[bot]",
        last_comment_days_ago=2.0,
        last_comment_body="bumped\n",
    )
    c = classify_issue(iss, now=NOW)
    assert c.last_is_skill_or_bot is True


def test_skill_marker_detected_regardless_of_author():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=2.0,
        labels=frozenset({"cve allocated", "fix released"}),
        last_comment_author="some-user",
        last_comment_days_ago=2.0,
        last_comment_body="<!-- apache-steward: status-rollup v1 -->\nentry",
    )
    c = classify_issue(iss, now=NOW)
    assert c.last_is_skill_or_bot is True


def test_extra_bot_login_override():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=2.0,
        labels=frozenset({"cve allocated", "fix released"}),
        last_comment_author="company-private-bot",
        last_comment_days_ago=2.0,
        last_comment_body="hello\n",
    )
    c = classify_issue(iss, now=NOW, extra_bot_logins=frozenset({"company-private-bot"}))
    assert c.last_is_skill_or_bot is True


def test_real_human_not_detected_as_bot():
    iss = make_issue(
        last_comment_author="reporter-jane",
        last_comment_body="this is broken\n",
    )
    c = classify_issue(iss, now=NOW)
    assert c.last_is_skill_or_bot is False


# ---------------------------------------------------------------------------
# classify_response — end-to-end with a synthetic GraphQL shape
# ---------------------------------------------------------------------------


def test_classify_response_handles_empty_repo():
    assert classify_response({"data": {"repository": {}}}, now=NOW) == []


def test_classify_response_skips_null_nodes():
    response: dict = {
        "data": {
            "repository": {
                "i1": None,
                "i2": {
                    "number": 2,
                    "state": "OPEN",
                    "closedAt": None,
                    "updatedAt": "2025-01-01T00:00:00Z",
                    "labels": {"nodes": [{"name": "needs triage"}]},
                    "comments": {"nodes": []},
                },
            }
        }
    }
    results = classify_response(response, now=NOW)
    assert len(results) == 1
    assert results[0].issue.number == 2


def test_classify_response_parses_iso_timestamps():
    response: dict = {
        "data": {
            "repository": {
                "i9": {
                    "number": 9,
                    "state": "CLOSED",
                    "closedAt": "2026-03-15T10:00:00Z",
                    "updatedAt": "2026-03-15T10:00:00Z",
                    "labels": {"nodes": [{"name": "announced"}]},
                    "comments": {"nodes": []},
                }
            }
        }
    }
    results = classify_response(response, now=NOW)
    assert len(results) == 1
    assert results[0].decision == Decision.SKIP_NOOP
    assert "post-announce" in results[0].reason


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_last_comment_falls_through_to_dispatch():
    iss = make_issue(
        state="OPEN",
        updated_days_ago=30.0,
        labels=frozenset({"cve allocated"}),
    )
    c = classify_issue(iss, now=NOW)
    assert c.decision == Decision.DISPATCH
    assert c.last_is_skill_or_bot is False


@pytest.mark.parametrize(
    "body,expected_skill",
    [
        ("<!-- apache-steward: x v1 -->", True),
        ("  \n<!-- apache-steward: x v1 -->", True),  # leading whitespace
        ("<!-- apache-steward:x -->", False),  # missing space after colon
        ("real reply\n<!-- apache-steward: x -->", False),  # not at start
        ("", False),
        (None, False),
    ],
)
def test_skill_marker_match_precision(body, expected_skill):
    iss = make_issue(
        last_comment_author="potiuk",
        last_comment_days_ago=5.0,
        last_comment_body=body,
    )
    c = classify_issue(iss, now=NOW)
    assert c.last_is_skill_or_bot is expected_skill
