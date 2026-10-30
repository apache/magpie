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
"""Bulk mode, orchestrator steps 3 and 4: the CVE-impact buckets and the merged confirmation.

`bucket` sorts the subagent reports: a tracker is *CVE-affecting* when a
proposed body-field update names a field that lands in the CVE record
(Title, Short public summary for publish, CWE, Severity, Affected
versions, Reporter credited as, Remediation developer, PR with the fix,
Public advisory URL); its trackers are walked in ascending order. The
mechanical `allocated → review-ready` push of a `pr merged → fix released`
flip rides the non-CVE-affecting confirmation (the atomicity rule), even on
a tracker that is also CVE-affecting for a content change.

`parse_reply` reads the merged confirmation: `all`, `<N>:all`,
`<N>:1,3,5`, `<N>:skip`, `<N>:edit <item>: <value>`, `force-sync <N>` (a
pre-flight-skipped tracker only), `cancel` / `none`. Clauses split on `;`
and new lines. A tracker or item the proposal does not carry, two
dispositions for one tracker, or free text makes the reply `ambiguous`:
nothing applies.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

CVE_FIELDS = (
    "Title",
    "Short public summary for publish",
    "CWE",
    "Severity",
    "Affected versions",
    "Reporter credited as",
    "Remediation developer",
    "PR with the fix",
    "Public advisory URL",
)
_FIELD = re.compile(
    r"^[\s\"'`*_-]*(?:" + "|".join(re.escape(f) for f in CVE_FIELDS) + r")(?![\w])", re.IGNORECASE
)


def cve_affecting(update: object) -> bool:
    return bool(_FIELD.match(str(update)))


def bucket(data: Mapping[str, Any]) -> dict[str, Any]:
    cve: list[int] = []
    plain: list[int] = []
    pushes: list[int] = []
    for report in data.get("reports") or []:
        number = int(report["issue"])
        updates = report.get("proposed_body_field_updates") or []
        (cve if any(cve_affecting(u) for u in updates) else plain).append(number)
        adds = {str(x) for x in report.get("proposed_label_add") or []}
        if "fix released" in adds and report.get("cve_id"):
            pushes.append(number)
    return {
        "ok": True,
        "cve_affecting": sorted(cve),
        "non_cve_affecting": sorted(plain),
        "walk_order": sorted(cve),
        "review_ready_push": sorted(pushes),
        "review_ready_push_bucket": "non_cve_affecting" if pushes else None,
    }


_ALL = re.compile(r"^(?:all|go|yes|proceed)$", re.IGNORECASE)
_CANCEL = re.compile(r"^(?:cancel|none|abort)$", re.IGNORECASE)
_TRACKER = re.compile(r"^#?(?P<n>\d+)\s*:\s*(?P<rest>.+)$", re.DOTALL)
_FORCE = re.compile(r"^force-sync\s+(?P<list>#?\d+(?:(?:\s*,\s*|\s+)#?\d+)*)$", re.IGNORECASE)
_ITEMS = re.compile(r"^\d+(?:(?:\s*,\s*|\s+)\d+)*$")
_EDIT = re.compile(r"^edit\s+(?P<item>\d+)\s*:\s*(?P<value>.+)$", re.IGNORECASE | re.DOTALL)


def parse_reply(data: Mapping[str, Any]) -> dict[str, Any]:
    proposal = {int(k): sorted({int(i) for i in v}) for k, v in (data.get("proposal") or {}).items()}
    skipped = {int(n) for n in data.get("preflight_skipped") or []}
    reply = str(data.get("reply") or "").strip()
    plan: dict[int, list[int]] = {}
    edits: list[dict[str, Any]] = []
    force: list[int] = []
    skip: list[int] = []
    ambiguous: list[str] = []
    everything = False

    def take(number: int, items: list[int], token: str) -> None:
        if number in plan or number in skip:
            ambiguous.append(token)
        else:
            plan[number] = items

    for clause in [c.strip() for c in re.split(r"[;\n]", reply) if c.strip()]:
        if _CANCEL.match(clause):
            return {
                "ok": True,
                "action": "cancel",
                "apply": {},
                "edits": [],
                "force_sync": [],
                "skip": [],
                "ambiguous": [],
            }
        if _ALL.match(clause):
            everything = True
            continue
        forced = _FORCE.match(clause)
        if forced:
            numbers = [int(n) for n in re.findall(r"\d+", forced.group("list"))]
            if any(n not in skipped for n in numbers):
                ambiguous.append(clause)
            force.extend(n for n in numbers if n in skipped and n not in force)
            continue
        scoped = _TRACKER.match(clause)
        if not scoped or int(scoped.group("n")) not in proposal:
            ambiguous.append(clause)
            continue
        number, rest = int(scoped.group("n")), scoped.group("rest").strip()
        edit = _EDIT.match(rest)
        if rest.lower() == "all":
            take(number, proposal[number], clause)
        elif rest.lower() == "skip":
            if number in plan:
                ambiguous.append(clause)
            else:
                skip.append(number)
        elif _ITEMS.match(rest):
            items = sorted({int(i) for i in re.findall(r"\d+", rest)})
            if any(i not in proposal[number] for i in items):
                ambiguous.append(clause)
            else:
                take(number, items, clause)
        elif edit and int(edit.group("item")) in proposal[number]:
            edits.append(
                {"tracker": number, "item": int(edit.group("item")), "value": edit.group("value").strip()}
            )
        else:
            ambiguous.append(clause)
    if ambiguous:
        return {
            "ok": True,
            "action": "ambiguous",
            "apply": {},
            "edits": [],
            "force_sync": [],
            "skip": [],
            "ambiguous": ambiguous,
        }
    if everything:
        for number, items in proposal.items():
            if number not in skip:
                plan.setdefault(number, items)
    for change in edits:
        plan.setdefault(int(change["tracker"]), proposal[int(change["tracker"])])
    action = "apply" if plan else ("force_sync" if force else "none")
    return {
        "ok": True,
        "action": action,
        "apply": {str(n): plan[n] for n in sorted(plan)},
        "edits": edits,
        "force_sync": sorted(force),
        "skip": sorted(skip),
        "ambiguous": [],
    }
