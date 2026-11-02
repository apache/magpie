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
  8) — or real CI still running where auto-merge will hold the merge (below) —
  no unresolved review thread (an outdated one the agent verified the
  current code addresses moves to `resolve_first` for the maintainer to
  resolve instead), no other maintainer's standing
  `CHANGES_REQUESTED`, no unanswered maintainer question (Golden rule 7), and
  no finding above `nit`.
* `COMMENT` — everything else.

When the only thing between a `COMMENT` and an `APPROVE` is a set of `minor` /
`nit` findings that each carry a `fixup` (a one-line, mechanical change the
maintainer can make), and the maintainer can push to the PR head, the result
also offers `FIXUP`: apply those changes as a commit on the contributor's
branch, then approve. It becomes the default action, not the disposition —
what is posted after a fixup is still an `APPROVE`.

When the repository allows auto-merge and the viewer can enable it on this PR,
an action that ends in an `APPROVE` gains auto-merge: the default becomes
`APPROVE+AUTO-MERGE`, or `FIXUP+APPROVE+AUTO-MERGE` when the fixup is the
default. Auto-merge is never offered on a self-authored PR, on one that already
has it enabled, or on a branch that conflicts.

Auto-merge also changes what pending CI means. GitHub holds an auto-merge until
the required checks pass, so real CI that is still running is not a gate on the
auto-merge path when every running check is a required one: the approval and
auto-merge go in immediately, and a failure later simply never merges. A running
check that branch protection does not require keeps the gate, since auto-merge
would not wait for it. Plain `APPROVE` / `FIXUP` are then not offered,
because without auto-merge they would approve on unfinished CI. Failing CI, a
rollup that is green from bot checks only, and a run still waiting for workflow
approval stay gates (Golden rule 8): those runs have to be approved or re-run
first, and `ci_action` says so.

Conflicts never force `REQUEST_CHANGES`, but a `DIRTY` / `CONFLICTING` /
still-`UNKNOWN` branch is always named in the body.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

SEVERITIES = ("nit", "minor", "major", "blocking")
MERGE_METHODS = ("MERGE", "SQUASH", "REBASE")
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
    head_pushable: bool = False,
    resolve_first: list[dict[str, Any]] | None = None,
    auto_merge_allowed: bool = False,
    viewer_can_enable_auto_merge: bool = False,
    auto_merge_enabled: bool = False,
    self_authored: bool = False,
    merge_method: str | None = None,
    pending_not_required: tuple[str, ...] | list[str] = (),
    viewer_known: bool = True,
) -> dict[str, Any]:
    resolve_first = resolve_first or []
    counts = Counter(str(f.get("severity") or "").lower() for f in findings)
    unknown = [s for s in counts if s not in SEVERITIES]
    if unknown:
        raise ValueError(f"unknown severity {unknown[0]!r}; use one of {', '.join(SEVERITIES)}")
    blocking, major, minor, nit = (counts[s] for s in ("blocking", "major", "minor", "nit"))
    ci_failed = ci_state in ("FAILURE", "ERROR")
    conflict = None
    if mergeable == "CONFLICTING" or merge_state == "DIRTY":
        conflict = "The branch currently conflicts with its base and needs a rebase before this can merge."
    elif mergeable == "UNKNOWN":
        conflict = "GitHub has not computed whether this branch merges cleanly yet."
    auto_merge_possible = (
        auto_merge_allowed
        and viewer_can_enable_auto_merge
        and not auto_merge_enabled
        and not self_authored
        and viewer_known
        and not conflict
    )
    ci_pending = ci_state == "PENDING" and real_ci
    # Auto-merge waits only for required checks; a running check that is not required could fail after the merge.
    held_by_auto_merge = ci_pending and auto_merge_possible and not pending_not_required
    gates: list[str] = []
    ci_action = None
    if ci_pending and auto_merge_possible and pending_not_required:
        gates.append(
            "CI is PENDING and auto-merge would not wait for "
            + ", ".join(f"`{n}`" for n in pending_not_required)
            + " (not a required check)"
        )
    elif ci_state == "EXPECTED":
        gates.append("CI is waiting for workflow approval — the project's real CI has not run")
        ci_action = "approve the waiting workflow runs (pr-management-triage), then re-run disposition"
    elif ci_state != "SUCCESS" and not held_by_auto_merge:
        gates.append(f"CI is {ci_state or 'not reported'}")
        if ci_state == "PENDING" and not real_ci:
            ci_action = "approve or re-run the project's workflows (pr-management-triage); only bot checks are running"
    elif ci_state == "SUCCESS" and not real_ci:
        gates.append("the rollup is green from bot checks only — the project's real CI never ran")
        ci_action = (
            "approve or re-run the project's workflows (pr-management-triage), then re-run disposition"
        )
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
        if held_by_auto_merge:
            reason += "; CI is still running, so approve with auto-merge and let GitHub hold the merge until it passes"
        if resolve_first:
            reason += f"; resolve the {len(resolve_first)} outdated thread(s) the current code addresses to unblock the merge"
    fixup = _fixup(findings, disposition, gates, conflict, head_pushable)
    auto_merge = _auto_merge(
        disposition == "APPROVE" or fixup["eligible"],
        conflict,
        allowed=auto_merge_allowed,
        viewer_can_enable=viewer_can_enable_auto_merge,
        already_enabled=auto_merge_enabled,
        self_authored=self_authored,
        viewer_known=viewer_known,
        merge_method=merge_method,
    )
    overrides = ["APPROVE", "REQUEST_CHANGES", "COMMENT"]
    if fixup["eligible"]:
        overrides = ["FIXUP", *overrides]
    default = "FIXUP" if fixup["eligible"] else disposition
    if auto_merge["eligible"]:
        default += "+APPROVE+AUTO-MERGE" if default == "FIXUP" else "+AUTO-MERGE"
        if held_by_auto_merge:
            # Without auto-merge these would approve on unfinished CI (Golden rule 8).
            overrides = [o for o in overrides if o not in ("APPROVE", "FIXUP")]
        overrides = [default, *overrides]
    return {
        "disposition": disposition,
        "reason": reason,
        "counts": {"blocking": blocking, "major": major, "minor": minor, "nit": nit},
        "approval_gates": gates,
        "ci_pending_held_by_auto_merge": held_by_auto_merge,
        "ci_action": ci_action,
        "footer": footer_variant(disposition, permission),
        "conflict_note": conflict,
        "resolve_first": resolve_first,
        "fixup": fixup,
        "auto_merge": auto_merge,
        "default": default,
        "overrides": overrides,
    }


