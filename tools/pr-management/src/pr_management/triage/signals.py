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
"""The precondition glossary of the triage decision table, as functions of one PR."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from .. import ci, markers
from ..config import Config
from ..model import COLLABORATOR_ASSOCIATIONS, FIRST_TIME_ASSOCIATIONS, PR, Thread
from ..people import Maintainers, is_bot, is_copilot

MENTION = re.compile(r"(?<![\w`/])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:/[A-Za-z0-9_.-]+)?)")

SECURITY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("CVE ID", r"\bCVE-\d{4}-\d+\b"),
    *(
        (phrase, r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b")
        for phrase in (
            "security vulnerability",
            "security issue",
            "security fix",
            "security bug",
            "security flaw",
            "security patch",
            "arbitrary code execution",
            "remote code execution",
            "SQL injection",
            "path traversal",
            "directory traversal",
            "privilege escalation",
            "auth bypass",
            "authentication bypass",
            "authorization bypass",
            "insecure deserialization",
            "heap overflow",
            "buffer overflow",
            "use-after-free",
            "exploitable",
            "exploit",
        )
    ),
    ("RCE", r"\bRCE\b"),
    ("XSS", r"\bXSS\b"),
    ("CSRF", r"\bCSRF\b"),
    ("SSRF", r"\bSSRF\b"),
)

CONFLICT_WINDOW_AUTHOR_COOLDOWN = dt.timedelta(hours=72)
F5B_WINDOW = 5
F6_MIN_CHARS = 80
F3_ACTIVITY = dt.timedelta(days=14)
TOO_FRESH = dt.timedelta(minutes=30)
ABANDONED = dt.timedelta(days=30)
FOLLOW_UP_PUSH = dt.timedelta(hours=24)
MAX_FLAKY_FAILURES = 2
MAX_COMMITS_BEHIND = 50
FLAGGED_AUTHOR_THRESHOLD = 3


def mentions(text: str) -> list[str]:
    return MENTION.findall(text or "")


def collaborator_threads(pr: PR) -> list[Thread]:
    """Unresolved threads opened by a collaborator (the qualifier rows 14-20 share)."""
    return [
        t
        for t in pr.threads
        if not t.resolved and t.first is not None and t.first.association in COLLABORATOR_ASSOCIATIONS
    ]


def reviewers(threads: list[Thread]) -> list[str]:
    seen: list[str] = []
    for thread in threads:
        if thread.first is not None and thread.first.author not in seen:
            seen.append(thread.first.author)
    return seen


@dataclass
class Signals:
    """Everything the table reads about one PR, computed once."""

    failed: list[str]
    grace: dict[str, object]
    ci_signal: bool
    conflict: bool
    threads: list[Thread]
    real_ci: bool
    first_time: bool
    security: list[dict[str, str]] = field(default_factory=list)

    @property
    def kinds(self) -> set[str]:
        found = set()
        if self.conflict:
            found.add("conflict")
        if self.ci_signal:
            found.add("ci")
        if self.threads:
            found.add("threads")
        return found

    @property
    def deterministic(self) -> bool:
        return bool(self.kinds)


def compute(pr: PR, cfg: Config, now: dt.datetime) -> Signals:
    failed = ci.failed_checks(pr)
    grace = ci.grace(pr, now)
    ci_signal = pr.rollup_state == "FAILURE" and bool(failed) and not grace["in_grace"]
    return Signals(
        failed=failed,
        grace=grace,
        ci_signal=ci_signal,
        conflict=pr.mergeable == "CONFLICTING",
        threads=collaborator_threads(pr),
        real_ci=ci.real_ci_ran(pr, cfg),
        first_time=pr.association in FIRST_TIME_ASSOCIATIONS,
        security=security_matches(pr),
    )


def security_matches(pr: PR) -> list[dict[str, str]]:
    """Title, body (the triage fold excluded) and commit messages against the security patterns."""
    body = markers.FOLD_RE.sub("", pr.body)
    places = [("title", pr.title), ("body", body)]
    places += [
        (f"commit {c.oid[:7]}: {c.message.splitlines()[0][:72] if c.message else ''}", c.message)
        for c in pr.commits
    ]
    found: list[dict[str, str]] = []
    for where, text in places:
        for label, pattern in SECURITY_PATTERNS:
            match = re.search(pattern, text or "", flags=re.IGNORECASE)
            if match:
                found.append({"where": where, "pattern": label, "match": match.group(0)})
    return found


# --- pre-filters --------------------------------------------------------------


def _feedback_items(pr: PR) -> list[tuple[dt.datetime, str, str]]:
    items = [(c.created, c.author, c.association) for c in pr.all_comments() if c.created]
    items += [(r.submitted, r.author, r.association) for r in pr.reviews if r.submitted and r.body.strip()]
    return sorted(items, key=lambda i: i[0], reverse=True)


def f5a(pr: PR, now: dt.datetime, people: Maintainers) -> bool:
    items = _feedback_items(pr)
    if not items:
        return False
    at, author, association = items[0]
    if not people.is_maintainer(author, association):
        return False
    if now - at >= CONFLICT_WINDOW_AUTHOR_COOLDOWN:
        return False
    return pr.head_committed is None or at > pr.head_committed


def f5b(pr: PR, people: Maintainers) -> bool:
    comments = [
        c
        for c in reversed(pr.all_comments())
        if c.created and c.author != pr.author and people.is_maintainer(c.author, c.association)
    ][:F5B_WINDOW]
    for comment in comments:
        named = [m for m in mentions(comment.body) if m.lower() != pr.author.lower()]
        if not named:
            continue
        replied = set()
        for later in pr.all_comments():
            if later.created and comment.created and later.created > comment.created:
                replied.add(later.author.lower())
        for review in pr.reviews:
            if review.submitted and comment.created and review.submitted > comment.created:
                replied.add(review.author.lower())
        if not any(m.lower() in replied for m in named):
            return True
    return False


def f5c(pr: PR, cfg: Config, people: Maintainers) -> bool:
    human = [c for c in pr.all_comments() if c.created and not is_bot(c.author)]
    if not human or human[-1].author != pr.author:
        return False
    last = human[-1]
    team = (cfg.committers_team or "").lower()
    named = mentions(last.body)
    hit = False
    for name in named:
        if "/" in name:
            hit = True
            continue
        if name.lower() == pr.author.lower():
            continue
        known = people.known(name)
        if known is None:
            # Unknown mentioned login: decide conservatively, resolve and re-run.
            people.unresolved.add(name)
            hit = True
        elif known:
            hit = True
    if team and team.split("/")[-1] in last.body.lower():
        hit = True
    if not hit:
        return False
    after = last.created
    if after is None:
        return True
    if any(
        c.created and c.created > after and people.is_maintainer(c.author, c.association)
        for c in pr.all_comments()
    ):
        return False
    return not any(
        r.submitted and r.submitted > after and people.is_maintainer(r.author, r.association)
        for r in pr.reviews
    )


def f6(pr: PR, viewer: str) -> bool:
    if not pr.is_draft or pr.head_committed is None:
        return False
    for review in pr.reviews:
        if (
            review.association in COLLABORATOR_ASSOCIATIONS
            and review.author != viewer
            and review.state in ("COMMENTED", "CHANGES_REQUESTED", "APPROVED")
            and review.submitted is not None
            and review.submitted > pr.head_committed
            and review.body.strip()
        ):
            return True
    for comment in pr.comments:
        prose = MENTION.sub("", comment.body).strip()
        if (
            comment.association in COLLABORATOR_ASSOCIATIONS
            and comment.author != viewer
            and len(prose) >= F6_MIN_CHARS
            and comment.created is not None
            and comment.created > pr.head_committed
        ):
            return True
    return False


def f4_skips(pr: PR, cfg: Config, sig: Signals) -> bool:
    """Already marked ready and no regression since the label went on."""
    if cfg.ready_label not in pr.labels:
        return False
    clean = pr.rollup_state == "SUCCESS" and not sig.conflict and not sig.threads
    if clean:
        return True
    added = pr.label_added_at(cfg.ready_label)
    if added is None:
        return False
    if sig.conflict:
        return False
    if pr.rollup_state in ("FAILURE", "ERROR"):
        failing = [c for c in pr.contexts if ci.context_failed(c)]
        if not failing or any((c.started or c.completed or added) > added for c in failing):
            return False
    return not any(t.first and t.first.created and t.first.created > added for t in sig.threads)


# --- table preconditions ------------------------------------------------------


def copilot_review_stale(pr: PR, cfg: Config, now: dt.datetime) -> str | None:
    """The URL of an unresolved Copilot thread at least `stale_copilot_days` old with no author reply."""
    window = dt.timedelta(days=cfg.stale_copilot_days)
    for thread in pr.threads:
        first = thread.first
        if thread.resolved or first is None or first.created is None or not is_copilot(first.author):
            continue
        if now - first.created < window:
            continue
        if markers.author_replied_after(pr, first.created):
            continue
        return first.url or pr.url
    return None


def likely_addressed(pr: PR, threads: list[Thread]) -> bool:
    firsts = [t.first.created for t in threads if t.first and t.first.created]
    if not firsts or pr.head_committed is None or pr.head_committed <= max(firsts):
        return False
    for thread in threads:
        first = thread.first
        if first is None or first.created is None:
            return False
        replied = any(
            c.author == pr.author and c.created and c.created > first.created for c in thread.comments
        )
        if not replied and pr.head_committed <= first.created:
            return False
    return True


def stale_review(pr: PR, now: dt.datetime) -> list[str]:
    """Reviewers whose CHANGES_REQUESTED the author pushed past without a follow-up."""
    if pr.head_committed is None:
        return []
    found: list[str] = []
    for review in pr.reviews:
        if review.state != "CHANGES_REQUESTED" or review.submitted is None:
            continue
        if pr.head_committed <= review.submitted:
            continue
        if now - pr.head_committed < FOLLOW_UP_PUSH:
            continue
        followed = False
        for comment in pr.all_comments():
            if comment.created is None:
                continue
            if (
                comment.author == pr.author
                and comment.created > review.submitted
                and review.author.lower() in (m.lower() for m in mentions(comment.body))
            ):
                followed = True
            if comment.author == review.author and comment.created > pr.head_committed:
                followed = True
        if not followed:
            found.append(review.author)
    return found


def first_time_no_real_ci(pr: PR, sig: Signals) -> bool:
    if not sig.first_time:
        return False
    if pr.rollup_state in (None, "EXPECTED") or not pr.contexts:
        return True
    return pr.rollup_state == "SUCCESS" and not sig.real_ci


def first_time_stale_abandoned(pr: PR, cfg: Config, sig: Signals, now: dt.datetime) -> bool:
    if not sig.first_time or pr.head_committed is None:
        return False
    marker = markers.any_triage_marker(pr, cfg.marker)
    if marker is None or pr.head_committed > marker.at:
        return False
    return now - pr.head_committed >= ABANDONED


def unsettled(pr: PR, sig: Signals) -> bool:
    """Row 22: the server-side state has not settled."""
    if pr.mergeable == "UNKNOWN":
        return True
    if pr.rollup_state == "SUCCESS" and sig.failed:
        return True
    return pr.rollup_state == "FAILURE" and not sig.failed
