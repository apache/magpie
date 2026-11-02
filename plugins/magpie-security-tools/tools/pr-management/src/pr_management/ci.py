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
"""CI state: failed checks, the real-CI guard, grace windows, systemic failures."""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .config import Config
from .model import COLLABORATOR_ASSOCIATIONS, PR, Context

FAILED_CONCLUSIONS = frozenset({"FAILURE", "TIMED_OUT"})
FAILED_STATES = frozenset({"FAILURE", "ERROR"})
PENDING_STATUSES = frozenset({"QUEUED", "IN_PROGRESS", "PENDING", "WAITING", "REQUESTED"})

#: Checks that succeed without any real CI having run.
BOT_CHECKS = ("mergeable", "wip", "dco", "boring-cyborg", "probot", "labeler", "label", "triage", "welcome")

GRACE_UNENGAGED = dt.timedelta(hours=24)
GRACE_ENGAGED = dt.timedelta(hours=96)


def context_failed(ctx: Context) -> bool:
    if ctx.kind == "StatusContext":
        return (ctx.conclusion or "") in FAILED_STATES
    return (ctx.conclusion or "") in FAILED_CONCLUSIONS


def context_pending(ctx: Context) -> bool:
    if ctx.kind == "StatusContext":
        return ctx.conclusion in (None, "PENDING", "EXPECTED")
    return ctx.conclusion is None or (ctx.status or "") in PENDING_STATUSES


def failed_checks(pr: PR) -> list[str]:
    """Failing checks attributable to the PR: the REST re-derivation when supplied."""
    if pr.rest_failed_checks is not None:
        return list(pr.rest_failed_checks)
    return [c.name for c in pr.contexts if context_failed(c)]


def needs_rest_checks(pr: PR) -> bool:
    """The rollup page is a prefix; a failing PR whose page is truncated needs the REST list."""
    return pr.rollup_state in ("FAILURE", "ERROR") and pr.contexts_truncated and pr.rest_failed_checks is None


def pending_checks(pr: PR) -> list[str]:
    return [c.name for c in pr.contexts if context_pending(c)]


def is_static(name: str, cfg: Config) -> bool:
    lowered = name.lower()
    return any(p in lowered or lowered in p for p in (q.lower() for q in cfg.static_check_patterns))


def _is_bot_check(name: str) -> bool:
    lowered = name.lower()
    return any(lowered == b.lower() or lowered.startswith(b.lower() + " ") for b in BOT_CHECKS)


def real_ci_ran(pr: PR, cfg: Config) -> bool:
    """At least one context is real CI, not a bot or labeler check."""
    names = [c.name for c in pr.contexts]
    if cfg.real_ci_patterns:
        return any(re.match(p, n, flags=re.IGNORECASE) for p in cfg.real_ci_patterns for n in names)
    return any(not _is_bot_check(n) for n in names)


def collaborator_engaged(pr: PR) -> bool:
    if any(r.association in COLLABORATOR_ASSOCIATIONS and r.author != pr.author for r in pr.reviews):
        return True
    return any(
        c.association in COLLABORATOR_ASSOCIATIONS and c.author != pr.author for c in pr.all_comments()
    )


def grace(pr: PR, now: dt.datetime) -> dict[str, Any]:
    """Whether the CI-failure signal is still inside its grace window."""
    window = GRACE_ENGAGED if collaborator_engaged(pr) else GRACE_UNENGAGED
    failing = [c for c in pr.contexts if context_failed(c)]
    anchors = [t for t in (c.started or c.completed for c in failing) if t is not None]
    anchor = max(anchors) if anchors else pr.updated
    if anchor is None:
        return {"in_grace": False, "window_hours": int(window.total_seconds() // 3600)}
    elapsed = now - anchor
    return {
        "in_grace": elapsed < window,
        "window_hours": int(window.total_seconds() // 3600),
        "failed_hours_ago": int(elapsed.total_seconds() // 3600),
        "remaining_hours": max(0, int((window - elapsed).total_seconds() // 3600)),
    }


def load_rest_failures(path: Path) -> list[str]:
    """`check-runs` output (slurped pages) → names of failed or timed-out runs."""
    document = json.loads(path.read_text(encoding="utf-8"))
    pages = document if isinstance(document, list) else [document]
    names: list[str] = []
    for page in pages:
        for run in (page or {}).get("check_runs") or []:
            if str(run.get("conclusion") or "").upper() in FAILED_CONCLUSIONS:
                names.append(str(run.get("name") or ""))
    return names


def load_systemic(path: Path | None) -> set[str]:
    """`gql-main-recent-failures` → check names failing on at least two recently merged PRs."""
    if path is None:
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    pulls = (((data.get("data") or {}).get("repository") or {}).get("pullRequests") or {}).get("nodes") or []
    counts: Counter[str] = Counter()
    for pull in pulls:
        failing: set[str] = set()
        for commit in ((pull or {}).get("commits") or {}).get("nodes") or []:
            rollup = ((commit or {}).get("commit") or {}).get("statusCheckRollup") or {}
            for ctx in (rollup.get("contexts") or {}).get("nodes") or []:
                if ctx.get("__typename") == "StatusContext":
                    if ctx.get("state") in FAILED_STATES:
                        failing.add(str(ctx.get("context")))
                elif ctx.get("conclusion") in FAILED_CONCLUSIONS:
                    failing.add(str(ctx.get("name")))
        counts.update(failing)
    return {name for name, count in counts.items() if count >= 2}


def load_action_required(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    """`runs-action-required` (slurped pages) → head SHA → runs awaiting approval."""
    index: dict[str, list[dict[str, Any]]] = {}
    if path is None:
        return index
    document = json.loads(path.read_text(encoding="utf-8"))
    pages: Iterable[Any] = document if isinstance(document, list) else [document]
    for page in pages:
        for run in (page or {}).get("workflow_runs") or []:
            if (
                run.get("conclusion") not in (None, "action_required")
                and run.get("status") != "action_required"
            ):
                continue
            sha = str(run.get("head_sha") or "")
            if sha:
                index.setdefault(sha, []).append({"id": run.get("id"), "name": run.get("name")})
    return index
