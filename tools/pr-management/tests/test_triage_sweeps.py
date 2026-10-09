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
"""Step 0.5 bot-draft promotion and the Step 5 stale sweeps (stale-sweeps.md)."""

from __future__ import annotations

from typing import Any

from pr_management import config, model, people
from pr_management.triage import classify as C
from pr_management.triage import sweeps

from .helpers import NOW, ago, check, comment, pr, review, thread

READY = "ready for maintainer review"


def _cfg() -> config.Config:
    return config.Config(real_ci_patterns=[r"Tests", r"Static checks", r"Build"])


def run(
    *nodes: dict[str, Any],
    viewer: str = "triager",
    action_required: dict[str, list[dict[str, Any]]] | None = None,
    maintainers: people.Maintainers | None = None,
    liveness: dict[int, dict[str, Any]] | None = None,
) -> list[C.Decision]:
    prs = [model.from_node(n) for n in nodes]
    for p in prs:
        p.commits_behind = 0
        if liveness and p.number in liveness:
            p.extra["liveness"] = liveness[p.number]
    return C.classify(
        prs,
        _cfg(),
        C.Options(viewer=viewer, now=NOW),
        maintainers or people.Maintainers(),
        action_required or {},
        set(),
    )


def one(*nodes: dict[str, Any], **kw: Any) -> C.Decision:
    (decision,) = run(*nodes, **kw)
    return decision


def fold(head: str, when: str, action: str = "draft") -> str:
    return (
        f"Change.\n<!-- pr-triage-fold: triaged={when} head={head} action={action} by=triager -->\n"
        "[Pull Request quality criteria](https://x)\n<!-- /pr-triage-fold -->"
    )


def labelled(days: float) -> list[dict[str, Any]]:
    return [{"__typename": "LabeledEvent", "createdAt": ago(days=days), "label": {"name": READY}}]


def live(
    mergeable: str = "MERGEABLE", state: str = "BLOCKED", head: str = "abc1234def5678"
) -> dict[str, Any]:
    return {
        "data": {
            "repository": {
                "pullRequest": {"headRefOid": head, "mergeable": mergeable, "mergeStateStatus": state}
            }
        }
    }


def _live(doc: dict[str, Any]) -> dict[str, Any]:
    found = sweeps.liveness_from(doc)
    assert found is not None
    return found


# --- Step 0.5 -----------------------------------------------------------------------


def test_bot_draft_is_promoted_before_f2_drops_it() -> None:
    d = one(pr(author="dependabot[bot]", assoc="NONE", draft=True, updated=ago(days=1)))
    assert (d.row, d.classification, d.action) == ("0.5", "bot_draft", "promote-bot-draft")


def test_bot_non_draft_stays_filtered() -> None:
    assert one(pr(author="renovate[bot]", assoc="NONE")).filter == "F2"


def test_bot_draft_with_pending_runs_is_rerouted_to_approval() -> None:
    d = one(
        pr(author="github-actions", assoc="NONE", draft=True),
        action_required={"abc1234def5678": [{"id": 1, "name": "Tests"}]},
    )
    assert (d.classification, d.action) == ("pending_workflow_approval", "approve-workflow")
    assert d.details["rerouted_from"] == "promote-bot-draft"


# --- Sweep 1 ------------------------------------------------------------------------


def test_sweep_1a_triaged_draft_without_reply_or_push() -> None:
    d = one(pr(draft=True, updated=ago(days=8), committed=ago(days=10), body=fold("abc1234", ago(days=8))))
    assert (d.row, d.classification, d.action) == ("sweep-1a", "stale_draft", "close-stale")
    assert d.details["variant"] == "triaged"


def test_sweep_1a_a_push_after_the_marker_is_a_response() -> None:
    d = one(pr(draft=True, updated=ago(days=2), committed=ago(days=2), body=fold("0000000", ago(days=9))))
    assert d.row != "sweep-1a"


