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
"""Step 0.5 (bot-draft promotion) and Step 5 (the stale sweeps) of pr-management-triage.

A pure function of the fetched state, run after the decision table. A sweep
decision replaces the table decision for its PR; a sweep only looks at PRs the
table did not act on (a `skip`, a row-5 deferral, or the F3 / F6 pre-filters,
which the table notes "stale sweeps may still pull back in"), plus the row-1
PRs Sweep 3 retires and the row-14b PRs Sweep 5 escalates. Active-conversation
pre-filters (F5a/F5b/F5c), collaborator and bot PRs, and backport PRs are never
swept; ready-labelled PRs belong to Sweep 4 alone.

Sweep 4 re-classifies a stale ready PR against the live decision table. The
batched `mergeable` is unreliable for that queue, so it needs a live liveness
read (`gql-pr-liveness`, saved as `liveness-<N>.json`, put on `pr.extra`
by the caller); without one the PR comes back as `needs`.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any

from .. import markers
from ..config import Config
from ..model import COLLABORATOR_ASSOCIATIONS, PR
from ..people import Maintainers, is_bot
from . import signals as S
from .classify import decide
from .types import Decision, Options

#: Sweep 4's label-age and quiet windows, and Sweep 5's reply window.
SWEEP_WINDOW = dt.timedelta(days=7)

#: Base decisions a staleness sweep (1-3, 5) may replace.
SWEEPABLE_FILTERS = frozenset({"F3", "F6"})

#: Live `mergeStateStatus` values that mean a clean branch (`blocked` is only the missing approval).
HEALTHY_STATES = frozenset({"CLEAN", "HAS_HOOKS", "UNSTABLE", "BEHIND", "BLOCKED"})

#: Table rows whose next move is the author's, and the author-facing action Sweep 4 posts with the strip.
AUTHOR_COURT: dict[str, tuple[str, str]] = {
    "9": ("ping", "merge conflict — author must rebase"),
    "12": ("comment", "failing static checks — code fix needed"),
    "12b": ("comment", "failing static checks — code fix needed"),
    "17": ("comment", "quality issues — code fix needed"),
    "8": ("comment", "quality issues — code fix needed"),
    "2": ("comment", "unaddressed Copilot review — code fix needed"),
    "15": ("ping", "unresolved threads, author not engaged"),
    "14c": ("request-author-confirmation", "awaiting author readiness confirmation"),
}

#: Table actions that are a maintainer's move and are performed with the label kept.
MAINTAINER_ACTIONS = frozenset({"approve-workflow", "rerun", "rebase"})


def liveness_from(document: Any) -> dict[str, Any] | None:
    """The pull request object of a saved `gql-pr-liveness` read (raw or already unwrapped)."""
    if not isinstance(document, dict):
        return None
    pr = ((document.get("data") or {}).get("repository") or {}).get("pullRequest")
    if pr is None and "mergeable" in document:
        pr = document
    return pr if isinstance(pr, dict) else None


def _decision(pr: PR, row: str, classification: str, action: str, reason: str, **details: Any) -> Decision:

    outcome = "skip" if action == "skip" else "act"
    return Decision(
        pr, outcome, row=row, classification=classification, action=action, reason=reason, details=details
    )


def last_author_activity(pr: PR) -> dt.datetime | None:
    stamps = [pr.head_committed] + [c.created for c in pr.all_comments() if c.author == pr.author]
    found = [s for s in stamps if s is not None]
    return max(found) if found else None


def last_triage_at(
    pr: PR, cfg: Config, viewer: str, people: Maintainers
) -> tuple[dt.datetime | None, list[str]]:
    """The newest triage marker in either channel, and the marker authors still to resolve.

    A comment marker starts Sweep 1a's close clock only when its author is the
    viewer or passes the maintainer test; an unresolved author does not start it
    and is returned so the skill can resolve it.
    """
    stamps: list[dt.datetime] = []
    unresolved: list[str] = []
    fold = markers.parse_fold(pr.body)
    if fold is not None and fold.triaged is not None:
        stamps.append(fold.triaged)
    for comment in pr.comments:
        if comment.created is None or cfg.marker not in comment.body or comment.author == pr.author:
            continue
        if comment.association not in COLLABORATOR_ASSOCIATIONS:
            continue
        if comment.author == viewer:
            stamps.append(comment.created)
            continue
        known = people.known(comment.author)
        if known is None:
            people.unresolved.add(comment.author)
            unresolved.append(comment.author)
        elif known:
            stamps.append(comment.created)
    return (max(stamps) if stamps else None), unresolved


def _weeks(delta: dt.timedelta) -> int:
    return max(1, delta.days // 7)


def _quiet_since(pr: PR) -> dt.datetime | None:
    stamps = [pr.head_committed]
    stamps += [c.created for c in pr.all_comments()]
    stamps += [r.submitted for r in pr.reviews]
    found = [s for s in stamps if s is not None]
    return max(found) if found else None


def bot_drafts(
    prs: list[PR], suppressed: set[int], action_required: dict[str, list[dict[str, Any]]]
) -> list[Decision]:
    """Step 0.5: every open bot-authored draft, proposed for promotion."""
    found: list[Decision] = []
    for pr in prs:
        if pr.number in suppressed or not pr.is_draft or not is_bot(pr.author):
            continue
        pending = action_required.get(pr.head_sha, [])
        if pending:
            found.append(
                _decision(
                    pr,
                    "0.5",
                    "pending_workflow_approval",
                    "approve-workflow",
                    "Bot draft with workflow runs awaiting approval — approve CI before promoting",
                    runs=pending,
                    rerouted_from="promote-bot-draft",
                )
            )
            continue
        found.append(
            _decision(
                pr,
                "0.5",
                "bot_draft",
                "promote-bot-draft",
                "Bot-authored draft — mark ready for review and apply the ready label",
            )
        )
    return found


def _sweep4(
    pr: PR,
    cfg: Config,
    opts: Options,
    people: Maintainers,
    action_required: dict[str, list[dict[str, Any]]],
    systemic: set[str],
) -> Decision | None:

    now = opts.now
    added = pr.label_added_at(cfg.ready_label)
    if added is not None and now - added < SWEEP_WINDOW:
        return None
    if added is None and (pr.created is None or now - pr.created < SWEEP_WINDOW):
        return None
    quiet = _quiet_since(pr)
    if quiet is not None and now - quiet < SWEEP_WINDOW:
        return None
    if S.f5c(pr, cfg, people):
        return _decision(
            pr,
            "sweep-4-keep",
            "stale_ready_label",
            "skip",
            "Keep label — the author asked a maintainer and is waiting on us",
        )
    live = pr.extra.get("liveness")
    if not live:
        return Decision(
            pr,
            "needs",
            row="sweep-4",
            needs=[
                {"op": "gql-pr-liveness", "params": [str(pr.number)], "save": f"liveness-{pr.number}.json"}
            ],
            reason="Sweep 4 needs a live mergeability read",
        )
    if live.get("headRefOid") and live["headRefOid"] != pr.head_sha:
        return _decision(
            pr,
            "sweep-4-keep",
            "stale_ready_label",
            "skip",
            "Head moved since the fetch — re-examine next sweep",
        )
    mergeable = str(live.get("mergeable") or "UNKNOWN").upper()
    state = str(live.get("mergeStateStatus") or "UNKNOWN").upper()
    if mergeable == "CONFLICTING" or state == "DIRTY":
        pr.mergeable = "CONFLICTING"
    elif mergeable == "MERGEABLE" and state in HEALTHY_STATES:
        pr.mergeable = "MERGEABLE"
    else:
        return _decision(
            pr,
            "sweep-4-keep",
            "stale_ready_label",
            "skip",
            "Mergeability not settled on the live read — defer to the next sweep",
        )

    sig = S.compute(pr, cfg, now)
    table = decide(pr, cfg, opts, sig, Counter(), action_required, systemic)
    if table.outcome == "needs":
        table.row = table.row or "sweep-4"
        return table
    court = AUTHOR_COURT.get(table.row or "")
    if court is not None:
        author_action, trigger = court
        return _decision(
            pr,
            "sweep-4",
            "stale_ready_label",
            "strip-ready-label",
            f"Ready label stale ≥ {SWEEP_WINDOW.days} days, {trigger} — strip and hand back",
            author_action=author_action,
            table_row=table.row,
            table_reason=table.reason,
            audit_marker=True,
            fold_into_audit=author_action in ("ping", "request-author-confirmation"),
            failed_checks=table.details.get("failed_checks"),
            reviewers=table.details.get("reviewers"),
        )
    if table.action in MAINTAINER_ACTIONS:
        table.details.update(sweep="sweep-4", keep_ready_label=True, strip_ready_label=False)
        return table
    return _decision(
        pr,
        "sweep-4-keep",
        "stale_ready_label",
        "skip",
        f"Keep label — next move is a maintainer's ({table.reason})",
        table_row=table.row,
    )


def sweep(
    prs: list[PR],
    decisions: list[Decision],
    cfg: Config,
    opts: Options,
    people: Maintainers,
    action_required: dict[str, list[dict[str, Any]]],
    systemic: set[str] | None = None,
) -> list[Decision]:
    """Bot-draft promotion and Sweeps 1-5; each result replaces its PR's table decision."""
    systemic = systemic or set()
    by_number = {d.pr.number: d for d in decisions}
    suppressed = {n for n, d in by_number.items() if d.outcome == "suppressed"}
    out = bot_drafts(prs, suppressed, action_required)
    now = opts.now
    for pr in sorted(prs, key=lambda p: p.number):
        base = by_number.get(pr.number)
        if base is None or base.outcome in ("suppressed", "needs") or is_bot(pr.author):
            continue
        if base.filter in ("F1", "F2", "backport"):
            continue
        ready = cfg.ready_label in pr.labels
        if ready:
            if base.outcome == "act":
                continue
            found = _sweep4(pr, cfg, opts, people, action_required, systemic)
            if found is not None:
                out.append(found)
            continue
        if base.filter is not None and base.filter not in SWEEPABLE_FILTERS:
            continue
        sweep3 = base.row == "1" and base.classification == "pending_workflow_approval"
        sweep5 = base.row == "14b"
        # A stale draft is Sweep 1's whatever the table proposed for it: the
        # table's action targets a live PR, and F3 already let the draft through
        # only because it has been quiet for two weeks.
        if base.outcome == "act" and not sweep3 and not pr.is_draft:
            continue
        if S.f5c(pr, cfg, people):
            continue
        found = _stale(pr, base, cfg, opts, people, sweep3=sweep3, sweep5=sweep5, now=now)
        if found is not None:
            out.append(found)
    return out


