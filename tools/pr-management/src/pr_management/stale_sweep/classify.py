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
"""pr-stale-sweep Steps 1-3: the pool, the per-PR state, one class per PR.

Inactivity is measured from the PR's last *real* activity — creation, a commit,
a comment, a review, a review-thread reply, a label change — never from
`updatedAt`, which this sweep's own nudge would reset. The sweep's own nudge and
close-notice comments are not activity.

Classes, first match wins:

* `SKIP-NO-TIMESTAMPS` — no creation time to measure from.
* `SKIP-READY-LABEL` — carries the ready label: the maintainers' court.
* `SKIP-SECURITY` — a security pattern in the title, body, commit messages or
  the most recent comment: may need confidential handling.
* `SKIP-MAINTAINER-COURT` — the author asked a maintainer a question no
  maintainer answered (the shared F5c test).
* `CLOSE-STALE` — idle ≥ `hard_close_days`; or idle ≥ `close_days` with a
  standing nudge (no author activity since) that is at least
  `NOTICE_FLOOR_DAYS` old.
* `SKIP-NUDGE-PENDING` — a standing nudge whose close window has not run out.
* `REQUEST-UPDATE` — idle ≥ `warn_days` and no standing nudge, including a PR
  already idle past `close_days`: it is nudged first, never closed unwarned.

PRs idle less than `warn_days`, drafts and bot-authored PRs are not candidates.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import model
from ..config import Config
from ..model import PR, parse_time
from ..people import Maintainers, is_bot
from ..triage import signals
from .plan import Plan

NUDGE_MARKER = "<!-- pr-stale-sweep-nudge -->"
CLOSE_MARKER = "<!-- pr-stale-sweep-close -->"
#: However long a PR was idle when it was nudged, the author gets at least this long to answer.
NOTICE_FLOOR_DAYS = 7
#: More candidates than this and the maintainer narrows the sweep first.
CAP = 50

CLASS_DOCS = {
    "REQUEST-UPDATE": "classifications/request-update.md",
    "CLOSE-STALE": "classifications/close-stale.md",
    "SKIP-SECURITY": "classifications/skip-security.md",
    "SKIP-MAINTAINER-COURT": "classifications/skip-maintainer-court.md",
    "SKIP-READY-LABEL": "classifications/skip-ready-label.md",
    "SKIP-NO-TIMESTAMPS": "classifications/skip-no-timestamps.md",
    "SKIP-NUDGE-PENDING": "classifications/skip-nudge-pending.md",
}
ACTING = ("REQUEST-UPDATE", "CLOSE-STALE")


@dataclass
class Item:
    pr: PR
    cls: str
    days_idle: int | None = None
    reason: str = ""
    remaining_days: int | None = None
    nudge_at: dt.datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawComment:
    author: str
    created: dt.datetime | None
    body: str


def raw_comments(node: dict[str, Any]) -> list[RawComment]:
    return [
        RawComment(
            author=str(((c.get("author") or {}).get("login")) or "ghost"),
            created=parse_time(c.get("createdAt")),
            body=str(c.get("body") or ""),
        )
        for c in ((node.get("comments") or {}).get("nodes") or [])
        if c
    ]


def load(paths: list[Path]) -> list[tuple[PR, list[RawComment]]]:
    """PRs from saved pages or single-PR reads, deduplicated by number, with their raw comments."""
    seen: dict[int, tuple[PR, list[RawComment]]] = {}
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        for node in model._pr_nodes(document):
            pr = model.from_node(node)
            seen[pr.number] = (pr, raw_comments(node))
    return [seen[n] for n in sorted(seen)]


def _sweep_comment(comment: RawComment) -> bool:
    return NUDGE_MARKER in comment.body or CLOSE_MARKER in comment.body


def last_activity(pr: PR, raw: list[RawComment]) -> dt.datetime | None:
    """The newest real activity: creation, commits, comments, reviews, thread replies, label changes."""
    stamps: list[dt.datetime] = [t for t in (pr.created, pr.head_committed) if t]
    stamps += [c.committed for c in pr.commits if c.committed]
    stamps += [c.created for c in raw if c.created and not _sweep_comment(c)]
    stamps += [r.submitted for r in pr.reviews if r.submitted]
    stamps += [c.created for t in pr.threads for c in t.comments if c.created]
    stamps += [e.at for e in pr.label_events if e.at]
    return max(stamps) if stamps else None


def standing_nudge(pr: PR, raw: list[RawComment]) -> dt.datetime | None:
    """The newest nudge with no author activity after it (author activity resets the clock)."""
    nudges = [c.created for c in raw if c.created and c.author != pr.author and NUDGE_MARKER in c.body]
    if not nudges:
        return None
    at = max(nudges)
    if pr.head_committed is not None and pr.head_committed > at:
        return None
    authored = [c.created for c in raw if c.author == pr.author and c.created]
    authored += [r.submitted for r in pr.reviews if r.author == pr.author and r.submitted]
    authored += [c.created for t in pr.threads for c in t.comments if c.author == pr.author and c.created]
    if any(t > at for t in authored):
        return None
    return at


def _days(delta: dt.timedelta) -> int:
    return max(0, delta.days)


def classify_one(
    pr: PR, raw: list[RawComment], plan: Plan, cfg: Config, people: Maintainers, now: dt.datetime
) -> Item | None:
    """One class for one PR, or None when it is not a candidate at all."""
    if pr.created is None:
        return Item(pr, "SKIP-NO-TIMESTAMPS", reason="GitHub returned no timestamps for this PR")
    last = last_activity(pr, raw)
    assert last is not None
    idle = _days(now - last)
    if idle < plan.warn_days:
        return None
    item = Item(pr, "", days_idle=idle)
    if cfg.ready_label in pr.labels:
        item.cls, item.reason = "SKIP-READY-LABEL", f"Carries `{cfg.ready_label}` — waiting on maintainers"
        return item
    found = signals.security_matches(pr)
    if raw:
        latest = max(raw, key=lambda c: c.created or dt.datetime.min.replace(tzinfo=dt.UTC))
        probe = model.from_node({"number": pr.number, "title": "", "body": latest.body})
        found += [
            {**m, "where": "most recent comment"}
            for m in signals.security_matches(probe)
            if m["where"] == "body"
        ]
    if found:
        item.cls, item.reason = (
            "SKIP-SECURITY",
            "Security signals — may need confidential handling, review manually",
        )
        item.details["security_matches"] = found
        return item
    if signals.f5c(pr, cfg, people):
        item.cls = "SKIP-MAINTAINER-COURT"
        item.reason = "Author is waiting on a maintainer response — the next move is ours"
        return item
    nudge = standing_nudge(pr, raw)
    item.nudge_at = nudge
    if idle >= plan.hard_close_days:
        item.cls, item.reason = (
            "CLOSE-STALE",
            f"Inactive {idle} days, past the {plan.hard_close_days}-day hard close",
        )
        item.details["basis"] = "hard_close"
        return item
    if nudge is not None:
        since = _days(now - nudge)
        item.details["nudged_days_ago"] = since
        if idle >= plan.close_days and since >= NOTICE_FLOOR_DAYS:
            item.cls = "CLOSE-STALE"
            item.reason = f"Inactive {idle} days; nudged {since} days ago with no author response"
            item.details["basis"] = "nudged"
            return item
        wait = max(plan.close_days - idle, NOTICE_FLOOR_DAYS - since, 0)
        item.cls = "SKIP-NUDGE-PENDING"
        item.reason = f"Nudged {since} days ago; eligible to close in {max(wait, 1)} day(s) if still silent"
        item.remaining_days = max(wait, 1)
        return item
    item.cls = "REQUEST-UPDATE"
    item.remaining_days = max(plan.close_days - idle, NOTICE_FLOOR_DAYS)
    item.reason = f"Inactive {idle} days, no prior nudge"
    return item


def sweep(
    loaded: list[tuple[PR, list[RawComment]]],
    plan: Plan,
    cfg: Config,
    people: Maintainers,
    now: dt.datetime,
) -> dict[str, Any]:
    filtered = {"draft": 0, "bot": 0, "label": 0, "fresh": 0}
    items: list[Item] = []
    for pr, raw in loaded:
        if plan.explicit_numbers is not None and pr.number not in plan.explicit_numbers:
            continue
        if pr.is_draft:
            filtered["draft"] += 1
            continue
        if is_bot(pr.author):
            filtered["bot"] += 1
            continue
        if plan.label_filter and plan.label_filter not in pr.labels:
            filtered["label"] += 1
            continue
        item = classify_one(pr, raw, plan, cfg, people, now)
        if item is None:
            filtered["fresh"] += 1
            continue
        items.append(item)
    acting = [i for i in items if i.cls in ACTING]
    load = sorted({CLASS_DOCS[i.cls] for i in items}, key=list(CLASS_DOCS.values()).index)
    warnings = list(cfg.warnings)
    over_cap = len(acting) > CAP
    if over_cap:
        warnings.append(
            f"{len(acting)} candidates — more than {CAP}; narrow with `stale label:<label>` or `stale close:<N>` "
            "before going on (nothing is truncated)"
        )
    return {
        "thresholds": {
            "warn_days": plan.warn_days,
            "close_days": plan.close_days,
            "hard_close_days": plan.hard_close_days,
            "source": plan.source,
        },
        "dry_run": plan.dry_run,
        "pool": {
            "candidates": len(acting),
            "past_close": sum(1 for i in acting if (i.days_idle or 0) >= plan.close_days),
            "warn_to_close": sum(1 for i in acting if (i.days_idle or 0) < plan.close_days),
            "filtered": filtered,
        },
        "over_cap": over_cap,
        "proposals": [_entry(i) for i in acting],
        "skipped": [_entry(i) for i in items if i.cls not in ACTING],
        "needs": [
            {
                "op": "upstream-permission",
                "params": [login],
                "save": f"permission-{login}",
                "why": "maintainer status decided conservatively; resolve and classify again",
            }
            for login in sorted(people.unresolved, key=str.lower)
        ],
        "load": load,
        "warnings": warnings,
    }


def _entry(item: Item) -> dict[str, Any]:
    pr = item.pr
    out: dict[str, Any] = {
        "number": pr.number,
        "title": pr.title,
        "url": pr.url,
        "author": pr.author,
        "head_sha": pr.head_sha,
        "class": item.cls,
        "days_idle": item.days_idle,
        "reason": item.reason,
        "doc": CLASS_DOCS[item.cls],
    }
    if item.remaining_days is not None:
        out["remaining_days"] = item.remaining_days
    if item.nudge_at is not None:
        out["nudged_at"] = item.nudge_at.isoformat()
    if item.details:
        out["details"] = item.details
    return out
