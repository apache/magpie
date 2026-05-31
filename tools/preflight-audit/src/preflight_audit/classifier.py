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
"""Pure classifier for the bulk-mode pre-flight no-op skip decision.

This module is the executable spec of the rule table documented in
[`.claude/skills/security-issue-sync/bulk-mode.md`](../../../.claude/skills/security-issue-sync/bulk-mode.md).
Both representations must stay in sync — a PR that changes one
should change the other.

The classifier is intentionally split from the fetch layer
(:mod:`preflight_audit.fetch`) so tests can drive it with synthetic
issue dicts and replays of canned GraphQL responses, without any
network calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

# The skill-marker prefix every framework-authored tracker comment
# carries (status-rollup, release-manager hand-off, wrap-up). Keeps
# the classifier in lock-step with `tools/github/status-rollup.md`.
SKILL_MARKER_PREFIX = "<!-- apache-steward: "

# Bot logins always treated as bot-equivalent regardless of comment body.
# Extend per-adopter via the override file (see bulk-mode.md).
_BUILTIN_BOT_LOGINS: frozenset[str] = frozenset(
    {
        "github-actions[bot]",
        "dependabot[bot]",
    }
)


class Decision(StrEnum):
    """The three possible classifier outcomes."""

    DISPATCH = "dispatch"
    DISPATCH_URGENT = "dispatch-urgent"
    SKIP_NOOP = "skip-noop"


@dataclass(frozen=True)
class IssueState:
    """Lightweight snapshot the classifier needs for one tracker.

    Mirrors the GraphQL response shape produced by
    :func:`preflight_audit.fetch.build_query` so the fetch layer can
    instantiate these directly from `gh api graphql` output.
    """

    number: int
    state: str  # "OPEN" | "CLOSED"
    closed_at: datetime | None
    updated_at: datetime
    labels: frozenset[str]
    last_comment_author: str | None
    last_comment_created_at: datetime | None
    last_comment_body: str | None


@dataclass(frozen=True)
class Classification:
    """The classifier's output for one tracker."""

    issue: IssueState
    decision: Decision
    reason: str
    last_is_skill_or_bot: bool


def _is_skill_or_bot(
    login: str | None,
    body: str | None,
    extra_bot_logins: frozenset[str],
) -> bool:
    """Return True when the comment counts as bot-equivalent.

    Three signals (any one is enough):

    1. The login is a literal GitHub App account (ends in ``[bot]``
       or matches a built-in / override-listed bot login).
    2. The body begins with the framework's skill marker — see
       :data:`SKILL_MARKER_PREFIX`. This is the signal that catches
       sync-skill writes on single-operator trackers where the skill
       runs under the operator's own user account.
    3. The login is in the adopter's override-supplied
       ``extra_bot_logins`` set (for personal-account bots).
    """
    if login is not None:
        if login in _BUILTIN_BOT_LOGINS or login in extra_bot_logins:
            return True
        if login.endswith("[bot]"):
            return True
    return bool(body is not None and body.lstrip().startswith(SKILL_MARKER_PREFIX))


def _days_between(now: datetime, then: datetime | None) -> float | None:
    if then is None:
        return None
    return (now - then).total_seconds() / 86400


