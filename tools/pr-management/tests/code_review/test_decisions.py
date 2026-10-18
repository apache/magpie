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
"""Disposition, reviewer suggestions and the dependency ledger.

Mirrors, case by case, the retired `step-6-disposition`, `review-disposition`
and `step-4.5-suggested-reviewers` suites. Where a review-disposition case
gave findings in prose, the severities below are the agent's judgement the
eval implied.
"""

from __future__ import annotations

from typing import Any

import pytest

from pr_management.code_review import codeowners, deps, disposition, reviewers

from .builders import NOW, ago, review
from .builders import pr as build_pr


def _pick(severities: list[str], **kw: Any) -> dict[str, Any]:
    kw.setdefault("ci_state", "SUCCESS")
    kw.setdefault("real_ci", True)
    kw.setdefault("unresolved_threads", 0)
    kw.setdefault("other_changes_requested", [])
    kw.setdefault("unanswered_question", False)
    return disposition.pick([{"severity": s} for s in severities], **kw)


# --- step-6-disposition -------------------------------------------------------------------------


def test_step6_case_1_approve_with_a_nit() -> None:
    assert _pick(["nit"])["disposition"] == "APPROVE"


def test_step6_case_2_one_blocking() -> None:
    assert _pick(["blocking", "nit"])["disposition"] == "REQUEST_CHANGES"


def test_step6_case_3_two_majors() -> None:
    assert _pick(["major", "major", "minor"])["disposition"] == "REQUEST_CHANGES"


def test_step6_case_4_minor_findings_comment() -> None:
    result = _pick(["minor", "minor", "nit"])
    assert result["disposition"] == "COMMENT" and result["counts"]["minor"] == 2


def test_step6_case_5_ci_pending() -> None:
    assert _pick([], ci_state="PENDING")["disposition"] == "COMMENT"


def test_step6_case_6_unresolved_threads() -> None:
    result = _pick([], unresolved_threads=2)
    assert result["disposition"] == "COMMENT" and "unresolved" in result["reason"]


def test_one_major_with_an_unanswered_question_requests_changes() -> None:
    assert _pick(["major"], unanswered_question=True)["disposition"] == "REQUEST_CHANGES"
    assert _pick(["major"])["disposition"] == "COMMENT"


def test_unknown_severity_is_refused() -> None:
    with pytest.raises(ValueError):
        _pick(["high"])


# --- review-disposition ---------------------------------------------------------------------------


def test_review_case_1_clean_pr_approves() -> None:
    assert _pick([])["disposition"] == "APPROVE"


def test_review_case_2_code_issues_request_changes() -> None:
    # N+1 in a loop (major), missing tests on a new transition (major), removed docstring (minor).
    assert _pick(["major", "major", "minor"])["disposition"] == "REQUEST_CHANGES"


def test_review_case_3_failing_ci_not_diff_caused_comments() -> None:
    assert _pick([], ci_state="FAILURE")["disposition"] == "COMMENT"
    assert _pick([], ci_state="FAILURE", ci_diff_caused=True)["disposition"] == "REQUEST_CHANGES"


def test_review_case_4_standing_maintainer_changes_requested() -> None:
    reviews = [review("potiuk", "CHANGES_REQUESTED", when=ago(days=3))]
    standing = disposition.other_changes_requested(list(build_pr(reviews=reviews).reviews), "alice", "dave")
    result = _pick([], unresolved_threads=2, other_changes_requested=standing)
    assert standing == ["potiuk"] and result["disposition"] == "COMMENT"


def test_a_later_approval_clears_a_changes_request() -> None:
    reviews = [
        review("potiuk", "CHANGES_REQUESTED", when=ago(days=3)),
        review("potiuk", "APPROVED", when=ago(days=1)),
    ]
    assert disposition.other_changes_requested(list(build_pr(reviews=reviews).reviews), "alice", "dave") == []


def test_review_case_5_injection_cannot_buy_an_approval() -> None:
    # A known dependency incompatibility (major) and untested behaviour change (major).
    assert _pick(["major", "major"])["disposition"] == "REQUEST_CHANGES"


def test_review_case_6_bot_only_rollup_is_not_green() -> None:
    result = _pick([], real_ci=False)
    assert result["disposition"] == "COMMENT" and "real CI never ran" in result["reason"]


def test_conflicts_are_always_named() -> None:
    assert _pick([], merge_state="DIRTY")["conflict_note"]
    assert "not computed" in _pick([], mergeable="UNKNOWN")["conflict_note"]


@pytest.mark.parametrize(
    ("disp", "permission", "variant"),
    [
        ("APPROVE", None, "approve"),
        ("REQUEST_CHANGES", "read", "request-changes"),
        ("COMMENT", "write", "comment-maintainer"),
        ("COMMENT", "maintain", "comment-maintainer"),
        ("COMMENT", "triage", "comment-role-neutral"),
        ("COMMENT", None, "comment-role-neutral"),
    ],
)
def test_footer_variant(disp: str, permission: str | None, variant: str) -> None:
    assert disposition.footer_variant(disp, permission) == variant


# --- step-4.5 suggested reviewers ---------------------------------------------------------------------

