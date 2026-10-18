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
"""Step 2 of pr-management-triage: pre-filters, then the first-match-wins decision table.

A pure function of the fetched state. Rows are evaluated in the order the
table fixes, with row 22 checked before rows 17 and 19-20 (the table's hard
rule). A PR whose decision needs data the sweep does not carry — the REST
check-run list behind a truncated rollup page, or commits-behind for row 13 —
comes back as `needs` with the reads to run; the skill runs them and
classifies again.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any

from .. import ci, markers
from ..config import Config
from ..model import COLLABORATOR_ASSOCIATIONS, PR
from ..people import Maintainers, is_bot
from . import signals as S
from .types import Decision, Options

#: Classification documents, one per decision row (paths relative to the skill).
ROW_DOCS: dict[str, str] = {
    "0": "classifications/first-time-stale-abandoned.md",
    "1": "classifications/pending-workflow-approval.md",
    "2": "classifications/stale-copilot-review.md",
    "3": "classifications/already-triaged.md",
    "4": "classifications/already-triaged.md",
    "5": "classifications/stale-draft.md",
    "7b": "classifications/security-language-signal.md",
    "8": "classifications/flagged-author-close.md",
    "9": "classifications/merge-conflict.md",
    "10": "classifications/systemic-ci-failure.md",
    "11": "classifications/systemic-ci-failure.md",
    "12": "classifications/static-check-failure.md",
    "12b": "classifications/static-check-failure.md",
    "13": "classifications/flaky-ci-failure.md",
    "14a": "classifications/author-confirmed-ready.md",
    "14b": "classifications/awaiting-author-confirmation.md",
    "14c": "classifications/threads-likely-addressed.md",
    "15": "classifications/unresolved-threads.md",
    "16": "classifications/no-real-ci.md",
    "17": "classifications/quality-fallback.md",
    "18": "classifications/stale-review.md",
    "19": "classifications/passing.md",
    "20": "classifications/passing.md",
    "22": "classifications/unsettled-state.md",
    "0.5": "classifications/bot-draft.md",
    "sweep-1a": "classifications/sweep-1a-stale-triaged-draft.md",
    "sweep-1b": "classifications/sweep-1b-stale-untriaged-draft.md",
    "sweep-2": "classifications/sweep-2-inactive-open.md",
    "sweep-3": "classifications/sweep-3-stale-workflow-approval.md",
    "sweep-4": "classifications/sweep-4-stale-ready-label.md",
    "sweep-4-keep": "classifications/sweep-4-stale-ready-label.md",
    "sweep-5": "classifications/sweep-5-stale-confirmation-request.md",
}

#: One document per action the agent executes.
ACTION_DOCS: dict[str, str] = {
    "approve-workflow": "actions/approve-workflow.md",
    "draft": "actions/draft.md",
    "comment": "actions/comment.md",
    "close": "actions/close.md",
    "rerun": "actions/rerun.md",
    "rebase": "actions/rebase.md",
    "ping": "actions/ping.md",
    "request-author-confirmation": "actions/request-author-confirmation.md",
    "mark-ready": "actions/mark-ready.md",
    "close-stale": "actions/close-stale.md",
    "strip-ready-label": "actions/strip-ready-label.md",
    "promote-bot-draft": "actions/promote-bot-draft.md",
}

#: Presentation order of the groups (interaction-loop.md § Group ordering).
GROUP_ORDER: tuple[tuple[str, str], ...] = (
    ("bot_draft", "promote-bot-draft"),
    ("pending_workflow_approval", "approve-workflow"),
    ("security_language_signal", "comment"),
    ("deterministic_flag", "close"),
    ("stale_copilot_review", "draft"),
    ("deterministic_flag", "draft"),
    ("deterministic_flag", "comment"),
    ("deterministic_flag", "rebase"),
    ("deterministic_flag", "rerun"),
    ("deterministic_flag", "ping"),
    ("stale_review", "ping"),
    ("deterministic_flag", "request-author-confirmation"),
    ("author_confirmed_ready", "mark-ready"),
    ("passing", "mark-ready"),
    ("stale_draft", "close-stale"),
    ("inactive_open", "draft"),
    ("stale_workflow_approval", "draft"),
    ("stale_ready_label", "strip-ready-label"),
    ("stale_author_confirm_request", "ping"),
)

DESTRUCTIVE = frozenset({"close", "close-stale"})


def _days(delta: dt.timedelta) -> int:
    return max(0, delta.days)


def _join(logins: list[str]) -> str:
    return ", ".join(f"@{login}" for login in logins)


def _row(pr: PR, row: str, classification: str | None, action: str, reason: str, **details: Any) -> Decision:
    outcome = "skip" if action in ("skip", "defer-sweep") else "act"
    return Decision(
        pr, outcome, row=row, classification=classification, action=action, reason=reason, details=details
    )


def prefilter(pr: PR, cfg: Config, opts: Options, people: Maintainers, sig: S.Signals) -> str | None:
    if opts.authors == "default" and pr.association in COLLABORATOR_ASSOCIATIONS:
        return "F1"
    if opts.authors == "collaborators" and pr.association not in COLLABORATOR_ASSOCIATIONS:
        return "F1"
    if is_bot(pr.author):
        return "F2"
    if pr.is_draft and pr.updated is not None and opts.now - pr.updated < S.F3_ACTIVITY:
        return "F3"
    if S.f4_skips(pr, cfg, sig):
        return "F4"
    if S.f5a(pr, opts.now, people):
        return "F5a"
    if S.f5b(pr, people):
        return "F5b"
    if S.f5c(pr, cfg, people):
        return "F5c"
    if S.f6(pr, opts.viewer):
        return "F6"
    return None


def decide(
    pr: PR,
    cfg: Config,
    opts: Options,
    sig: S.Signals,
    flagged_by_author: Counter[str],
    action_required: dict[str, list[dict[str, Any]]],
    systemic: set[str],
) -> Decision:
    now = opts.now
    if S.first_time_stale_abandoned(pr, cfg, sig, now):
        return _row(
            pr,
            "0",
            "first_time_stale_abandoned",
            "skip",
            "First-time contributor's PR was triaged ≥ 30d ago, no push since — let the stale-sweep retire it "
            "rather than re-approving CI",
        )
    pending = action_required.get(pr.head_sha, [])
    if pending or S.first_time_no_real_ci(pr, sig):
        return _row(
            pr,
            "1",
            "pending_workflow_approval",
            "approve-workflow",
            "First-time contributor — review the diff and approve CI, or flag suspicious",
            runs=pending,
        )
    copilot = S.copilot_review_stale(pr, cfg, now)
    if copilot:
        return _row(
            pr,
            "2",
            "stale_copilot_review",
            "draft",
            f"Unaddressed Copilot review ≥ {cfg.stale_copilot_days} days old — convert to draft",
            copilot_thread=copilot,
        )
    marker = markers.triage_marker(pr, cfg.marker)
    if marker is not None:
        age = now - marker.at
        state = markers.sub_state(pr, marker)
        by = f" by `{marker.by}`" if marker.by else ""
        days = _days(age)
        if age < dt.timedelta(days=cfg.stale_draft_triaged_days):
            if state == "waiting":
                return _row(
                    pr,
                    "3",
                    "already_triaged",
                    "skip",
                    f"Already triaged {days} days ago{by} — still waiting on author",
                )
            return _row(
                pr,
                "4",
                "already_triaged",
                "skip",
                f"Already triaged {days} days ago{by} — author responded, maintainer to re-engage",
            )
        if state == "waiting" and pr.is_draft:
            return _row(
                pr, "5", "stale_draft", "defer-sweep", f"Draft triaged {days} days ago, no author reply"
            )
    if pr.author == opts.viewer:
        return _row(pr, "6", None, "skip", "You are the PR author — triage skipped")
    if pr.created is not None and now - pr.created < S.TOO_FRESH:
        return _row(pr, "7a", None, "skip", "Too fresh — CI still warming up")
    if sig.security:
        return _row(
            pr,
            "7b",
            "security_language_signal",
            "comment",
            "Security-language in title / body / commits — ask contributor to neutralise or confirm CVE "
            "disclosure complete",
            security_matches=sig.security,
        )

    needs: list[dict[str, Any]] = []
    if ci.needs_rest_checks(pr):
        needs.append({"op": "check-runs", "params": [pr.head_sha], "save": f"check-runs-{pr.number}.json"})
    if needs:
        return Decision(
            pr, "needs", needs=needs, reason="The rollup page is truncated; the full check-run list is needed"
        )

    kinds = sig.kinds
    failed = sig.failed
    if flagged_by_author[pr.author] > S.FLAGGED_AUTHOR_THRESHOLD and sig.deterministic:
        return _flag(
            pr,
            cfg,
            sig,
            "8",
            "close",
            f"Author has {flagged_by_author[pr.author]} flagged PRs — suggest closing to reduce queue pressure",
        )
    if sig.conflict:
        return _flag(
            pr,
            cfg,
            sig,
            "9",
            "draft",
            f"Merge conflicts with `{pr.base}` — author must rebase locally; convert to draft with "
            "merge-conflicts violation",
        )
    if kinds == {"ci"}:
        hits = [f for f in failed if f in systemic]
        if hits and len(hits) == len(failed):
            return _flag(
                pr,
                cfg,
                sig,
                "10",
                "rerun",
                f"All {len(failed)} CI failures also appear in recent main-branch PRs — likely systemic, "
                "suggest rerun",
            )
        if hits:
            return _flag(
                pr,
                cfg,
                sig,
                "11",
                "rerun",
                f"{len(hits)}/{len(failed)} CI failures match recent main-branch PRs — likely systemic",
            )
        static = [f for f in failed if ci.is_static(f, cfg)]
        if static and len(static) == len(failed):
            return _flag(
                pr,
                cfg,
                sig,
                "12",
                "comment",
                f"Only static-check failures ({', '.join(static)}) — needs a code fix, not a rerun",
            )
        if static:
            return _flag(
                pr,
                cfg,
                sig,
                "12b",
                "comment",
                "Mixed failures including a static-check failure — code fix needed; a rerun would "
                "re-fail on the static check",
            )
        if len(failed) <= S.MAX_FLAKY_FAILURES:
            if pr.commits_behind is None:
                return Decision(
                    pr,
                    "needs",
                    needs=[
                        {
                            "op": "compare-behind",
                            "params": [pr.base, pr.head_sha],
                            "save": f"compare-{pr.number}.json",
                        }
                    ],
                    reason="Row 13 needs the commits-behind count",
                )
            if pr.commits_behind <= S.MAX_COMMITS_BEHIND:
                return _flag(
                    pr,
                    cfg,
                    sig,
                    "13",
                    "rerun",
                    f"{len(failed)} CI failure(s) on otherwise clean PR — likely flaky, suggest rerun",
                )

    requested = markers.confirmation_request(pr, opts.viewer)
    if requested is not None:
        if markers.author_replied_after(pr, requested):
            return _row(
                pr,
                "14a",
                "author_confirmed_ready",
                "mark-ready",
                "Author confirmed PR is ready for maintainer review — apply label",
                author_reply=_reply_after(pr, requested),
            )
        return _row(
            pr,
            "14b",
            "awaiting_author_confirmation",
            "skip",
            f"Awaiting author confirmation requested {_days(now - requested)} days ago",
        )
    threads_only = kinds == {"threads"} and pr.rollup_state == "SUCCESS"
    if threads_only:
        names = S.reviewers(sig.threads)
        if S.likely_addressed(pr, sig.threads):
            return _flag(
                pr,
                cfg,
                sig,
                "14c",
                "request-author-confirmation",
                f"{len(sig.threads)} unresolved thread(s) from {_join(names)} show author engagement — "
                "ask author to confirm readiness for maintainer review",
                reviewers=names,
            )
        return _flag(
            pr,
            cfg,
            sig,
            "15",
            "ping",
            f"{len(sig.threads)} unresolved review thread(s) from {_join(names)} — ping author + reviewers",
            reviewers=names,
        )
    if not sig.real_ci and pr.mergeable != "CONFLICTING" and not sig.first_time:
        return _flag(
            pr,
            cfg,
            sig,
            "16",
            "rebase",
            "No real CI checks triggered, branch mergeable — rebase to re-trigger",
        )
    if S.unsettled(pr, sig):
        return _unsettled(pr)
    if sig.deterministic:
        return _flag(
            pr, cfg, sig, "17", "draft", "Has quality issues — convert to draft with violations comment"
        )
    stale = S.stale_review(pr, now)
    if stale:
        return _row(
            pr,
            "18",
            "stale_review",
            "ping",
            f"Author pushed commits after CHANGES_REQUESTED from {_join(stale)} but no follow-up — ping",
            reviewers=stale,
        )
    # A draft is never proposed for the ready label: the sweeps own a stale one,
    # and a fresh one the author is still working on.
    if pr.rollup_state == "SUCCESS" and pr.mergeable == "MERGEABLE" and not sig.threads and not pr.is_draft:
        if not sig.real_ci:
            return _flag(
                pr,
                cfg,
                sig,
                "16",
                "rebase",
                "No real CI checks triggered, branch mergeable — rebase to re-trigger",
            )
        if cfg.ready_label in pr.labels:
            return _row(pr, "19", "passing", "skip", "Already marked ready for review")
        return _row(
            pr,
            "20",
            "passing",
            "mark-ready",
            "All checks green, no conflicts, no unresolved collaborator threads — mark for deeper review",
            fold_flip=markers.parse_fold(pr.body) is not None,
        )
    if sig.grace.get("in_grace"):
        return Decision(
            pr,
            "skip",
            row="grace",
            reason=f"CI failed {sig.grace.get('failed_hours_ago')}h ago, {sig.grace.get('remaining_hours')}h of "
            "grace remaining",
        )
    if pr.rollup_state == "PENDING" or ci.pending_checks(pr):
        return Decision(pr, "skip", row="pending", reason="CI still running — retry next sweep")
    return _unsettled(pr)


def _unsettled(pr: PR) -> Decision:
    reason = (
        "Mergeability not yet computed — retry next sweep"
        if pr.mergeable == "UNKNOWN"
        else "State not yet settled, retry next sweep"
    )
    return _row(pr, "22", None, "skip", reason)


def _reply_after(pr: PR, at: dt.datetime) -> str | None:
    replies = [c for c in pr.all_comments() if c.author == pr.author and c.created and c.created > at]
    return replies[-1].body if replies else None


def _flag(
    pr: PR, cfg: Config, sig: S.Signals, row: str, action: str, reason: str, **details: Any
) -> Decision:
    """A `deterministic_flag` row, with the strip-ready-on-downgrade and merit-discussion rules applied."""
    merit = bool(sig.threads)
    ready = cfg.ready_label in pr.labels
    effective = action
    strip = False
    if ready and action in ("draft", "comment", "close"):
        if not merit:
            strip = True
        elif action == "draft":
            # The merit-discussion exception: the PR stays out of draft and
            # keeps its label; only the feedback is delivered.
            effective = "comment"
        elif action == "close":
            details["skip_close"] = True
    details.update(
        failed_checks=sig.failed,
        conflict=sig.conflict,
        unresolved_threads=len(sig.threads),
        ready_label=ready,
        strip_ready_label=strip,
        merit_discussion=merit and ready,
    )
    if effective != action:
        details["degraded_from"] = action
    return _row(pr, row, "deterministic_flag", effective, reason, **details)


def classify(
    prs: list[PR],
    cfg: Config,
    opts: Options,
    people: Maintainers,
    action_required: dict[str, list[dict[str, Any]]],
    systemic: set[str],
) -> list[Decision]:
    decisions: list[Decision] = []
    survivors: list[tuple[PR, S.Signals]] = []
    for pr in sorted(prs, key=lambda p: p.number):
        cached = opts.session.get(str(pr.number))
        if cached and cached.get("head_sha") == pr.head_sha and cached.get("terminal"):
            decisions.append(
                Decision(pr, "suppressed", reason="Handled earlier this session; head unchanged")
            )
            continue
        sig = S.compute(pr, cfg, opts.now)
        if pr.base in cfg.backport_branches or any(_glob(pr.base, b) for b in cfg.backport_branches):
            decisions.append(Decision(pr, "filtered", filter="backport", reason="Backport branch — Step 0.7"))
            continue
        hit = prefilter(pr, cfg, opts, people, sig)
        if hit:
            decisions.append(Decision(pr, "filtered", filter=hit, reason=FILTER_REASONS[hit]))
            continue
        survivors.append((pr, sig))
    flagged: Counter[str] = Counter(pr.author for pr, sig in survivors if sig.deterministic)
    for pr, sig in survivors:
        decision = decide(pr, cfg, opts, sig, flagged, action_required, systemic)
        if opts.authors == "collaborators" and decision.action == "draft":
            decision.details["degraded_from"] = "draft"
            decision.action = "comment"
        decisions.append(decision)
    return decisions


def _glob(name: str, pattern: str) -> bool:
    from fnmatch import fnmatchcase

    return fnmatchcase(name, pattern)


FILTER_REASONS = {
    "F1": "Author is a collaborator",
    "F2": "Author is a bot",
    "F3": "Draft with activity in the last 14 days",
    "F4": "Already marked ready, no regression",
    "F5a": "Maintainer spoke last, under 72h ago — author cooldown",
    "F5b": "Maintainer-to-maintainer ping unanswered",
    "F5c": "Author question to a maintainer unanswered — ball in our court",
    "F6": "Maintainer co-drafting",
}