def test_sweep_1a_a_thread_reply_is_a_response() -> None:
    d = one(
        pr(
            draft=True,
            updated=ago(days=8),
            committed=ago(days=12),
            body=fold("abc1234", ago(days=9)),
            threads=[
                thread(
                    comment("kaxil", "MEMBER", ago(days=11), "?"),
                    comment("nina-contributor", when=ago(days=8), body="done"),
                )
            ],
        )
    )
    assert d.row != "sweep-1a"


def test_sweep_1a_waits_seven_days() -> None:
    d = one(pr(draft=True, updated=ago(days=5), committed=ago(days=10), body=fold("abc1234", ago(days=5))))
    assert d.row != "sweep-1a"


def test_sweep_1a_comment_marker_by_unresolved_collaborator_needs_permission() -> None:
    d = one(
        pr(
            draft=True,
            updated=ago(days=20),
            committed=ago(days=30),
            comments=[comment("router", "COLLABORATOR", ago(days=20), "Pull Request quality criteria")],
        ),
        maintainers=people.Maintainers(team=frozenset()),
    )
    assert d.outcome == "needs" and d.needs[0]["op"] == "upstream-permission"


def test_sweep_1a_read_role_marker_does_not_start_the_close_clock() -> None:
    d = one(
        pr(
            draft=True,
            updated=ago(days=10),
            committed=ago(days=30),
            comments=[comment("router", "COLLABORATOR", ago(days=10), "Pull Request quality criteria")],
        ),
        maintainers=people.Maintainers(permissions={"router": "triage"}),
    )
    assert d.row != "sweep-1a"


def test_sweep_1a_viewer_marker_needs_no_check() -> None:
    d = one(
        pr(
            draft=True,
            updated=ago(days=10),
            committed=ago(days=30),
            comments=[comment("triager", "MEMBER", ago(days=10), "Pull Request quality criteria")],
        ),
    )
    assert d.row == "sweep-1a"


def test_sweep_1b_untriaged_draft() -> None:
    d = one(pr(draft=True, updated=ago(days=15), committed=ago(days=20)))
    assert (d.row, d.action) == ("sweep-1b", "close-stale")
    assert d.details["variant"] == "untriaged"


def test_sweep_1_takes_a_stale_draft_from_a_table_action() -> None:
    d = one(pr(draft=True, updated=ago(days=15), committed=ago(days=20), mergeable="CONFLICTING"))
    assert d.row == "sweep-1b"


def test_sweep_1b_waits_two_weeks() -> None:
    assert one(pr(draft=True, updated=ago(days=10))).row != "sweep-1b"


# --- Sweep 2 and 3 --------------------------------------------------------------------


def test_sweep_2_inactive_open_pr_skipped_by_the_table() -> None:
    d = one(pr(updated=ago(days=30), committed=ago(days=30), mergeable="UNKNOWN"))
    assert (d.row, d.classification, d.action) == ("sweep-2", "inactive_open", "draft")


def test_sweep_2_never_overrides_a_table_action() -> None:
    assert one(pr(updated=ago(days=30), committed=ago(days=30), mergeable="CONFLICTING")).row == "9"


def test_sweep_3_stale_workflow_approval() -> None:
    d = one(
        pr(
            assoc="FIRST_TIME_CONTRIBUTOR",
            updated=ago(days=30),
            committed=ago(days=30),
            checks=[check("Mergeable")],
        )
    )
    assert (d.row, d.classification, d.action) == ("sweep-3", "stale_workflow_approval", "draft")


def test_sweep_3_young_approval_stays_with_the_table() -> None:
    d = one(pr(assoc="FIRST_TIME_CONTRIBUTOR", updated=ago(days=3), checks=[check("Mergeable")]))
    assert d.row == "1"


# --- the guards ------------------------------------------------------------------------