def _auto_merge(
    ends_in_approve: bool,
    conflict: str | None,
    *,
    allowed: bool,
    viewer_can_enable: bool,
    already_enabled: bool,
    self_authored: bool,
    merge_method: str | None,
    viewer_known: bool = True,
) -> dict[str, Any]:
    """Whether the action that ends in an `APPROVE` should also enable auto-merge."""
    if not allowed:
        return {"eligible": False, "reason": "the repository does not allow auto-merge"}
    if not ends_in_approve:
        return {"eligible": False, "reason": "auto-merge only follows an APPROVE"}
    if not viewer_known:
        # Without the read's own viewer, `self_authored` rests on a command-line flag alone.
        return {
            "eligible": False,
            "reason": "the saved read has no viewer to check self-authorship against; refresh it",
        }
    if self_authored:
        return {"eligible": False, "reason": "a self-authored PR is never auto-merged by its own review"}
    if already_enabled:
        return {"eligible": False, "reason": "auto-merge is already enabled on this PR"}
    if not viewer_can_enable:
        return {"eligible": False, "reason": "the viewer cannot enable auto-merge on this PR"}
    if conflict:
        return {"eligible": False, "reason": "the branch does not merge cleanly"}
    method = (merge_method or "SQUASH").upper()
    if method not in MERGE_METHODS:
        method = "SQUASH"
    return {
        "eligible": True,
        "reason": "the repository allows auto-merge and every approval gate holds",
        "method": method,
    }


def _fixup(
    findings: list[dict[str, Any]],
    disposition: str,
    gates: list[str],
    conflict: str | None,
    head_pushable: bool,
) -> dict[str, Any]:
    """Whether applying the remaining findings as a commit would earn an `APPROVE`."""
    if disposition != "COMMENT" or not findings:
        return {"eligible": False, "reason": f"nothing to fix up on a {disposition}"}
    if any(str(f.get("severity") or "").lower() in ("major", "blocking") for f in findings):
        return {"eligible": False, "reason": "a major finding needs the author, not a fixup"}
    if gates:
        return {"eligible": False, "reason": "an approval gate other than the findings is open"}
    if conflict:
        return {"eligible": False, "reason": "the branch does not merge cleanly"}
    if not head_pushable:
        return {"eligible": False, "reason": "the maintainer cannot push to the PR head"}
    missing = [f for f in findings if not str(f.get("fixup") or "").strip()]
    if missing:
        return {"eligible": False, "reason": f"{len(missing)} finding(s) have no mechanical fixup"}
    return {
        "eligible": True,
        "reason": "every remaining finding is minor or nit with a mechanical fixup",
        "changes": [str(f["fixup"]).strip() for f in findings],
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
