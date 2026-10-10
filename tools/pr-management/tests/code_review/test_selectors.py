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
"""Selector parsing and the my-reviews queue.

Mirrors the retired `selector-resolution` and `step-1-selectors-match-chips`
eval suites case by case.
"""

from __future__ import annotations

import pytest

from pr_management import config
from pr_management.code_review import codeowners, selectors

from .builders import NOW, ago, check, commit, pr, review

FIVE = ["review-requested", "touching-mine", "codeowner", "mentioned", "reviewed-before"]


def _subset(parsed: selectors.Selector, **expected: object) -> None:
    got = parsed.as_dict()
    for key, value in expected.items():
        assert got[key] == value, key


# --- selector-resolution ------------------------------------------------------------------


def test_case_1_single_pr() -> None:
    _subset(
        selectors.parse(["pr:65981"]),
        mode="single-pr",
        pr_number=65981,
        area_label=None,
        collab=None,
        team=None,
        signals=[],
        max=None,
        dry_run=False,
        inline="on",
    )


def test_case_2_composed_flags() -> None:
    _subset(
        selectors.parse(["area:scheduler", "collab:false", "max:5"]),
        mode="area",
        pr_number=None,
        area_label="area:scheduler",
        collab="non-collaborator",
        team=None,
        signals=FIVE,
        max=5,
        dry_run=False,
        inline="on",
    )


def test_case_3_default_no_args() -> None:
    _subset(selectors.parse([]), mode="my-reviews", signals=FIVE, max=None, dry_run=False, inline="on")


def test_case_4_ready_with_negation() -> None:
    _subset(
        selectors.parse(["requested-only", "dry-run", "inline:off"]),
        mode="my-reviews",
        signals=["review-requested"],
        dry_run=True,
        inline="off",
    )


def test_negatives_compose() -> None:
    assert selectors.parse(["no-touching-mine", "no-mentioned"]).signals == [
        "review-requested",
        "codeowner",
        "reviewed-before",
    ]


@pytest.mark.parametrize(("arg", "days"), [("since:7d", 7), ("since:2w", 14), ("since:90d", 90)])
def test_since_windows(arg: str, days: int) -> None:
    assert selectors.parse([arg]).since_days == days


def test_unknown_flags_are_refused() -> None:
    with pytest.raises(selectors.SelectorError):
        selectors.parse(["approve-everything"])


# --- step-1 match chips -----------------------------------------------------------------------


RULES = codeowners.parse("airflow/core/serde.py @alice\nairflow/core/executors/ @alice\n")


def _queue(
    *nodes: selectors.PR, sel: selectors.Selector | None = None, active: set[str] | None = None
) -> list[selectors.Entry]:
    return selectors.queue(
        list(nodes),
        sel or selectors.parse([]),
        config.Config(real_ci_patterns=["Tests"]),
        "alice",
        active or set(),
        RULES,
        set(),
        NOW,
    )


def test_case_1_multiple_signals() -> None:
    (entry,) = _queue(
        pr(number=6101, requested=["alice"], files=["airflow/core/serde.py", "airflow/www/views.py"]),
        active={"airflow/cli/commands/user_command.py", "airflow/core/serde.py"},
    )
    assert entry.chips[:3] == [
        "review-requested",
        "touches: airflow/core/serde.py",
        "codeowner: airflow/core/serde.py",
    ]


def test_case_2_mentioned_in_comment() -> None:
    (entry,) = _queue(
        pr(
            number=6102,
            requested=["bob"],
            files=["airflow/cli/commands/connection_command.py"],
            comments=[("bob", "@alice can you sanity-check the CLI flag names?")],
        ),
        active={"airflow/cli/commands/user_command.py"},
    )
    assert entry.chips[0] == "mentioned-in: comment"


def test_case_3_triage_comment_is_not_reviewed_before() -> None:
    assert (
        _queue(
            pr(
                number=6103,
                requested=["carol"],
                files=["airflow/utils/log/file_processor_handler.py"],
                comments=[("alice", "Rebased and reran CI.")],
            ),
            active={"airflow/api/auth.py"},
        )
        == []
    )


def test_case_4_draft_excluded() -> None:
    assert (
        _queue(
            pr(
                number=6104,
                draft=True,
                requested=["alice"],
                files=["airflow/core/executors/base_executor.py"],
                body="@alice early thoughts welcome",
            ),
            active={"airflow/core/executors/base_executor.py"},
        )
        == []
    )


def test_mention_is_word_bounded() -> None:
    assert _queue(pr(body="ping @alice-bot or email@alice.com")) == []


def test_reviewed_before_uses_real_reviews() -> None:
    (entry,) = _queue(pr(reviews=[review("alice", "COMMENTED", when=ago(days=4))]))
    assert entry.chips[0] == "reviewed-before: 4 days ago"


def test_last_codeowners_rule_wins() -> None:
    rules = codeowners.parse("src/ @alice\n* @someone-else\n")
    assert codeowners.owners_of(rules, "src/a.py") == ("@someone-else",)


def test_team_ownership_needs_team_membership() -> None:
    rules = codeowners.parse("/scheduler/ @acme/core\n")
    entries = selectors.queue(
        [pr(files=["scheduler/job.py"])],
        selectors.parse([]),
        config.Config(),
        "alice",
        set(),
        rules,
        {"acme/core"},
        NOW,
    )
    assert entries[0].chips[0] == "codeowner: scheduler/job.py"


def test_filters_apply_to_the_union() -> None:
    nodes = [
        pr(number=1, requested=["alice"], labels=["area:scheduler"], assoc="CONTRIBUTOR"),
        pr(number=2, requested=["alice"], labels=["area:api"]),
        pr(number=3, requested=["alice"], labels=["area:scheduler"], assoc="MEMBER"),
    ]
    got = _queue(*nodes, sel=selectors.parse(["area:scheduler", "collab:false"]))
    assert [e.pr.number for e in got] == [1]


def test_area_wildcard() -> None:
    assert selectors.matches_area(("provider:amazon",), "provider*")


def test_no_real_ci_ranks_last_and_prior_approval_auto_skips() -> None:
    entries = _queue(
        pr(number=1, requested=["alice"], checks=[check("Mergeable")], updated=ago(hours=1)),
        pr(number=2, requested=["alice"], updated=ago(days=2)),
        pr(number=3, requested=["alice"], reviews=[review("alice", "APPROVED", commit_oid="abc1234def")]),
        pr(number=4, requested=["alice"], reviews=[review("alice", "APPROVED", commit_oid="0000000")]),
    )
    # Real CI first, newest update first; the bot-only PR goes last however fresh it is.
    assert [e.pr.number for e in entries] == [3, 4, 2, 1]
    by = {e.pr.number: e for e in entries}
    assert by[3].skip == "prior-approval-current-sha"
    assert by[4].ask == "prior-approval-stale-sha"
    assert not by[1].real_ci


def test_team_selector_matches_the_requested_team() -> None:
    got = _queue(
        pr(requested_teams=["acme/providers"]), pr(number=2), sel=selectors.parse(["team:providers"])
    )
    assert [e.pr.number for e in got] == [1]


def test_commits_are_scanned_for_mentions() -> None:
    (entry,) = _queue(pr(commits=[commit("Thanks @alice for the idea")]))
    assert entry.chips[0] == "mentioned-in: commit"