def _stale(
    pr: PR,
    base: Decision,
    cfg: Config,
    opts: Options,
    people: Maintainers,
    *,
    sweep3: bool,
    sweep5: bool,
    now: dt.datetime,
) -> Decision | None:

    idle = now - pr.updated if pr.updated else dt.timedelta(0)
    if pr.is_draft:
        triaged, unresolved = last_triage_at(pr, cfg, opts.viewer, people)
        if unresolved:
            return Decision(
                pr,
                "needs",
                row="sweep-1",
                needs=[
                    {"op": "upstream-permission", "params": [login], "save": f"permission-{login}"}
                    for login in unresolved
                ],
                reason="A triage-marker author's maintainer status decides the close clock",
            )
        if triaged is not None:
            activity = last_author_activity(pr)
            if now - triaged >= dt.timedelta(days=cfg.stale_draft_triaged_days) and (
                activity is None or activity <= triaged
            ):
                days = (now - triaged).days
                return _decision(
                    pr,
                    "sweep-1a",
                    "stale_draft",
                    "close-stale",
                    f"Draft triaged {days} days ago, no author reply or push — close with stale-draft notice",
                    variant="triaged",
                    days_since_triage=days,
                )
        elif idle >= dt.timedelta(days=cfg.stale_draft_untriaged_days):
            return _decision(
                pr,
                "sweep-1b",
                "stale_draft",
                "close-stale",
                f"Draft inactive for {_weeks(idle)} weeks — close with stale-draft notice",
                variant="untriaged",
                days_idle=idle.days,
            )
        return None
    if sweep3:
        pushed = now - pr.head_committed if pr.head_committed else idle
        if idle >= dt.timedelta(days=cfg.stale_workflow_approval_days) and pushed >= dt.timedelta(
            days=cfg.stale_workflow_approval_days
        ):
            return _decision(
                pr,
                "sweep-3",
                "stale_workflow_approval",
                "draft",
                f"Awaiting workflow approval for {_weeks(idle)} weeks, no activity — convert to draft",
                days_idle=idle.days,
            )
        return None
    if sweep5:
        requested = markers.confirmation_request(pr, opts.viewer)
        if (
            requested is not None
            and not markers.author_replied_after(pr, requested)
            and (now - requested >= SWEEP_WINDOW)
        ):
            days = (now - requested).days
            return _decision(
                pr,
                "sweep-5",
                "stale_author_confirm_request",
                "ping",
                f"Author confirmation requested {days} days ago, no reply — escalating to plain "
                "reviewer ping",
                days_since_request=days,
                reviewers=S.reviewers(S.collaborator_threads(pr)),
            )
    if idle >= dt.timedelta(days=cfg.inactive_open_days):
        return _decision(
            pr,
            "sweep-2",
            "inactive_open",
            "draft",
            f"Open non-draft inactive for {_weeks(idle)} weeks — convert to draft",
            days_idle=idle.days,
        )
    return None
