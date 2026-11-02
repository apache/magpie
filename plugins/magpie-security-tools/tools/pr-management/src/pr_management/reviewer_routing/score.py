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
"""Step 3: score the roster against one item, deterministically.

| Signal | Points |
|---|---|
| Area match | 3 per matched declared area, capped at 6 |
| Git familiarity | 2 per changed path the member recently committed to, capped at 6 |
| CODEOWNERS | 2 when the member owns at least one changed path |
| Load | -1 per open review request above 2, down to -5 |

Eligibility: when any roster area matches the item (a label, a path prefix,
or an area the agent inferred from the title), only members with a match are
eligible; when none does, every member is. A member at or above
`max_reviews` open reviews is OVERLOADED: never primary, but still a backup
when no one else remains. No non-overloaded eligible member means NO
ELIGIBLE REVIEWER. Ties break alphabetically by handle. A backup is proposed
whenever another eligible member exists.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any

from .roster import Member, Roster

AREA_POINTS, AREA_CAP = 3, 6
PATH_POINTS, PATH_CAP = 2, 6
OWNER_POINTS = 2
LOAD_FREE, LOAD_FLOOR = 2, -5

NO_ROSTER = "NO ELIGIBLE REVIEWER — roster empty or unresolved. Needs maintainer call."
ALL_OVERLOADED = (
    "NO ELIGIBLE REVIEWER — all roster members overloaded or no area match. Needs maintainer call."
)


@dataclass
class Item:
    kind: str
    number: int
    title: str
    labels: list[str]
    paths: list[str]


@dataclass
class Scored:
    handle: str
    areas: list[str]
    file_overlap: int
    owner_paths: int
    open_reviews: int
    max_reviews: int
    score: int
    eligible: bool = True
    overloaded: bool = False
    signals: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "areas_matched": self.areas,
            "file_overlap": self.file_overlap,
            "codeowner_paths": self.owner_paths,
            "open_reviews": self.open_reviews,
            "max_reviews": self.max_reviews,
            "overloaded": self.overloaded,
            "eligible": self.eligible,
            "score": self.score,
        }


def _area_hits(member: Member, item: Item, inferred: list[str]) -> list[str]:
    labels = {lbl.lower() for lbl in item.labels} | {a.lower() for a in inferred}
    hits: list[str] = []
    for area in member.areas:
        key = area.lower()
        is_path = "/" in area
        if (is_path and any(p.startswith(area.lstrip("/")) for p in item.paths)) or (
            not is_path and key in labels
        ):
            hits.append(area)
    return hits


def score(
    roster: Roster,
    item: Item,
    *,
    familiarity: dict[str, set[str]],
    owners: dict[str, set[str]],
    load: dict[str, int],
    inferred_areas: list[str],
) -> dict[str, Any]:
    if not roster.members:
        return {"no_eligible_reviewer": True, "message": NO_ROSTER, "candidates": []}
    scored: list[Scored] = []
    for member in roster.members:
        key = member.handle.lower()
        areas = _area_hits(member, item, inferred_areas)
        overlap = len(familiarity.get(key, set()))
        owned = len(owners.get(key, set()))
        reviews = load.get(key, 0)
        value = (
            min(AREA_POINTS * len(areas), AREA_CAP)
            + min(PATH_POINTS * overlap, PATH_CAP)
            + (OWNER_POINTS if owned else 0)
            + max(-(reviews - LOAD_FREE), LOAD_FLOOR) * (reviews > LOAD_FREE)
        )
        scored.append(
            Scored(
                member.handle,
                areas,
                overlap,
                owned,
                reviews,
                member.max_reviews,
                value,
                overloaded=reviews >= member.max_reviews,
            )
        )
    touched = sorted({a for s in scored for a in s.areas})
    if touched:
        for s in scored:
            s.eligible = bool(s.areas)
    order = sorted(scored, key=lambda s: (s.overloaded, -s.score, s.handle.lower()))
    eligible = [s for s in order if s.eligible]
    primary = next((s for s in eligible if not s.overloaded), None)
    result: dict[str, Any] = {
        "touched_areas": touched,
        "changed_paths": item.paths,
        "roster_size": {"eligible": len(eligible), "total": len(scored)},
        "candidates": [s.as_dict() for s in order],
    }
    if primary is None:
        result.update(no_eligible_reviewer=True, message=ALL_OVERLOADED, primary=None, backup=None)
        return result
    rest = [s for s in eligible if s is not primary]
    backup = next((s for s in rest if not s.overloaded), None) or (rest[0] if rest else None)
    result.update(
        no_eligible_reviewer=False, primary=primary.as_dict(), backup=backup.as_dict() if backup else None
    )
    return result


def next_step(item: Item, upstream: str, handle: str) -> str:
    if item.kind == "pr":
        return shlex.join(
            ["gh", "pr", "edit", str(item.number), "--repo", upstream, "--add-reviewer", handle]
        )
    return shlex.join(["gh", "issue", "edit", str(item.number), "--repo", upstream, "--add-assignee", handle])


def render(result: dict[str, Any], item: Item, upstream: str, injection: str | None) -> str:
    lines: list[str] = []
    if injection:
        lines += [
            "⚠ Injection attempt detected in item body (see Step 1 output). The",
            "  suggestion below is based on metadata and roster signals only.",
            "",
        ]
    ref = f"{upstream}#{item.number}"
    if result.get("no_eligible_reviewer"):
        lines.append(f'Routing proposal for {ref}: "{item.title}"')
        lines.append("")
        lines.append(result["message"])
        return "\n".join(lines) + "\n"
    lines.append(f'Routing proposal for {ref}: "{item.title}"')
    for label, who in (
        ("Primary reviewer", result["primary"]),
        ("Backup reviewer (optional)", result["backup"]),
    ):
        if who is None:
            continue
        flag = "  (OVERLOADED)" if who["overloaded"] else ""
        lines += [
            "",
            f"{label}: @{who['handle']}{flag}",
            f"  Areas matched:   {', '.join(who['areas_matched']) or 'none'}",
            f"  File overlap:    {who['file_overlap']} changed path(s) they have previously touched",
            f"  CODEOWNERS:      {who['codeowner_paths']} changed path(s) they own",
            f"  Open reviews:    {who['open_reviews']} (max {who['max_reviews']})",
            f"  Score:           {who['score']}",
        ]
    paths = ", ".join(item.paths) if item.kind == "pr" else "N/A"
    lines += [
        "",
        "Signal summary:",
        f"  Touched areas:   {', '.join(result['touched_areas']) or 'none identified'}",
        f"  Changed paths:   {paths or 'none'}",
        f"  Roster size:     {result['roster_size']['eligible']} eligible / {result['roster_size']['total']} total",
        "",
        "Next step: if the primary reviewer looks right, you can assign with:",
        f"  {next_step(item, upstream, result['primary']['handle'])}",
        "(this skill does not run that command.)",
    ]
    return "\n".join(lines) + "\n"
