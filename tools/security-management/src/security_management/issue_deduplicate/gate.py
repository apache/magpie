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
"""Inputs, Step 1 and Step 2: which tracker is kept, whether the merge may run, both trackers' fields.

- `selector`: `dedupe #<keep> <drop>` (any reference form); one tracker is
  ambiguous, since which side is kept is the user's call.
- `classify`: the Step 1 checks — both open, the same single scope label,
  neither `duplicate` — and the CVE rules of *Inputs*: a CVE only on the
  dropped side means swap the sides, a `public` record on either side
  refuses the merge (that is an errata, not a dedupe), and with two CVEs the
  kept one must be at least as far along, and the dropped one is retracted.
- `fields`: the template fields of both bodies through github-body-field
  (`shared.fields`, fail closed), whether each carries a CVE JSON
  attachment, and the two conflicts: different CWEs (a blocker for the
  triager) and a dropped-side severity that differs (never propagated).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.shared import fields as body_fields
from security_management.shared import refs, selectors
from security_management.shared.rollup import one_line
from security_management.shell import w

DUPLICATE = "duplicate"
CVE_STATES = ("allocated", "review-ready", "publish-ready", "public")
ROLES = (
    "issue_description",
    "public_summary",
    "affected_versions",
    "mailing_thread",
    "public_advisory_url",
    "reporter_credit",
    "pr_with_fix",
    "remediation_developer",
    "cwe",
    "severity",
    "cve_link",
)
VIEW = "number,title,state,body,labels,milestone,assignees,author,comments,createdAt"
ATTACHMENT_MARKER = "<!-- generate-cve-json:"
_SKILL = re.compile(
    r"^/?(?:magpie-security:)?(?:security-)?(?:issue-)?(?:dedupe|deduplicate)$", re.IGNORECASE
)
_CVE = re.compile(r"CVE-\d{4}-\d+")
_BACKEND_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_RANGE = re.compile(r"^#?\d+-#?\d+$")


def _names(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        value = value.get("nodes") or []
    return [str(v.get("name") if isinstance(v, Mapping) else v) for v in value or []]


def selector(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    words = str(data.get("invocation") or "").replace(",", " ").split()
    if words and _SKILL.match(words[0]):
        words = words[1:]
    words = [word for word in words if word.lower() not in ("into", "keep", "drop", "->", "→")]
    if platform == "github":
        try:
            issues: list[Any] = selectors.issue_numbers(" ".join(words), tracker) if words else []
        except ValueError as exc:
            return {"ok": False, "refused": str(exc)}
        if any(_RANGE.match(word) for word in words):
            return {"ok": False, "refused": "name two trackers, the kept one first, not a range"}
    else:
        if not all(_BACKEND_ID.match(word) for word in words):
            return {"ok": False, "refused": f"{' '.join(words)!r} is not two {platform} tracker IDs"}
        issues = list(dict.fromkeys(words))
    if len(issues) < 2:
        return {
            "ok": False,
            "refused": "name both trackers, the kept one first: which side is kept is the user's call",
        }
    if len(issues) > 2:
        return {"ok": False, "refused": "a merge takes exactly two trackers, the kept one first"}
    keep, drop = issues
    if platform == "github":
        commands = [f"gh issue view {n} --repo {w(tracker)} --json {VIEW}" for n in (keep, drop)]
    else:
        read = (
            "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-deduplicate"
        )
        commands = [f"{read} issue-view {w(n)}" for n in (keep, drop)] + [
            f"{read} issue-comments {w(n)}" for n in (keep, drop)
        ]
    return {"ok": True, "keep": keep, "drop": drop, "commands": commands}


def _scopes(labels: list[str], scopes: list[str]) -> list[str]:
    return [s for s in scopes if s in labels]


def _cve_of(value: object) -> str | None:
    found = _CVE.findall(str(value or ""))
    return found[0] if found else None


def classify(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    scopes = [str(s) for s in data.get("scope_labels") or []]
    if not scopes:
        return {"ok": False, "refused": "scope_labels is empty: read scope_detection.labels from project.md"}
    keep, drop = data["keep"], data["drop"]
    duplicate = str(data.get("duplicate_label") or DUPLICATE)

    def link(side: Mapping[str, Any]) -> str:
        return refs.tracker_link(tracker, side["number"], side.get("url"), platform)

    found: list[dict[str, str]] = []
    keep_scopes = _scopes(_names(keep.get("labels")), scopes)
    drop_scopes = _scopes(_names(drop.get("labels")), scopes)
    for name, side, sides in (("Kept", keep, keep_scopes), ("Drop", drop, drop_scopes)):
        if len(sides) != 1:
            what = "no scope label" if not sides else f"more than one scope label ({', '.join(sides)})"
            found.append(
                {
                    "kind": "scope_unclear",
                    "detail": f"{name} tracker {link(side)} has {what}; set exactly one before merging.",
                }
            )
    if len(keep_scopes) == 1 and len(drop_scopes) == 1 and keep_scopes != drop_scopes:
        found.append(
            {
                "kind": "scope_mismatch",
                "detail": f"Kept tracker {link(keep)} has scope label '{keep_scopes[0]}'; drop tracker {link(drop)} "
                f"has scope label '{drop_scopes[0]}'. Different scopes must not be merged — use "
                "security-issue-sync scope-split flow instead.",
            }
        )
    for name, side in (("Kept", keep), ("Drop", drop)):
        if str(side.get("state") or "").upper() != "OPEN":
            found.append(
                {
                    "kind": "closed_tracker",
                    "detail": f"{name} tracker {link(side)} is already closed. Merging into or out of a closed "
                    "tracker is almost always a mistake — confirm with the user before proceeding.",
                }
            )
    for name, side in (("Kept", keep), ("Drop", drop)):
        if duplicate in _names(side.get("labels")):
            found.append(
                {
                    "kind": "already_duplicate",
                    "detail": f"{name} tracker {link(side)} is already labelled '{duplicate}', indicating a partial "
                    "merge may have already occurred. Surface to the user to decide how to recover.",
                }
            )
    keep_cve, drop_cve = _cve_of(keep.get("cve_link")), _cve_of(drop.get("cve_link"))
    states = {
        "keep": one_line(keep.get("cve_state")) or None,
        "drop": one_line(drop.get("cve_state")) or None,
    }
    probe: list[str] = []
    retract = None
    if drop_cve and not keep_cve:
        found.append(
            {
                "kind": "cve_on_drop",
                "detail": f"Only the drop tracker {link(drop)} carries a CVE ({drop_cve}): keep that tracker instead, "
                "so the allocation is preserved.",
            }
        )
    for side, cve_id in (("keep", keep_cve), ("drop", drop_cve)):
        if cve_id and states[side] is None:
            probe.append(cve_id)
        elif cve_id and states[side] not in CVE_STATES:
            return {"ok": False, "refused": f"{states[side]!r} is not a CVE state ({', '.join(CVE_STATES)})"}
    if any(states[s] == "public" for s in ("keep", "drop") if (keep_cve if s == "keep" else drop_cve)):
        found.append(
            {
                "kind": "cve_public",
                "detail": "A CVE record here is already public: folding a shipped advisory into another tracker is "
                "an errata announcement (Step 16), not a dedupe.",
            }
        )
    elif keep_cve and drop_cve and not probe:
        assert states["keep"] is not None and states["drop"] is not None
        if CVE_STATES.index(states["drop"]) > CVE_STATES.index(states["keep"]):
            found.append(
                {
                    "kind": "drop_further_along",
                    "detail": f"The drop tracker's {drop_cve} ({states['drop']}) is further along than the kept "
                    f"tracker's {keep_cve} ({states['keep']}): keep the drop tracker instead.",
                }
            )
        else:
            retract = drop_cve
    if probe and not found:
        return {
            "ok": True,
            "verdict": "probe",
            "probe": probe,
            "message": "run the CVE tool's fetch_current_state for each CVE and pass the state as cve_state",
            "blockers": [],
            "blocker": None,
            "blocker_detail": None,
        }
    return {
        "ok": True,
        "verdict": "blocked" if found else "proceed",
        "blockers": found,
        "blocker": found[0]["kind"] if found else None,
        "blocker_detail": found[0]["detail"] if found else None,
        "scope_label": keep_scopes[0] if not found and keep_scopes else None,
        "keep_cve": keep_cve,
        "retract": retract,
    }


def _comment_bodies(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        value = value.get("nodes") or []
    return [str(c.get("body") if isinstance(c, Mapping) else c) for c in value or []]


def without_attachment(value: str | None) -> str | None:
    """`value` cut at the CVE JSON attachment, which `--attach` appends after the last field."""
    if not value:
        return value
    lines = value.split("\n")
    for index, line in enumerate(lines):
        if line.startswith(ATTACHMENT_MARKER):
            return "\n".join(lines[:index]).strip() or None
    return value


def has_attachment(body: str) -> bool:
    return any(line.rstrip().startswith(ATTACHMENT_MARKER) for line in body.split("\n"))


def fields(data: Mapping[str, Any]) -> dict[str, Any]:
    config = data.get("body_fields")
    out: dict[str, Any] = {}
    for key in ("keep", "drop"):
        side = data[key]
        read = body_fields.read(str(side.get("body") or ""), ROLES, config)
        if read["undecided"]:
            names = ", ".join(sorted({u["field"] for u in read["undecided"]}))
            return {
                "ok": False,
                "refused": f"the {key} tracker's body has fields github-body-field will not decide on ({names})",
            }
        values = {role: without_attachment(read["values"].get(role) or None) for role in ROLES}
        attachment = has_attachment(str(side.get("body") or "")) or any(
            has_attachment(c) for c in _comment_bodies(side.get("comments"))
        )
        milestone = side.get("milestone")
        out[key] = {
            "number": side.get("number"),
            **{role: values[role] for role in ROLES if role != "issue_description"},
            "has_issue_description": bool(values["issue_description"]),
            "absent": read["absent"],
            "has_cve_json_attachment": attachment,
            "labels": _names(side.get("labels")),
            "milestone": (milestone.get("title") if isinstance(milestone, Mapping) else milestone) or None,
        }
    keep_cwe, drop_cwe = out["keep"]["cwe"], out["drop"]["cwe"]
    keep_sev, drop_sev = out["keep"]["severity"], out["drop"]["severity"]
    unknown = {None, "Unknown", "unknown"}
    out["cwe_conflict"] = bool(keep_cwe and drop_cwe and _cwe_id(keep_cwe) != _cwe_id(drop_cwe))
    out["severity_propagation_risk"] = drop_sev not in unknown and drop_sev != keep_sev
    out["ok"] = True
    return out


def _cwe_id(value: str) -> str:
    match = re.search(r"CWE-\d+", value, re.IGNORECASE)
    return match.group(0).upper() if match else value.strip().lower()
