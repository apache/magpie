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
"""The retired model-graded pr-management-stats suites, as code.

One test per former case of `tools/skill-evals/evals/pr-management-stats/`
(`classify` and `pressure-weight`), named after it, with the same scenario
and the same expected outcome.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pr_management.stats import reference

from .helpers import make_ctx

QC = "[Pull Request quality criteria](https://example.org/quality#criteria)"


def _pr(author, *, assoc="CONTRIBUTOR", committed, comments=(), created=None, draft=False, labels=()):
    return {
        "number": 1,
        "title": "t",
        "isDraft": draft,
        "createdAt": created or "2026-04-01T00:00:00Z",
        "author": {"login": author},
        "authorAssociation": assoc,
        "labels": {"nodes": [{"name": n} for n in labels]},
        "commits": {"nodes": [{"commit": {"oid": "abc1234", "committedDate": committed}}]},
        "comments": {
            "nodes": [
                {"author": {"login": a}, "authorAssociation": s, "createdAt": t, "body": b}
                for a, s, t, b in comments
            ]
        },
        "latestReviews": {"nodes": []},
        "reviewThreads": {"nodes": []},
        "timelineItems": {"nodes": []},
    }


def _status(pr, now="2026-05-20T00:00:00Z"):
    ctx = make_ctx(now=datetime.fromisoformat(now.replace("Z", "+00:00")))
    reference.classify(pr, ctx)
    if not pr["_is_triaged"]:
        return "untriaged", None
    state = "triaged_responded" if pr["_responded"] else "triaged_waiting"
    return state, pr["_triage_at"].isoformat().replace("+00:00", "Z")


# --- classify ------------------------------------------------------------------


def test_case_1_untriaged():
    assert _status(_pr("alice", committed="2026-05-10T08:00:00Z")) == ("untriaged", None)


def test_case_2_triaged_waiting():
    pr = _pr(
        "bob",
        committed="2026-05-08T10:00:00Z",
        comments=[("potiuk", "MEMBER", "2026-05-09T14:00:00Z", QC + "\n\nThe PR is missing unit tests.")],
    )
    assert _status(pr) == ("triaged_waiting", "2026-05-09T14:00:00Z")


def test_case_3_triaged_responded_comment():
    pr = _pr(
        "carol",
        committed="2026-05-05T09:00:00Z",
        comments=[
            ("kaxil", "COLLABORATOR", "2026-05-06T11:00:00Z", "Please see the " + QC + "."),
            ("carol", "CONTRIBUTOR", "2026-05-07T08:30:00Z", "Done, updated the title."),
        ],
    )
    assert _status(pr) == ("triaged_responded", "2026-05-06T11:00:00Z")


def test_case_4_triaged_responded_commit():
    pr = _pr(
        "dave",
        committed="2026-05-13T16:00:00Z",
        comments=[("potiuk", "MEMBER", "2026-05-11T10:00:00Z", QC + "\n\nPlease rebase.")],
    )
    assert _status(pr) == ("triaged_responded", "2026-05-11T10:00:00Z")


def test_case_5_stale_marker():
    """A post-triage push counts as a response, not as a stale marker."""
    pr = _pr(
        "eve",
        committed="2026-05-15T09:00:00Z",
        comments=[("potiuk", "MEMBER", "2026-05-10T12:00:00Z", QC + "\n\nMissing CHANGELOG entry.")],
    )
    assert _status(pr) == ("triaged_responded", "2026-05-10T12:00:00Z")


def test_case_6_legacy_html_marker():
    pr = _pr(
        "frank",
        committed="2026-04-20T14:00:00Z",
        comments=[
            (
                "jlowin",
                "OWNER",
                "2026-04-22T09:00:00Z",
                "Closing due to inactivity.\n<!-- Pull Request quality criteria -->",
            ),
        ],
    )
    assert _status(pr) == ("triaged_waiting", "2026-04-22T09:00:00Z")


# --- pressure weight -----------------------------------------------------------

NOW = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)


def _weight(pr):
    reference.classify(pr, make_ctx(now=NOW))
    return reference.pressure_weight(pr, NOW)


def test_case_1_collaborator():
    assert (
        _weight(_pr("m", assoc="MEMBER", committed="2026-05-17T10:00:00Z", created="2026-05-17T10:00:00Z"))
        == 0
    )


def test_case_2_ready_for_review():
    pr = _pr(
        "c",
        committed="2026-05-06T08:00:00Z",
        labels=["ready for maintainer review", "area:providers"],
        comments=[("m", "MEMBER", "2026-05-05T10:00:00Z", QC)],
    )
    assert _weight(pr) == 1


def test_case_3_stale_triaged():
    pr = _pr(
        "c",
        assoc="FIRST_TIME_CONTRIBUTOR",
        committed="2026-05-07T14:00:00Z",
        labels=["area:core"],
        comments=[("m", "MEMBER", "2026-05-08T10:00:00Z", QC)],
    )
    assert _weight(pr) == 2


def test_case_4_draft():
    assert (
        _weight(_pr("c", draft=True, committed="2026-05-16T10:00:00Z", created="2026-05-16T10:00:00Z")) == 0
    )


def test_case_5_untriaged_very_old():
    assert (
        _weight(_pr("c", assoc="NONE", committed="2026-04-12T08:00:00Z", created="2026-04-12T08:00:00Z")) == 5
    )


def test_case_6_untriaged_fresh():
    pr = _pr(
        "c", assoc="FIRST_TIME_CONTRIBUTOR", committed="2026-05-16T15:00:00Z", created="2026-05-16T15:00:00Z"
    )
    assert _weight(pr) == 1


def test_case_7_untriaged_week_old():
    assert _weight(_pr("c", committed="2026-05-08T10:00:00Z", created="2026-05-08T10:00:00Z")) == 3


def test_ready_takes_precedence_over_a_stale_triaged_draft():
    pr = _pr(
        "c",
        draft=True,
        committed="2026-05-01T10:00:00Z",
        labels=["ready for maintainer review"],
        comments=[("m", "MEMBER", "2026-05-02T10:00:00Z", QC)],
    )
    assert _weight(pr) == 1


def test_the_pr_author_quoting_the_marker_is_not_a_triage_marker():
    pr = _pr(
        "c",
        assoc="COLLABORATOR",
        committed="2026-05-01T10:00:00Z",
        comments=[("c", "COLLABORATOR", "2026-05-02T10:00:00Z", QC)],
    )
    assert _status(pr) == ("untriaged", None)


def test_a_fold_counts_and_a_stale_fold_head_counts_as_responded():
    body = "x\n<!-- pr-triage-fold: triaged=2026-05-09T00:00:00Z head=fffffff action=draft -->\nn\n<!-- /pr-triage-fold -->"
    pr = _pr("c", committed="2026-05-08T00:00:00Z")
    pr["body"] = body
    assert _status(pr) == ("triaged_responded", "2026-05-09T00:00:00Z")


def test_a_folded_confirmation_request_is_not_a_triage_marker():
    body = (
        "<!-- pr-triage-fold: triaged=2026-05-09T00:00:00Z head=abc1234 action=request-author-confirmation -->"
        "\nready for maintainer review confirmation\n<!-- /pr-triage-fold -->"
    )
    pr = _pr("c", committed="2026-05-08T00:00:00Z")
    pr["body"] = body
    assert _status(pr)[0] == "untriaged"