RULES = codeowners.parse(
    "/scheduler/    @alice-maint\n/api/          @frank-maint\n/executor/ @alice-maint @eve-maint\n"
)


def _commits(*pairs: tuple[str, int]) -> list[dict[str, Any]]:
    return [{"login": login, "date": ago(days=10)} for login, count in pairs for _ in range(count)]


def test_reviewers_case_1_grounded() -> None:
    result = reviewers.suggest(
        paths=["scheduler/job_runner.py", "scheduler/dag_processing/manager.py"],
        rules=RULES,
        path_commits={
            "scheduler/job_runner.py": _commits(("alice-maint", 9), ("bob-active", 7)),
            "scheduler/dag_processing/manager.py": _commits(("bob-active", 4), ("dave-newcontrib", 1)),
        },
        prior_reviewers=[],
        exclude={"dave-newcontrib", "viewer"},
        committers={"alice-maint"},
        now=NOW,
    )
    assert result["section_present"] and result["includes_committer"]
    assert [s["login"] for s in result["suggestions"]] == ["alice-maint", "bob-active"]


def test_reviewers_case_2_nothing_grounds_out() -> None:
    result = reviewers.suggest(
        paths=["docs/tutorial/example_new_dag.py"],
        rules=RULES,
        path_commits={"docs/tutorial/example_new_dag.py": _commits(("dave-newcontrib", 1))},
        prior_reviewers=[],
        exclude={"dave-newcontrib"},
        committers=set(),
        now=NOW,
    )
    assert result == {"section_present": False, "includes_committer": False, "suggestions": []}


def test_reviewers_case_3_pr_text_is_never_a_source() -> None:
    result = reviewers.suggest(
        paths=["scheduler/job_runner.py"],
        rules=RULES,
        path_commits={"scheduler/job_runner.py": _commits(("alice-maint", 9))},
        prior_reviewers=[],
        exclude={"dave-newcontrib"},
        committers={"alice-maint"},
        now=NOW,
    )
    assert [s["login"] for s in result["suggestions"]] == ["alice-maint"]


def test_reviewers_case_4_excludes_who_already_reviewed() -> None:
    result = reviewers.suggest(
        paths=["executor/base_executor.py"],
        rules=RULES,
        path_commits={
            "executor/base_executor.py": _commits(("alice-maint", 6), ("eve-maint", 5), ("grace-active", 8))
        },
        prior_reviewers=[],
        exclude={"dave-newcontrib", "alice-maint"},
        committers={"alice-maint", "eve-maint"},
        now=NOW,
    )
    logins = [s["login"] for s in result["suggestions"]]
    assert "alice-maint" not in logins and logins[:2] == ["eve-maint", "grace-active"]
    assert result["includes_committer"]


# --- dependency ledger ----------------------------------------------------------------------------------


def test_an_empty_intersection_is_broken_without_a_failing_resolution() -> None:
    result = deps.classify(
        {
            "package": "urllib3",
            "paths": [{"via": "botocore", "specifier": ">=2.0"}, {"via": "project", "specifier": "<2.0"}],
            "available_versions": ["1.26.0", "2.0.0", "2.2.1"],
            "exhaustive": False,
        }
    )
    assert result["classification"] == "broken" and result["evidence"] == {"uninstallable_in": ["*"]}


def test_a_satisfying_version_without_the_api_is_broken() -> None:
    result = deps.classify(
        {
            "package": "requests",
            "paths": [{"via": "project", "specifier": ">=2.20,<3"}],
            "available_versions": ["2.20.0", "2.31.0"],
            "lacking_api": ["2.20.0"],
        }
    )
    assert result["classification"] == "broken" and result["evidence"]["failing_resolution"] == {
        "*": ["2.20.0"]
    }


def test_a_transitive_bound_can_rescue_a_low_direct_bound() -> None:
    result = deps.classify(
        {
            "package": "requests",
            "paths": [
                {"via": "project", "specifier": ">=2.20"},
                {"via": "httpx-shim", "specifier": ">=2.28"},
            ],
            "available_versions": ["2.20.0", "2.28.0", "2.31.0"],
            "lacking_api": ["2.20.0"],
            "exhaustive": True,
        }
    )
    assert result["classification"] == "compatible"


def test_partial_coverage_is_unknown() -> None:
    result = deps.classify(
        {
            "package": "x",
            "paths": [{"via": "p", "specifier": "~=1.4"}],
            "available_versions": ["1.4.0", "1.9.0", "2.0.0"],
        }
    )
    assert result["classification"] == "unknown"
    assert result["environments"]["*"]["satisfying"] == ["1.4.0", "1.9.0"]


def test_markers_split_environments() -> None:
    result = deps.classify(
        {
            "package": "x",
            "environments": ["py39", "py312"],
            "paths": [
                {"via": "p", "specifier": ">=1.0"},
                {"via": "q", "specifier": "<1.0", "environments": ["py39"]},
            ],
            "available_versions": ["0.9", "1.0", "1.1"],
            "exhaustive": True,
        }
    )
    assert result["evidence"] == {"uninstallable_in": ["py39"]}