def test_maintainer_court_guard_skips_staleness_sweeps() -> None:
    d = one(
        pr(
            updated=ago(days=30),
            committed=ago(days=35),
            mergeable="UNKNOWN",
            comments=[comment("nina-contributor", when=ago(days=30), body="@kaxil is this ok?")],
        ),
        maintainers=people.Maintainers(team=frozenset({"kaxil"})),
    )
    assert d.row is None or not d.row.startswith("sweep")


def test_ready_label_pr_never_reaches_sweeps_1_to_3() -> None:
    d = one(
        pr(draft=True, labels=[READY], updated=ago(days=40), committed=ago(days=40), label_events=labelled(2))
    )
    assert d.row is None or d.row not in ("sweep-1a", "sweep-1b", "sweep-2", "sweep-3")


def test_active_conversation_is_not_swept() -> None:
    d = one(
        pr(
            updated=ago(days=30),
            committed=ago(days=40),
            mergeable="UNKNOWN",
            comments=[comment("potiuk", "MEMBER", ago(hours=5), "looking")],
        )
    )
    assert d.filter == "F5a"


# --- Sweep 4 ----------------------------------------------------------------------------


def _stale_ready(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "labels": [READY],
        "label_events": labelled(10),
        "updated": ago(days=9),
        "committed": ago(days=12),
    }
    base.update(kw)
    return pr(**base)


def test_sweep_4_needs_a_live_read() -> None:
    d = one(_stale_ready())
    assert d.outcome == "needs" and d.needs == [
        {"op": "gql-pr-liveness", "params": ["1"], "save": "liveness-1.json"}
    ]


def test_sweep_4_fresh_label_is_not_a_candidate() -> None:
    d = one(_stale_ready(label_events=labelled(2)))
    assert d.filter == "F4"


def test_sweep_4_recent_activity_is_not_a_candidate() -> None:
    d = one(_stale_ready(comments=[comment("nina-contributor", when=ago(days=3), body="ping")]))
    assert d.filter == "F4"


def test_sweep_4_healthy_blocked_keeps_the_label() -> None:
    d = one(_stale_ready(), liveness={1: _live(live())})
    assert (d.row, d.action) == ("sweep-4-keep", "skip")


def test_sweep_4_conflict_strips_and_pings() -> None:
    d = one(_stale_ready(), liveness={1: _live(live("CONFLICTING", "DIRTY"))})
    assert (d.row, d.classification, d.action) == ("sweep-4", "stale_ready_label", "strip-ready-label")
    assert d.details["author_action"] == "ping" and d.details["audit_marker"] and d.details["fold_into_audit"]
    assert "merge conflict" in d.reason


def test_sweep_4_unknown_live_state_defers() -> None:
    d = one(_stale_ready(), liveness={1: _live(live("UNKNOWN", "UNKNOWN"))})
    assert d.row == "sweep-4-keep" and "defer" in d.reason


def test_sweep_4_unengaged_threads_strip_and_ping() -> None:
    d = one(
        _stale_ready(
            committed=ago(days=20), threads=[thread(comment("kaxil", "MEMBER", ago(days=15), "why?"))]
        ),
        liveness={1: _live(live())},
    )
    assert d.action == "strip-ready-label" and d.details["table_row"] == "15"


def test_a_regression_after_the_label_stays_with_the_table() -> None:
    """A failure newer than the label bypasses F4; strip-ready-on-downgrade handles it, not Sweep 4."""
    d = one(
        _stale_ready(rollup="FAILURE", checks=[check("Static checks: ruff", "FAILURE", started=ago(days=3))])
    )
    assert d.row == "12" and d.details["strip_ready_label"]


def test_sweep_4_static_failure_strips_with_a_fix_request() -> None:
    d = one(
        _stale_ready(
            rollup="FAILURE",
            checks=[check("Tests"), check("Static checks: ruff", "FAILURE", started=ago(days=11))],
        ),
        liveness={1: _live(live("MERGEABLE", "UNSTABLE"))},
    )
    assert d.action == "strip-ready-label" and d.details["author_action"] == "comment"
    assert not d.details["fold_into_audit"]


