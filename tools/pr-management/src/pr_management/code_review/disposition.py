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
"""Step 6 — the disposition auto-pick, and the footer variant it implies.

Rules (one definition; the three the docs carried disagreed):

* `REQUEST_CHANGES` — at least one `blocking`, or two or more `major`, or one
  `major` with an unanswered author question, or a CI failure the agent
  judged diff-caused.
* `APPROVE` — every gate holds: rollup `SUCCESS` and real CI ran (Golden rule
  8), no unresolved review thread, no other maintainer's standing
  `CHANGES_REQUESTED`, no unanswered maintainer question (Golden rule 7), and
  no finding above `nit`.
* `COMMENT` — everything else.

Conflicts never force `REQUEST_CHANGES`, but a `DIRTY` / `CONFLICTING` /
still-`UNKNOWN` branch is always named in the body.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

SEVERITIES = ("nit", "minor", "major", "blocking")
MAINTAINER_PERMISSIONS = frozenset({"admin", "maintain", "write"})


def footer_variant(disposition: str, permission: str | None) -> str:
    """`approve`, `request-changes`, `comment-maintainer` or `comment-role-neutral`."""
    if disposition == "APPROVE":
        return "approve"
    if disposition == "REQUEST_CHANGES":
        return "request-changes"
    return (
        "comment-maintainer"
        if (permission or "").lower() in MAINTAINER_PERMISSIONS
        else "comment-role-neutral"
    )


def pick(
    findings: list[dict[str, Any]],
    *,
    ci_state: str | None,
    real_ci: bool,
    unresolved_threads: int,
    other_changes_requested: list[str],
    unanswered_question: bool,
    ci_diff_caused: bool = False,
    mergeable: str | None = None,
    merge_state: str | None = None,
    permission: str | None = None,
) -> dict[str, Any]:
    counts = Counter(str(f.get("severity") or "").lower() for f in findings)
    unknown = [s for s in counts if s not in SEVERITIES]
    if unknown:
        raise ValueError(f"unknown severity {unknown[0]!r}; use one of {', '.join(SEVERITIES)}")
    blocking, major, minor, nit = (counts[s] for s in ("blocking", "major", "minor", "nit"))
    ci_failed = ci_state in ("FAILURE", "ERROR")
    gates: list[str] = []
    if ci_state != "SUCCESS":
        gates.append(f"CI is {ci_state or 'not reported'}")
    elif not real_ci:
        gates.append("the rollup is green from bot checks only — the project's real CI never ran")
    if unresolved_threads:
        gates.append(f"{unresolved_threads} unresolved review thread(s)")
    if other_changes_requested:
        gates.append(
            "standing CHANGES_REQUESTED from " + ", ".join(f"`{m}`" for m in other_changes_requested)
        )
    if unanswered_question:
        gates.append("an unanswered maintainer question")
    tally = f"{blocking} blocking, {major} major, {minor} minor, {nit} nit"
    if blocking:
        disposition, reason = "REQUEST_CHANGES", f"{blocking} blocking finding(s) — {tally}"
    elif major >= 2:
        disposition, reason = "REQUEST_CHANGES", f"{major} major findings — {tally}"
    elif major and unanswered_question:
        disposition, reason = (
            "REQUEST_CHANGES",
            f"a major finding plus an unanswered author question — {tally}",
        )
    elif ci_failed and ci_diff_caused:
        disposition, reason = "REQUEST_CHANGES", "CI fails because of this diff"
    elif gates:
        disposition, reason = "COMMENT", "APPROVE is off the table: " + "; ".join(gates) + f" ({tally})"
    elif major or minor:
        disposition, reason = "COMMENT", f"findings above nit remain — {tally}"
    else:
        disposition, reason = "APPROVE", f"every approval gate holds — {tally}"
    conflict = None
    if mergeable == "CONFLICTING" or merge_state == "DIRTY":
        conflict = "The branch currently conflicts with its base and needs a rebase before this can merge."
    elif mergeable == "UNKNOWN":
        conflict = "GitHub has not computed whether this branch merges cleanly yet."
    return {
        "disposition": disposition,
        "reason": reason,
        "counts": {"blocking": blocking, "major": major, "minor": minor, "nit": nit},
        "approval_gates": gates,
        "footer": footer_variant(disposition, permission),
        "conflict_note": conflict,
        "overrides": ["APPROVE", "REQUEST_CHANGES", "COMMENT"],
    }


def other_changes_requested(reviews: list[Any], viewer: str, author: str) -> list[str]:
    """Reviewers whose latest review is CHANGES_REQUESTED (not the viewer, not the author)."""
    latest: dict[str, Any] = {}
    for review in sorted(reviews, key=lambda r: (r.submitted is None, r.submitted)):
        if review.state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[review.author.lower()] = review
    return sorted(
        r.author
        for key, r in latest.items()
        if r.state == "CHANGES_REQUESTED" and key not in (viewer.lower(), author.lower())
    )
