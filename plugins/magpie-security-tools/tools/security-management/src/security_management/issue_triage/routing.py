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
"""Step 4 `@`-mention picking and the Step 2.6 precedent signal.

`mentions` applies the routing priorities of `proposal-composition.md` to the
candidates the searches found (which PR author, which reviewer, which CVE
owner is relevant stays the agent's read of the search results):

1. the most recent analogous-fix PR author on the roster;
2. the most recent area reviewer on the roster;
3. the topic-specific owner of a recently closed sibling CVE's fix, on top;
4. only when 1 and 2 found nobody: one scope-default handle, and the
   routing-failure note the user must confirm.

The triager (`viewer`) and anyone off the roster are never picked; the cap
is 3 handles, and an empty roster stops the run rather than guessing.

`signal` turns the precedents the agent rated (STRONG / MODERATE, the
judgement) into the Step 2.6 signal: a STRONG rejection and no STRONG
positive lowers toward INVALID, the reverse raises toward VALID, anything
else is neutral. A precedent never auto-classifies.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import refs
from security_management.shared.rollup import one_line

CAP = 3
BUDGET = 3


def _handle(value: object) -> str:
    return str(value or "").strip().lstrip("@")


def mentions(data: Mapping[str, Any]) -> dict[str, Any]:
    roster = {_handle(r).lower(): _handle(r) for r in data.get("roster") or [] if _handle(r)}
    if not roster:
        raise ValueError(
            "the security-team roster is empty: populate release-trains.md; do not guess handles"
        )
    viewer = _handle(data.get("viewer")).lower()
    picked: list[str] = []
    dropped: list[dict[str, str]] = []

    def take(candidates: Sequence[object], limit: int, source: str) -> int:
        took = 0
        for raw in candidates:
            handle = _handle(raw)
            key = handle.lower()
            if not handle or took >= limit:
                continue
            if key == viewer:
                dropped.append({"handle": handle, "why": "the triager"})
            elif key not in roster:
                dropped.append({"handle": handle, "why": "not on the security-team roster"})
            elif roster[key] in picked:
                continue
            elif len(picked) >= CAP:
                dropped.append({"handle": handle, "why": f"over the cap of {CAP} ({source})"})
            else:
                picked.append(roster[key])
                took += 1
        return took

    history = take(data.get("pr_authors") or [], 1, "PR author")
    history += take(data.get("reviewers") or [], 1, "reviewer")
    take(data.get("topic_owners") or [], CAP, "topic owner")
    fallback = history == 0
    if fallback and len(picked) < CAP:
        take(data.get("scope_default") or [], 1, "scope default")
    pointer = one_line(data.get("pointer") or "this code area")
    return {
        "handles": [f"@{h}" for h in picked],
        "dropped": dropped,
        "routing_fallback": fallback,
        "fallback_note": (
            f"no PR-history match for `{pointer}`; falling back to scope-default — "
            "please confirm @-mentions before posting"
        )
        if fallback
        else None,
        "empty": not picked,
    }


def _strong(items: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [p for p in items if str(p.get("match_strength") or "").upper() == "STRONG"]


def signal(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    rejections: Sequence[Mapping[str, Any]] = data.get("rejection_precedents") or []
    positives: Sequence[Mapping[str, Any]] = data.get("positive_precedents") or []
    for item in (*rejections, *positives):
        if str(item.get("match_strength") or "").upper() not in ("STRONG", "MODERATE"):
            raise ValueError(f"precedent {item.get('number')}: match_strength must be STRONG or MODERATE")
    strong_no, strong_yes = _strong(rejections), _strong(positives)
    if strong_no and not strong_yes:
        verdict = "lowers_to_invalid"
    elif strong_yes and not strong_no:
        verdict = "raises_to_valid"
    else:
        verdict = "neutral"
    used = int(data.get("calls_used") or 0)
    citations = [
        f"Direct precedent: {refs.tracker_link(tracker, p['number'])} "
        f"(closed {one_line(p.get('closed_at'))[:10]} as {one_line(p.get('closed_as') or 'INVALID')}, "
        f"same shape: {one_line(p.get('one_line_shape'))})."
        for p in strong_no
    ]
    return {
        "disposition_signal": verdict,
        "budget_exhausted": used >= BUDGET,
        "over_budget": used > BUDGET,
        "trust_boundary_load_bearing": bool(strong_no and strong_yes),
        "citations": citations,
    }
