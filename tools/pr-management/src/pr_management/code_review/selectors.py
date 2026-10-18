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
"""Selectors and the "my reviews" working list.

`parse` turns the invocation's arguments into a `Selector`; `queue` applies it
to the saved open-PR sweep: the five signals (review-requested, touching-mine,
codeowner, mentioned, reviewed-before) are unioned and deduplicated, every
signal that fired contributes its chip, the post-fetch filters (`area:`,
`collab:`, `team:`, `ready`) apply to the union, and the list is ordered by
last update with PRs whose real CI never ran ranked below the rest.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast

from .. import ci
from ..config import Config
from ..model import COLLABORATOR_ASSOCIATIONS
from ..model import PR as TriagePR
from . import codeowners
from .data import PR

SIGNALS = ("review-requested", "touching-mine", "codeowner", "mentioned", "reviewed-before")
_ONLY = {
    "requested-only": "review-requested",
    "mine-only": "touching-mine",
    "codeowner-only": "codeowner",
    "mentioned-only": "mentioned",
    "reviewed-before-only": "reviewed-before",
}
_DROP = {
    "no-touching-mine": "touching-mine",
    "no-codeowner": "codeowner",
    "no-mentioned": "mentioned",
    "no-reviewed-before": "reviewed-before",
}
_WINDOW = re.compile(r"^(\d+)([dw])$")
_WIP = re.compile(r"\b(wip|do not merge|don't merge|dnm)\b", re.IGNORECASE)


class SelectorError(ValueError):
    pass


@dataclass
class Selector:
    mode: str = "my-reviews"
    pr_number: int | None = None
    area_label: str | None = None
    collab: str | None = None
    team: str | None = None
    ready: bool = False
    signals: list[str] = field(default_factory=lambda: list(SIGNALS))
    since_days: int = 30
    max: int | None = None
    dry_run: bool = False
    inline: str = "on"
    adversarial: str | None = None  # "off" | "tool" | "slash" | None (resolve from config)
    with_reviewers: list[str] = field(default_factory=list)
    with_reviewer: str | None = None
    repo: str | None = None
    lookahead: int = 3
    prefetch: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "pr_number": self.pr_number,
            "area_label": self.area_label,
            "collab": self.collab,
            "team": self.team,
            "ready": self.ready,
            "signals": [] if self.mode == "single-pr" else list(self.signals),
            "since_days": self.since_days,
            "max": self.max,
            "dry_run": self.dry_run,
            "inline": self.inline,
            "adversarial": self.adversarial,
            "with_reviewers": self.with_reviewers,
            "with_reviewer": self.with_reviewer,
            "repo": self.repo,
            "lookahead": self.lookahead,
            "prefetch": self.prefetch,
        }


def parse(args: list[str]) -> Selector:
    sel = Selector()
    only: list[str] = []
    drop: set[str] = set()
    for arg in args:
        key, _, value = arg.partition(":")
        if arg.startswith("pr:"):
            if not value.isdigit():
                raise SelectorError(f"pr:<N> needs a number, got {arg!r}")
            sel.pr_number = int(value)
        elif key == "area" and value:
            sel.area_label = arg
        elif key == "collab" and value in ("true", "false"):
            sel.collab = "collaborator" if value == "true" else "non-collaborator"
        elif key == "team" and value:
            sel.team = value
        elif arg == "ready":
            sel.ready = True
        elif arg in _ONLY:
            only.append(_ONLY[arg])
        elif arg in _DROP:
            drop.add(_DROP[arg])
        elif key == "since":
            match = _WINDOW.match(value)
            if not match:
                raise SelectorError(f"since:<window> takes e.g. 7d or 2w, got {arg!r}")
            sel.since_days = int(match.group(1)) * (7 if match.group(2) == "w" else 1)
        elif key == "max" and value.isdigit():
            sel.max = int(value)
        elif arg == "dry-run":
            sel.dry_run = True
        elif arg in ("inline:off", "body-only"):
            sel.inline = "off"
        elif arg == "no-adversarial":
            sel.adversarial = "off"
        elif key == "with-reviewers" and value:
            sel.with_reviewers = [v for v in value.split(",") if v]
        elif key == "with-reviewer" and value:
            sel.with_reviewer = value
        elif key == "repo" and re.match(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$", value):
            sel.repo = value
        elif key == "lookahead" and value.isdigit():
            sel.lookahead = int(value)
        elif arg == "no-prefetch":
            sel.prefetch = False
        else:
            raise SelectorError(f"unknown selector or flag {arg!r}")
    if only:
        sel.signals = [s for s in SIGNALS if s in only]
    sel.signals = [s for s in sel.signals if s not in drop]
    if sel.pr_number is not None:
        sel.mode = "single-pr"
    elif sel.team:
        sel.mode = "team"
    elif sel.ready:
        sel.mode = "ready"
    elif sel.area_label:
        sel.mode = "area"
    return sel


def matches_area(labels: tuple[str, ...], pattern: str) -> bool:
    if "*" in pattern:
        prefix = pattern.rstrip("*")
        return any(label.startswith(prefix) for label in labels)
    return pattern in labels


def _mention(viewer: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w@.])@" + re.escape(viewer) + r"(?![\w-])", re.IGNORECASE)


def mentioned_in(pr: PR, viewer: str) -> str | None:
    token = _mention(viewer)
    if token.search(pr.body):
        return "body"
    if any(token.search(body) for _, body in pr.comments):
        return "comment"
    if any(token.search(r.body) or any(token.search(c) for c in r.comment_bodies) for r in pr.reviews):
        return "review"
    if any(token.search(c.message) for c in pr.commits):
        return "commit"
    return None


def _relative(when: dt.datetime | None, now: dt.datetime) -> str:
    if when is None:
        return "earlier"
    days = (now - when).days
    if days <= 0:
        hours = max(1, int((now - when).total_seconds() // 3600))
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return f"{days} day{'s' if days != 1 else ''} ago"


def _first(paths: list[str]) -> str:
    return paths[0] if len(paths) == 1 else f"{paths[0]} +{len(paths) - 1} more"


def real_ci(pr: PR, cfg: Config) -> bool:
    """The shared Real-CI guard (`ci.real_ci_ran`) reads only the check contexts."""
    return ci.real_ci_ran(cast(TriagePR, SimpleNamespace(contexts=pr.contexts)), cfg)


@dataclass
class Entry:
    pr: PR
    chips: list[str]
    skip: str | None = None
    ask: str | None = None
    real_ci: bool = True


def signals_for(
    pr: PR,
    sel: Selector,
    viewer: str,
    active_set: set[str],
    rules: list[codeowners.Rule],
    viewer_teams: set[str],
    now: dt.datetime,
) -> list[str]:
    chips: list[str] = []
    if "review-requested" in sel.signals and viewer.lower() in (u.lower() for u in pr.requested_users):
        chips.append("review-requested")
    if "touching-mine" in sel.signals and pr.author.lower() != viewer.lower():
        touched = [f for f in pr.files if f in active_set]
        if touched:
            chips.append(f"touches: {_first(touched)}")
    if "codeowner" in sel.signals and rules:
        owned = [f for f in pr.files if codeowners.owns(codeowners.owners_of(rules, f), viewer, viewer_teams)]
        if owned:
            chips.append(f"codeowner: {_first(owned)}")
    if "mentioned" in sel.signals:
        where = mentioned_in(pr, viewer)
        if where:
            chips.append(f"mentioned-in: {where}")
    if "reviewed-before" in sel.signals:
        mine = [r for r in pr.reviews if r.author.lower() == viewer.lower()]
        if mine:
            latest = max((r.submitted for r in mine if r.submitted), default=None)
            chips.append(f"reviewed-before: {_relative(latest, now)}")
    return chips


def _skip(pr: PR, viewer: str) -> tuple[str | None, str | None]:
    """(auto-skip reason, ask reason) for a PR on the list."""
    if pr.author.lower() == viewer.lower():
        return "self-authored", None
    approvals = [r for r in pr.reviews if r.author.lower() == viewer.lower() and r.state == "APPROVED"]
    if approvals:
        latest = max(approvals, key=lambda r: r.submitted or dt.datetime.min.replace(tzinfo=dt.UTC))
        if latest.commit and pr.head_sha and latest.commit == pr.head_sha:
            return "prior-approval-current-sha", None
        return None, "prior-approval-stale-sha"
    if pr.changed_files == 0 or (pr.additions + pr.deletions) == 0:
        return "zero-diff", None
    if pr.is_draft:
        return None, "draft"
    if _WIP.search(pr.title):
        return None, "wip-title"
    return None, None


def queue(
    prs: list[PR],
    sel: Selector,
    cfg: Config,
    viewer: str,
    active_set: set[str],
    rules: list[codeowners.Rule],
    viewer_teams: set[str],
    now: dt.datetime,
) -> list[Entry]:
    entries: list[Entry] = []
    for pr in prs:
        if sel.mode == "single-pr":
            if pr.number != sel.pr_number:
                continue
            chips = signals_for(pr, sel, viewer, active_set, rules, viewer_teams, now)
        else:
            if pr.is_draft:
                continue  # drafts are only reviewed through pr:<N>
            if sel.team:
                wanted = sel.team.lower()
                if not any(
                    t.lower() in (wanted, wanted.split("/")[-1]) or t.lower().endswith("/" + wanted)
                    for t in pr.requested_teams
                ):
                    continue
                chips = [f"team-requested: {sel.team}"]
            elif sel.ready:
                if cfg.ready_label not in pr.labels:
                    continue
                chips = ["ready"]
            else:
                chips = signals_for(pr, sel, viewer, active_set, rules, viewer_teams, now)
                if not chips:
                    continue
            if sel.area_label and not matches_area(pr.labels, sel.area_label):
                continue
            if sel.collab == "collaborator" and pr.association not in COLLABORATOR_ASSOCIATIONS:
                continue
            if sel.collab == "non-collaborator" and pr.association in COLLABORATOR_ASSOCIATIONS:
                continue
        if pr.association not in COLLABORATOR_ASSOCIATIONS:
            chips.append("external")
        skip, ask = _skip(pr, viewer)
        entries.append(Entry(pr, chips, skip=skip, ask=ask, real_ci=real_ci(pr, cfg)))
    oldest = dt.datetime.min.replace(tzinfo=dt.UTC)
    entries.sort(key=lambda e: (not e.real_ci, -(e.pr.updated or oldest).timestamp()))
    if sel.max is not None:
        reviewable = [e for e in entries if e.skip is None][: sel.max]
        entries = reviewable + [e for e in entries if e.skip is not None]
    return entries
