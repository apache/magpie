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
"""Step 4.5 — up to three grounded reviewers to suggest, never fabricated.

Sources, cheapest first: `CODEOWNERS` owners of the touched paths, recent
commit authors on them, then reviewers of prior merged PRs on them. Every
candidate carries the evidence that produced it; PR text is never a source.
Excluded: the PR author, the viewer, anyone already requested or already
reviewing. At least one suggestion must be a committer when any candidate is;
otherwise the strongest contributor stays with an explicit "not a committer".
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..model import parse_time
from . import codeowners

STALE = dt.timedelta(days=365)


@dataclass
class Candidate:
    login: str
    owner_of: list[str] = field(default_factory=list)
    commits: int = 0
    last_commit: dt.datetime | None = None
    reviewed: int = 0
    committer: bool = False

    def score(self) -> tuple[int, int, int, float]:
        recency = self.last_commit.timestamp() if self.last_commit else 0.0
        return (1 if self.owner_of else 0, self.commits, self.reviewed, recency)

    def reason(self) -> str:
        parts = []
        if self.owner_of:
            parts.append(f"`CODEOWNERS` owner for `{self.owner_of[0]}`")
        if self.commits:
            parts.append(f"{self.commits} recent commit(s) on the changed paths")
        if self.reviewed:
            parts.append(f"reviewed {self.reviewed} prior merged PR(s) on these paths")
        parts.append("committer" if self.committer else "frequent contributor, not a committer")
        return " — ".join(parts[:1]) + (f" ({', '.join(parts[1:])})" if len(parts) > 1 else "")


def suggest(
    *,
    paths: list[str],
    rules: list[codeowners.Rule],
    path_commits: dict[str, list[dict[str, Any]]],
    prior_reviewers: list[str],
    exclude: set[str],
    committers: set[str],
    now: dt.datetime,
) -> dict[str, Any]:
    pool: dict[str, Candidate] = {}

    def get(login: str) -> Candidate:
        key = login.lstrip("@")
        return pool.setdefault(key.lower(), Candidate(key))

    for path in paths:
        for owner in codeowners.owners_of(rules, path):
            name = owner.lstrip("@")
            get(name).owner_of.append(path)
    for entries in path_commits.values():
        for entry in entries:
            login = entry.get("login")
            if not login:
                continue
            candidate = get(str(login))
            candidate.commits += 1
            when = parse_time(entry.get("date"))
            if when and (candidate.last_commit is None or when > candidate.last_commit):
                candidate.last_commit = when
    for login, count in Counter(r.lower() for r in prior_reviewers).items():
        get(login).reviewed += count
    lowered_committers = {c.lower() for c in committers}
    for key, candidate in pool.items():
        candidate.committer = bool(candidate.owner_of) or key in lowered_committers
    excluded = {e.lower().lstrip("@") for e in exclude}
    ranked = [c for k, c in pool.items() if k not in excluded and "/" not in k]
    teams = [c for k, c in pool.items() if k not in excluded and "/" in k]
    fresh = [c for c in ranked if c.owner_of or c.reviewed or (c.last_commit and now - c.last_commit < STALE)]
    ranked = fresh if fresh else ranked
    ranked.sort(key=lambda c: c.score(), reverse=True)
    picked = ranked[:3]
    if picked and not any(c.committer for c in picked):
        committer = next((c for c in ranked[3:] if c.committer), None)
        if committer is not None:
            picked[-1] = committer
    picked += [t for t in teams if not picked][:1]
    return {
        "section_present": bool(picked),
        "includes_committer": any(c.committer for c in picked),
        "suggestions": [{"login": c.login, "reason": c.reason(), "committer": c.committer} for c in picked],
    }
