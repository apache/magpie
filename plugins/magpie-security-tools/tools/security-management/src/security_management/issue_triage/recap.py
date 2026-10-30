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
"""Step 7 recap: distribution, one linked line per posted proposal, skipped group, next commands.

Next steps by class: VALID → `security-cve-allocate N`; INVALID and INFO-ONLY
→ `security-issue-invalidate N`; PROBABLE-DUP → `security-issue-deduplicate
N KEPT`; FIX-ALREADY-PUBLIC → `security-issue-invalidate N` only after the
reporter confirms the PR fixes their report (else `--retriage`);
DEFENSE-IN-DEPTH has none. The recap always says label flips and board moves
are `security-issue-sync`'s, never this skill's.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.shared import dispositions, refs
from security_management.shared.rollup import one_line

NEXT = {
    "VALID": "/security-cve-allocate {n}",
    "INVALID": "/security-issue-invalidate {n}",
    "INFO-ONLY": "/security-issue-invalidate {n}",
    "PROBABLE-DUP": "/security-issue-deduplicate {n} {kept}",
    "FIX-ALREADY-PUBLIC": "/security-issue-invalidate {n}",
}
FIX_PUBLIC_NOTE = (
    "only after the reporter confirms the public PR fixes their report; "
    "if they say it does not, re-triage with --retriage"
)
SYNC_NOTE = (
    "Label flips and project-board moves stay with `security-issue-sync` once the team's decision lands, "
    "not with this skill."
)


def render(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    distribution = {c.replace("-", "_"): 0 for c in dispositions.CLASSES}
    trackers = []
    next_steps = []
    notes = []
    lines = []
    for posted in data.get("posted") or []:
        number = int(posted["number"])
        klass = dispositions.normalise_class(posted.get("class"))
        if klass is None:
            raise ValueError(f"tracker {number}: class {posted.get('class')!r} is not one of the six")
        url = str(posted.get("comment_url") or "")
        distribution[klass.replace("-", "_")] += 1
        trackers.append({"number": number, "class": klass, "comment_url": url})
        lines.append(f"- {refs.tracker_link(tracker, number)} — {klass} — [comment]({url})")
        if klass in NEXT:
            kept = posted.get("kept")
            if klass == "PROBABLE-DUP" and not kept:
                raise ValueError(f"tracker {number}: PROBABLE-DUP needs the kept tracker")
            step = NEXT[klass].format(n=number, kept=kept)
            next_steps.append(step)
            if klass == "FIX-ALREADY-PUBLIC":
                notes.append({"step": step, "note": FIX_PUBLIC_NOTE})
    skipped = [
        {
            "number": int(s["number"]),
            "proposal_date": one_line(s.get("proposal_date")),
            "proposed_class": s.get("proposed_class"),
            "rule": one_line(s.get("rule") or "last comment is our unanswered triage proposal"),
        }
        for s in data.get("skipped") or []
    ]
    counts = ", ".join(f"{distribution[c.replace('-', '_')]} {c}" for c in dispositions.CLASSES)
    text = [f"**Triage recap:** {counts}.", ""]
    text += lines or ["- nothing posted"]
    if skipped:
        text += ["", "**Pre-flight skipped (awaiting reaction):**", ""]
        text += [
            f"- {refs.tracker_link(tracker, s['number'])} — proposal of {s['proposal_date'][:10]}"
            f" ({s['proposed_class'] or 'class unread'}) — {s['rule']}"
            for s in skipped
        ]
    failed = data.get("failed")
    if failed:
        text += [
            "",
            f"**Stopped at** {refs.tracker_link(tracker, failed['number'])}: {one_line(failed.get('error'))}.",
        ]
        remaining = [int(n) for n in data.get("remaining") or []]
        if remaining:
            text.append(f"Re-run the rest with `{', '.join(str(n) for n in remaining)}`.")
    if next_steps:
        text += ["", "**Next steps:**", ""]
        for step in next_steps:
            note = next((n["note"] for n in notes if n["step"] == step), None)
            text.append(f"- `{step}`" + (f" — {note}" if note else ""))
    text += ["", SYNC_NOTE]
    return {
        "distribution": distribution,
        "trackers": trackers,
        "next_steps": next_steps,
        "next_step_notes": notes,
        "skipped": skipped,
        "sync_note": True,
        "text": "\n".join(text) + "\n",
        "bare_refs": refs.bare_refs("\n".join(text)),
    }
