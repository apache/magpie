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
"""The triage pre-filters and decision table.

Each scenario mirrors a case of the model-graded suites this code replaces
(`tools/skill-evals/evals/pr-management-triage/{pre-filter,decision-table}`),
named after it, so the scripted rules are held to the same expectations.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from pr_management import config, model, people
from pr_management.triage import classify as C

from .helpers import NOW, ago, check, comment, pr, review, thread

READY = "ready for maintainer review"


def _cfg(**kw: Any) -> config.Config:
    cfg = config.Config(real_ci_patterns=[r"Tests", r"Static checks", r"Build"])
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def run(
    *nodes: dict[str, Any],
    cfg: config.Config | None = None,
    viewer: str = "triager",
    action_required: dict[str, list[dict[str, Any]]] | None = None,
    systemic: Iterable[str] = (),
    maintainers: people.Maintainers | None = None,
    authors: str = "default",
    behind: int | None = 0,
) -> list[C.Decision]:
    prs = [model.from_node(n) for n in nodes]
    for p in prs:
        p.commits_behind = behind
    return C.classify(
        prs,
        cfg or _cfg(),
        C.Options(viewer=viewer, now=NOW, authors=authors, sweeps=False),
        maintainers or people.Maintainers(),
        action_required or {},
        set(systemic),
    )


def one(*nodes: dict[str, Any], **kw: Any) -> C.Decision:
    (decision,) = run(*nodes, **kw)
    return decision


# --- pre-filters ----------------------------------------------------------------


def test_clean_contributor_reaches_the_table() -> None:
    assert one(pr()).filter is None


def test_f1_collaborator_author() -> None:
    assert one(pr(author="turboszabo", assoc="MEMBER")).filter == "F1"


def test_f1_lifted_by_authors_all() -> None:
    assert one(pr(author="turboszabo", assoc="MEMBER"), authors="all").filter is None


def test_f2_bot_author() -> None:
    assert one(pr(author="dependabot[bot]", assoc="NONE")).filter == "F2"


def test_row_7a_fresh_pr() -> None:
    d = one(pr(created=ago(minutes=13), updated=ago(minutes=13), committed=ago(minutes=13)))
    assert (d.row, d.action) == ("7a", "skip")


def test_f5a_active_maintainer_comment() -> None:
    d = one(pr(comments=[comment("potiuk", "MEMBER", ago(hours=25), "Please split this")]))
    assert d.filter == "F5a"


def test_row_6_viewer_is_author() -> None:
    d = one(pr(author="potiuk"), viewer="potiuk")
    assert (d.row, d.action) == ("6", "skip")


def test_f3_recent_draft() -> None:
    assert one(pr(draft=True, updated=ago(days=3))).filter == "F3"


def test_f4_already_ready_without_regression() -> None:
    assert one(pr(labels=[READY])).filter == "F4"


def test_f5b_maintainer_ping_unanswered() -> None:
    d = one(pr(comments=[comment("potiuk", "MEMBER", ago(days=4), "@kaxil @mik-laj what do you think?")]))
    assert d.filter == "F5b"


def test_f6_maintainer_co_drafted() -> None:
    d = one(
        pr(
            draft=True,
            updated=ago(days=20),
            committed=ago(days=21),
            reviews=[
                review("kaxil", "COMMENTED", when=ago(days=20), body="Let's restructure the loader first.")
            ],
        )
    )
    assert d.filter == "F6"


def test_f5a_top_level_review_body() -> None:
    d = one(pr(reviews=[review("kaxil", "COMMENTED", when=ago(hours=2), body="Needs a test.")]))
    assert d.filter == "F5a"


def test_f5a_inline_review_comment_only() -> None:
    d = one(pr(threads=[thread(comment("kaxil", "MEMBER", ago(hours=20), "nit"), resolved=True)]))
    assert d.filter == "F5a"


@pytest.mark.parametrize("body", ["   \n", ""])
def test_f5a_ignores_a_review_without_body(body: str) -> None:
    assert one(pr(reviews=[review("kaxil", "APPROVED", when=ago(hours=2), body=body)])).filter is None


def test_f5a_ignores_a_non_maintainer_review() -> None:
    d = one(pr(reviews=[review("other", "COMMENTED", assoc="CONTRIBUTOR", when=ago(hours=2), body="hm")]))
    assert d.filter is None


def test_f5a_needs_the_review_after_the_last_commit() -> None:
    at = ago(hours=10)
    d = one(pr(committed=at, reviews=[review("kaxil", "COMMENTED", when=at, body="Needs a test.")]))
    assert d.filter is None


@pytest.mark.parametrize(("hours", "fires"), [(71, True), (72, False), (73, False)])
def test_f5a_cooldown_is_strictly_under_72h(hours: int, fires: bool) -> None:
    d = one(
        pr(committed=ago(hours=100), reviews=[review("kaxil", "COMMENTED", when=ago(hours=hours), body="x")])
    )
    assert (d.filter == "F5a") is fires


def test_f5a_picks_the_newest_item_before_testing_its_author() -> None:
    d = one(
        pr(
            reviews=[review("kaxil", "COMMENTED", when=ago(hours=30), body="Please add docs")],
            comments=[comment("nina-contributor", when=ago(hours=5), body="Added docs")],
        )
    )
    assert d.filter is None


def test_f5b_ping_answered_by_a_review() -> None:
    d = one(
        pr(
            comments=[comment("potiuk", "MEMBER", ago(days=4), "@kaxil can you look?")],
            reviews=[review("kaxil", "APPROVED", when=ago(days=3), body="")],
        )
    )
    assert d.filter is None


def test_f5c_author_question_to_a_maintainer() -> None:
    m = people.Maintainers(team=frozenset({"kaxil"}))
    d = one(
        pr(comments=[comment("nina-contributor", when=ago(days=4), body="@kaxil is this approach ok?")]),
        maintainers=m,
    )
    assert d.filter == "F5c"


def test_unknown_maintainer_is_resolved_conservatively_and_reported() -> None:
    m = people.Maintainers()
    one(pr(comments=[comment("potiuk", "COLLABORATOR", ago(hours=5), "x")]), maintainers=m)
    assert m.unresolved == {"potiuk"}


def test_read_role_collaborator_is_not_a_maintainer() -> None:
    m = people.Maintainers(permissions={"router": "triage"})
    d = one(pr(comments=[comment("router", "COLLABORATOR", ago(hours=5), "labelled")]), maintainers=m)
    assert d.filter is None


# --- the decision table -----------------------------------------------------------


def test_case_1_passing() -> None:
    d = one(pr())
    assert (d.row, d.classification, d.action) == ("20", "passing", "mark-ready")


def test_case_2_merge_conflict() -> None:
    d = one(pr(mergeable="CONFLICTING"))
    assert (d.row, d.classification, d.action) == ("9", "deterministic_flag", "draft")


def test_case_3_systemic_ci_failure() -> None:
    d = one(pr(rollup="FAILURE", checks=[check("Tests (db)", "FAILURE")]), systemic={"Tests (db)"})
    assert (d.row, d.action) == ("10", "rerun")


def test_case_7_partial_systemic() -> None:
    d = one(
        pr(rollup="FAILURE", checks=[check("Tests (db)", "FAILURE"), check("Tests (api)", "FAILURE")]),
        systemic={"Tests (db)"},
    )
    assert (d.row, d.action) == ("11", "rerun")


def test_case_8_static_only() -> None:
    d = one(pr(rollup="FAILURE", checks=[check("Tests"), check("Static checks: ruff", "FAILURE")]))
    assert (d.row, d.action) == ("12", "comment")


def test_mixed_static_failure() -> None:
    d = one(
        pr(rollup="FAILURE", checks=[check("Static checks: ruff", "FAILURE"), check("Tests (a)", "FAILURE")])
    )
    assert (d.row, d.action) == ("12b", "comment")


def test_case_9_flaky_small() -> None:
    d = one(pr(rollup="FAILURE", checks=[check("Tests (a)", "FAILURE")]))
    assert (d.row, d.action) == ("13", "rerun")


def test_row_13_asks_for_commits_behind() -> None:
    d = one(pr(rollup="FAILURE", checks=[check("Tests (a)", "FAILURE")]), behind=None)
    assert d.outcome == "needs" and d.needs[0]["op"] == "compare-behind"


def test_row_13_far_behind_falls_to_draft() -> None:
    d = one(pr(rollup="FAILURE", checks=[check("Tests (a)", "FAILURE")]), behind=73)
    assert (d.row, d.action) == ("17", "draft")


def test_case_4_unresolved_threads() -> None:
    d = one(pr(committed=ago(days=6), threads=[thread(comment("kaxil", "MEMBER", ago(days=5), "why?"))]))
    assert (d.row, d.action) == ("15", "ping")
    assert "@kaxil" in d.reason


def test_case_12_threads_addressed() -> None:
    d = one(
        pr(
            committed=ago(days=3),
            threads=[
                thread(
                    comment("kaxil", "MEMBER", ago(days=6), "null?"),
                    comment("nina-contributor", when=ago(days=4), body="Fixed"),
                ),
                thread(
                    comment("kaxil", "MEMBER", ago(days=6), "test?"),
                    comment("nina-contributor", when=ago(days=4), body="Done"),
                ),
            ],
        )
    )
    assert (d.row, d.classification, d.action) == ("14c", "deterministic_flag", "request-author-confirmation")


def test_case_5_security_signal() -> None:
    d = one(pr(title="Fix SQL injection in the query builder"))
    assert (d.row, d.classification, d.action) == ("7b", "security_language_signal", "comment")
    assert d.details["security_matches"][0]["where"] == "title"


def test_security_scan_ignores_the_triage_fold() -> None:
    body = "Change.\n<!-- pr-triage-fold: triaged=2026-01-01T00:00:00Z head=0000000 action=comment -->\nCVE-2025-1234 mentioned\n<!-- /pr-triage-fold -->"
    assert one(pr(body=body)).row != "7b"


def test_security_scan_reads_commit_messages() -> None:
    d = one(pr(commit_messages=["Harden parser", "Prevent remote code execution"]))
    assert d.row == "7b"
    assert d.details["security_matches"][0]["where"].startswith("commit")


def test_case_6_no_real_ci() -> None:
    d = one(pr(checks=[check("Mergeable"), check("boring-cyborg")]))
    assert (d.row, d.action) == ("16", "rebase")


def test_first_time_contributor_without_real_ci_goes_to_workflow_approval() -> None:
    d = one(pr(assoc="FIRST_TIME_CONTRIBUTOR", checks=[check("Mergeable")]))
    assert (d.row, d.classification, d.action) == ("1", "pending_workflow_approval", "approve-workflow")


def test_action_required_index_wins() -> None:
    d = one(pr(), action_required={"abc1234def5678": [{"id": 9, "name": "Tests"}]})
    assert d.row == "1" and d.details["runs"] == [{"id": 9, "name": "Tests"}]


def test_case_10_author_confirmed() -> None:
    d = one(
        pr(
            committed=ago(days=6),
            comments=[
                comment(
                    "triager", "MEMBER", ago(days=5), "Is this ready for maintainer review confirmation?"
                ),
                comment("nina-contributor", when=ago(days=4), body="yes, ready"),
            ],
        )
    )
    assert (d.row, d.classification, d.action) == ("14a", "author_confirmed_ready", "mark-ready")


def test_case_11_awaiting_confirmation() -> None:
    d = one(
        pr(
            committed=ago(days=6),
            comments=[comment("triager", "MEMBER", ago(days=4), "ready for maintainer review confirmation?")],
        )
    )
    assert (d.row, d.classification, d.action) == ("14b", "awaiting_author_confirmation", "skip")


def test_confirmation_request_folded_into_the_body() -> None:
    body = (
        "Change.\n<!-- pr-triage-fold: triaged="
        + ago(days=4)
        + " head=abc1234 action=request-author-confirmation by=triager -->\nready for maintainer review confirmation\n<!-- /pr-triage-fold -->"
    )
    d = one(pr(body=body, committed=ago(days=6)))
    assert d.row == "14b"


def test_case_13_changes_requested() -> None:
    d = one(
        pr(committed=ago(days=3), reviews=[review("kaxil", "CHANGES_REQUESTED", when=ago(days=5), body="")])
    )
    assert (d.row, d.classification, d.action) == ("18", "stale_review", "ping")


def test_stale_review_waits_for_a_fresh_push() -> None:
    d = one(
        pr(committed=ago(hours=5), reviews=[review("kaxil", "CHANGES_REQUESTED", when=ago(days=5), body="")])
    )
    assert d.row != "18"


def test_case_14_already_ready() -> None:
    assert one(pr(labels=[READY])).filter == "F4"


def test_row_19_ready_label_with_a_regression_window() -> None:
    d = one(
        pr(
            labels=[READY],
            rollup="FAILURE",
            checks=[check("Tests (a)", "FAILURE", started=ago(days=1))],
            label_events=[{"__typename": "LabeledEvent", "createdAt": ago(days=2), "label": {"name": READY}}],
        )
    )
    assert d.row == "13"


def test_case_16_rollup_anomaly() -> None:
    d = one(pr(rollup="FAILURE", checks=[check("Tests (a)", "CANCELLED")]))
    assert (d.row, d.action) == ("22", "skip")


def test_case_19_unknown_mergeable() -> None:
    d = one(pr(mergeable="UNKNOWN"))
    assert (d.row, d.action) == ("22", "skip")
    assert "Mergeability" in d.reason


def _fold(head: str, when: str, by: str | None = "maya-triager") -> str:
    by_part = f" by={by}" if by else ""
    return (
        f"Change.\n<!-- pr-triage-fold: triaged={when} head={head} action=draft{by_part} -->\n"
        "See the [Pull Request quality criteria](https://x)\n<!-- /pr-triage-fold -->"
    )


def test_case_17_fold_already_triaged() -> None:
    d = one(pr(body=_fold("abc1234", ago(days=2)), mergeable="CONFLICTING"))
    assert (d.row, d.classification) == ("3", "already_triaged")
    assert "`maya-triager`" in d.reason


def test_case_18_fold_stale_after_push() -> None:
    d = one(pr(body=_fold("0000000", ago(days=2)), mergeable="CONFLICTING"))
    assert d.row == "9"


def test_case_20_comment_marker_by_other_maintainer() -> None:
    d = one(
        pr(
            mergeable="CONFLICTING",
            committed=ago(days=4),
            comments=[comment("other-maint", "MEMBER", ago(days=3), "See Pull Request quality criteria")],
        ),
        maintainers=people.Maintainers(permissions={"other-maint": "write"}),
    )
    assert d.row == "3"


def test_case_21_non_triager_comment_is_not_a_marker() -> None:
    d = one(
        pr(
            mergeable="CONFLICTING",
            committed=ago(days=4),
            comments=[comment("random", "CONTRIBUTOR", ago(days=3), "Pull Request quality criteria says")],
        )
    )
    assert d.row == "9"


def test_case_22_fold_by_another_triager_without_by() -> None:
    d = one(pr(body=_fold("abc1234", ago(days=2), by=None), mergeable="CONFLICTING"))
    assert d.row == "3" and " by " not in d.reason


def test_case_15_stale_draft_deferred_to_sweep() -> None:
    d = one(pr(draft=True, updated=ago(days=20), committed=ago(days=30), body=_fold("abc1234", ago(days=20))))
    assert (d.row, d.classification, d.action) == ("5", "stale_draft", "defer-sweep")


def test_row_0_first_time_abandoned() -> None:
    d = one(
        pr(
            assoc="FIRST_TIME_CONTRIBUTOR",
            committed=ago(days=60),
            body=_fold("abc1234", ago(days=50)),
            checks=[check("Mergeable")],
        ),
    )
    assert (d.row, d.classification) == ("0", "first_time_stale_abandoned")


def test_row_2_stale_copilot_review() -> None:
    d = one(
        pr(
            committed=ago(days=12),
            threads=[thread(comment("copilot-pull-request-reviewer", "NONE", ago(days=10), "bug"))],
        )
    )
    assert (d.row, d.classification, d.action) == ("2", "stale_copilot_review", "draft")


def test_row_8_author_with_many_flagged_prs_gets_close() -> None:
    nodes = [pr(n, mergeable="CONFLICTING", author="spammer", head=f"{n:07d}aaaa") for n in range(1, 6)]
    assert {d.action for d in run(*nodes)} == {"close"}


def test_truncated_rollup_page_asks_for_the_rest_list() -> None:
    d = one(pr(rollup="FAILURE", checks=[check("Tests (a)", "FAILURE")], contexts_total=80))
    assert d.outcome == "needs" and d.needs[0] == {
        "op": "check-runs",
        "params": ["abc1234def5678"],
        "save": "check-runs-1.json",
    }


def test_grace_window_defers_a_fresh_failure() -> None:
    d = one(pr(rollup="FAILURE", checks=[check("Tests (a)", "FAILURE", started=ago(hours=3))]))
    assert d.row == "grace" and d.outcome == "skip"


# --- strip-ready-on-downgrade and the merit-discussion exception ------------------


def _regressed(**kw: Any) -> dict[str, Any]:
    return pr(
        labels=[READY],
        mergeable="CONFLICTING",
        label_events=[{"__typename": "LabeledEvent", "createdAt": ago(days=4), "label": {"name": READY}}],
        **kw,
    )


def test_regressed_ready_pr_strips_the_label() -> None:
    d = one(_regressed())
    assert d.action == "draft" and d.details["strip_ready_label"]


def test_merit_discussion_keeps_the_label_and_degrades_draft_to_comment() -> None:
    d = one(
        _regressed(
            committed=ago(days=6), threads=[thread(comment("kaxil", "MEMBER", ago(days=5), "Design?"))]
        )
    )
    assert d.action == "comment"
    assert d.details["degraded_from"] == "draft" and not d.details["strip_ready_label"]
    assert d.details["merit_discussion"]


def test_collaborator_mode_never_drafts() -> None:
    d = one(pr(author="m", assoc="MEMBER", mergeable="CONFLICTING"), authors="collaborators")
    assert d.action == "comment"