def classify_issue(
    iss: IssueState,
    now: datetime,
    extra_bot_logins: frozenset[str] = frozenset(),
) -> Classification:
    """Apply the rule table to one tracker.

    Rules are checked **in order** — the first match wins. This is
    the executable spec of the table in
    `bulk-mode.md` § Pre-flight no-op classifier.
    """
    last_was_skill = _is_skill_or_bot(
        iss.last_comment_author,
        iss.last_comment_body,
        extra_bot_logins,
    )
    updated_age = _days_between(now, iss.updated_at)
    last_comment_age = _days_between(now, iss.last_comment_created_at)
    closed_age = _days_between(now, iss.closed_at)

    # Rule 1: 7-day updatedAt safety override — but only when the
    # recent activity wasn't itself a skill write. On a tracker the
    # skill just touched, the recently-bumped updatedAt is the skill's
    # own work; let downstream rules decide.
    if updated_age is not None and updated_age < 7:
        skill_drove_recent_update = last_was_skill and last_comment_age is not None and last_comment_age < 7
        if not skill_drove_recent_update:
            return Classification(
                issue=iss,
                decision=Decision.DISPATCH,
                reason=f"recent human activity (updatedAt {int(updated_age)}d)",
                last_is_skill_or_bot=last_was_skill,
            )

    # Rule 2: dispatch-urgent — a non-skill comment in the last 24h.
    if last_comment_age is not None and last_comment_age < 1 and not last_was_skill:
        return Classification(
            issue=iss,
            decision=Decision.DISPATCH_URGENT,
            reason=f"recent reply from {iss.last_comment_author} (<24h)",
            last_is_skill_or_bot=last_was_skill,
        )

    # Rule 3: closed > 30d ago AND `announced` label → post-announce.
    if iss.state == "CLOSED" and closed_age is not None and closed_age > 30 and "announced" in iss.labels:
        return Classification(
            issue=iss,
            decision=Decision.SKIP_NOOP,
            reason=f"post-announce; closed {int(closed_age)}d ago",
            last_is_skill_or_bot=last_was_skill,
        )

    # Rule 4: closed > 90d ago with no `announced` → stale invalid/dup.
    if iss.state == "CLOSED" and closed_age is not None and closed_age > 90 and "announced" not in iss.labels:
        return Classification(
            issue=iss,
            decision=Decision.SKIP_NOOP,
            reason=f"stale closed {int(closed_age)}d ago (no announce)",
            last_is_skill_or_bot=last_was_skill,
        )

    # Rule 5: open + full lifecycle + skill last → awaiting closure.
    full_set = {"cve allocated", "pr merged", "announced"}
    if iss.state == "OPEN" and full_set.issubset(iss.labels) and last_was_skill:
        age_s = f"{int(last_comment_age)}d" if last_comment_age is not None else "?"
        return Classification(
            issue=iss,
            decision=Decision.SKIP_NOOP,
            reason=f"all phases done; skill-last ({age_s})",
            last_is_skill_or_bot=last_was_skill,
        )

    # Rule 6: open + cve+pr+skill-last → awaiting release.
    if iss.state == "OPEN" and {"cve allocated", "pr merged"}.issubset(iss.labels) and last_was_skill:
        age_s = f"{int(last_comment_age)}d" if last_comment_age is not None else "?"
        return Classification(
            issue=iss,
            decision=Decision.SKIP_NOOP,
            reason=f"awaiting release; skill-last ({age_s})",
            last_is_skill_or_bot=last_was_skill,
        )

    # Rule 7: open + cve+fix-released+skill-last → awaiting advisory.
    if iss.state == "OPEN" and {"cve allocated", "fix released"}.issubset(iss.labels) and last_was_skill:
        age_s = f"{int(last_comment_age)}d" if last_comment_age is not None else "?"
        return Classification(
            issue=iss,
            decision=Decision.SKIP_NOOP,
            reason=f"fix released; awaiting advisory; skill-last ({age_s})",
            last_is_skill_or_bot=last_was_skill,
        )

    # Fall-through: dispatch.
    return Classification(
        issue=iss,
        decision=Decision.DISPATCH,
        reason="-",
        last_is_skill_or_bot=last_was_skill,
    )


def _parse_iso(s: str | None) -> datetime | None:
    if s is None:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _issue_from_node(node: dict[str, Any]) -> IssueState:
    """Build an :class:`IssueState` from a GraphQL issue node."""
    comments = node.get("comments", {}).get("nodes") or []
    last = comments[0] if comments else None
    last_author = None
    last_created = None
    last_body = None
    if last is not None:
        author = last.get("author") or {}
        last_author = author.get("login")
        last_created = _parse_iso(last.get("createdAt"))
        last_body = last.get("body")

    label_nodes = node.get("labels", {}).get("nodes") or []
    labels = frozenset(n["name"] for n in label_nodes)

    return IssueState(
        number=node["number"],
        state=node["state"],
        closed_at=_parse_iso(node.get("closedAt")),
        updated_at=_parse_iso(node["updatedAt"]) or datetime.now(UTC),
        labels=labels,
        last_comment_author=last_author,
        last_comment_created_at=last_created,
        last_comment_body=last_body,
    )


def classify_response(
    response: dict[str, Any],
    now: datetime,
    extra_bot_logins: frozenset[str] = frozenset(),
) -> list[Classification]:
    """Classify every issue in a raw `gh api graphql` response.

    Skips null nodes (issues that 404'd) silently — the caller
    can audit those by comparing against the input issue list.
    """
    repo = response.get("data", {}).get("repository", {}) or {}
    out: list[Classification] = []
    for _alias, node in repo.items():
        if node is None:
            continue
        iss = _issue_from_node(node)
        out.append(classify_issue(iss, now=now, extra_bot_logins=extra_bot_logins))
    return out