def test_sweep_4_flaky_failure_is_a_maintainer_rerun_keeping_the_label() -> None:
    d = one(
        _stale_ready(rollup="FAILURE", checks=[check("Tests (a)", "FAILURE", started=ago(days=11))]),
        liveness={1: _live(live("MERGEABLE", "UNSTABLE"))},
    )
    assert d.action == "rerun" and d.details["keep_ready_label"]


def test_sweep_4_author_waiting_on_a_maintainer_keeps_the_label() -> None:
    d = one(
        _stale_ready(comments=[comment("nina-contributor", when=ago(days=8), body="@kaxil ok to merge?")]),
        maintainers=people.Maintainers(team=frozenset({"kaxil"})),
    )
    assert d.row == "sweep-4-keep" and "waiting on us" in d.reason


def test_sweep_4_approved_mergeable_keeps_the_label() -> None:
    d = one(
        _stale_ready(reviews=[review("kaxil", "APPROVED", when=ago(days=9), body="")]),
        liveness={1: _live(live("MERGEABLE", "CLEAN"))},
    )
    assert d.row == "sweep-4-keep"


def test_sweep_4_moved_head_defers() -> None:
    d = one(_stale_ready(), liveness={1: _live(live(head="ffffffffffffff"))})
    assert d.row == "sweep-4-keep"


def test_liveness_accepts_an_unwrapped_object() -> None:
    assert sweeps.liveness_from({"mergeable": "MERGEABLE"}) == {"mergeable": "MERGEABLE"}
    assert sweeps.liveness_from([]) is None


# --- Sweep 5 ----------------------------------------------------------------------------


def test_sweep_5_escalates_a_silent_confirmation_request() -> None:
    d = one(
        pr(
            committed=ago(days=12),
            updated=ago(days=8),
            threads=[thread(comment("kaxil", "MEMBER", ago(days=11), "null?"))],
            comments=[comment("triager", "MEMBER", ago(days=8), "ready for maintainer review confirmation?")],
        )
    )
    assert (d.row, d.classification, d.action) == ("sweep-5", "stale_author_confirm_request", "ping")
    assert d.details["reviewers"] == ["kaxil"]


def test_sweep_5_waits_seven_days() -> None:
    d = one(
        pr(
            committed=ago(days=12),
            updated=ago(days=4),
            comments=[comment("triager", "MEMBER", ago(days=4), "ready for maintainer review confirmation?")],
        )
    )
    assert d.row == "14b"


# --- grouping ---------------------------------------------------------------------------


def test_sweep_groups_follow_the_table_groups() -> None:
    order = list(C.GROUP_ORDER)
    assert order[0] == ("bot_draft", "promote-bot-draft")
    assert order.index(("passing", "mark-ready")) < order.index(("stale_draft", "close-stale"))
    assert order[-1] == ("stale_author_confirm_request", "ping")
    assert "close-stale" in C.DESTRUCTIVE


def test_every_sweep_row_and_action_has_a_document() -> None:
    for row in ("0.5", "sweep-1a", "sweep-1b", "sweep-2", "sweep-3", "sweep-4", "sweep-4-keep", "sweep-5"):
        assert row in C.ROW_DOCS
    for action in ("close-stale", "strip-ready-label", "promote-bot-draft", "draft", "ping"):
        assert action in C.ACTION_DOCS


def test_sweeps_can_be_turned_off() -> None:
    prs = [model.from_node(pr(draft=True, updated=ago(days=15), committed=ago(days=20)))]
    (d,) = C.classify(
        prs, _cfg(), C.Options(viewer="v", now=NOW, sweeps=False), people.Maintainers(), {}, set()
    )
    assert d.row is None or not d.row.startswith("sweep")
