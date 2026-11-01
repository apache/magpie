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
  8), no unresolved review thread (an outdated one the agent verified the
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
    head_pushable: bool = False,
    resolve_first: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolve_first = resolve_first or []
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
        if resolve_first:
            reason += f"; resolve the {len(resolve_first)} outdated thread(s) the current code addresses to unblock the merge"
    conflict = None
    if mergeable == "CONFLICTING" or merge_state == "DIRTY":
        conflict = "The branch currently conflicts with its base and needs a rebase before this can merge."
    elif mergeable == "UNKNOWN":
        conflict = "GitHub has not computed whether this branch merges cleanly yet."
    fixup = _fixup(findings, disposition, gates, conflict, head_pushable)
    overrides = ["APPROVE", "REQUEST_CHANGES", "COMMENT"]
    return {
        "disposition": disposition,
        "reason": reason,
        "counts": {"blocking": blocking, "major": major, "minor": minor, "nit": nit},
        "approval_gates": gates,
        "footer": footer_variant(disposition, permission),
        "conflict_note": conflict,
        "resolve_first": resolve_first,
        "fixup": fixup,
        "default": "FIXUP" if fixup["eligible"] else disposition,
        "overrides": ["FIXUP", *overrides] if fixup["eligible"] else overrides,
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
