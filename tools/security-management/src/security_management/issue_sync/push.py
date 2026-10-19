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
"""Step 5b: whether the regenerated CVE JSON is pushed, and what the run says about it.

The decision flow of `apply-and-push.md`, in order, each call fed what the
previous one printed (`next` names the command to run and pass back):

1. no regeneration (no CVE) — `skip`;
2. the seven pre-push gates, first failure — `block`. Three are checked
   here on the JSON: the title through the cve-allocate strip cascade, an
   upgrade-target version in the summary, the `CWE-NNN: <Title>` long form.
   Four need judgement and come in as the model's verdicts (`judged`):
   trigger conditions, the incomplete-fix clause, the private-finder
   anonymisation, the conservative affected range. A verdict not given is
   asked for, never assumed;
3. the session probe — `expired` / `not-configured` is a manual-paste
   `hand-off`, with a recap blocker only when a `fix released` transition
   leaves the record `allocated`;
4. the push — a non-zero exit is a manual-paste `hand-off` with the error
   as a blocker, never retried this run;
5. the verify — a push carrying `review-ready` onto an `allocated` record is
   confirmed with `fetch_current_state`; `allocated` after it is a blocker.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.cve_allocate.title import TRACKER_PREFIXES, strip
from security_management.shared import selectors
from security_management.shared.rollup import one_line
from security_management.shell import w

GATES = (
    "title_strip_cascade",
    "upgrade_target_version",
    "trigger_conditions",
    "incomplete_fix_clause",
    "cwe_long_form",
    "anonymise_private_finder",
    "conservative_affected_range",
)
JUDGED = (
    "trigger_conditions",
    "incomplete_fix_clause",
    "anonymise_private_finder",
    "conservative_affected_range",
)
NATIVE = {"DRAFT": "allocated", "REVIEW": "review-ready", "READY": "publish-ready", "PUBLIC": "public"}
LATER = ("review-ready", "publish-ready", "public")
OAUTH_API = "<framework>/tools/cve-tool-vulnogram/oauth-api"
_UPGRADE = re.compile(r"upgrade[^.\n]{0,80}?\b[A-Za-z][\w.-]{0,60} v?\d+\.\d+(?:\.\d+)?\b", re.IGNORECASE)
_CWE_LONG = re.compile(r"^CWE-\d+: \S")


def _cna(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return (record.get("containers") or {}).get("cna") or {}


def mechanical(record: Mapping[str, Any], names: list[str], short: list[str]) -> dict[str, bool]:
    cna = _cna(record)
    title = one_line(cna.get("title"))
    summary = " ".join(str(d.get("value") or "") for d in cna.get("descriptions") or [])
    problem = (((cna.get("problemTypes") or [{}])[0].get("descriptions") or [{}])[0]).get("description") or ""
    return {
        "title_strip_cascade": bool(title) and strip(title, names, short, TRACKER_PREFIXES) == title,
        "upgrade_target_version": bool(_UPGRADE.search(summary)),
        "cwe_long_form": bool(_CWE_LONG.match(str(problem))),
    }


def _state(value: object) -> str | None:
    text = one_line(value)
    return NATIVE.get(text.upper(), text.lower() or None) if text else None


def decide(data: Mapping[str, Any]) -> dict[str, Any]:
    cve_id = one_line(data.get("cve_id"))
    oauth_api = w(str(data.get("oauth_api") or OAUTH_API))

    def out(action: str, why: str, **extra: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "action": action,
            "gate_failed": extra.pop("gate_failed", None),
            "handoff_variant": extra.pop("handoff_variant", None),
            "state_advance": extra.pop("state_advance", None),
            "recap_blocker": extra.pop("recap_blocker", False),
            "next": extra.pop("next", None),
            "reason": why,
            **extra,
        }

    if not data.get("regenerated") or not cve_id:
        return out(
            "skip", "Step 5a did not regenerate the JSON (no CVE allocated): there is no record to push"
        )
    cve_id = cve_id.upper()
    if not selectors.CVE.match(cve_id):
        return {"ok": False, "refused": f"cve_id {cve_id!r} is not CVE-YYYY-NNNNN"}
    names = [one_line(n) for n in data.get("project_names") or [] if one_line(n)]
    if not names:
        return {"ok": False, "refused": "project_names is empty: read them from title-normalization.md"}
    checks = mechanical(data.get("record") or {}, names, [one_line(n) for n in data.get("short_names") or []])
    judged = data.get("judged") or {}
    for gate in GATES:
        if gate in checks:
            passed = checks[gate]
        else:
            if gate not in judged:
                return out(
                    "pending",
                    f"judge the {gate} gate on the regenerated JSON and pass it in judged",
                    next=gate,
                )
            passed = bool(judged[gate])
        if not passed:
            return out(
                "block",
                f"the {gate} gate fails: fix the body field, re-regenerate and re-scan; do not push",
                gate_failed=gate,
            )
    before = _state(data.get("record_state"))
    pushed = _state(((data.get("record") or {}).get("CNA_private") or {}).get("state"))
    transition = bool(data.get("fix_released_transition"))
    stuck = transition and before == "allocated"
    probe = one_line(data.get("session")).lower() or None
    if probe is None:
        return out(
            "pending", "probe the CVE tool session", next=f"uv run --project {oauth_api} vulnogram-api-check"
        )
    if probe in ("expired", "not-configured"):
        why = (
            "the session expired: remind the operator to re-run vulnogram-api-setup; manual-paste hand-off this run"
            if probe == "expired"
            else "no session is configured: manual-paste hand-off through the source tab"
        )
        if stuck:
            why += "; the record is still allocated on a fix released transition, so the recap carries the deferral blocker"
        return out("hand-off", why, handoff_variant="manual-paste", recap_blocker=stuck)
    if probe != "valid":
        return {"ok": False, "refused": f"session {probe!r} is none of valid, expired, not-configured"}
    if data.get("push_exit") is None:
        json_file = one_line(data.get("json_file")) or f"<scratch>/cve-{cve_id}.json"
        return out(
            "pending",
            "push the regenerated JSON",
            next=f"uv run --project {oauth_api} vulnogram-api-record-update --cve-id {w(cve_id)} --json-file {w(json_file)}",
        )
    if int(data["push_exit"]) != 0:
        return out(
            "hand-off",
            "the push failed: surface the error verbatim, use the manual-paste hand-off, and retry on the next sync (not now)",
            handoff_variant="manual-paste",
            recap_blocker=True,
        )
    if before == "allocated" and pushed == "review-ready":
        fetched = _state(data.get("fetched_state"))
        if fetched is None:
            return out(
                "pending",
                "verify the state advance",
                next=f"uv run --project {oauth_api} vulnogram-api-record-fetch --cve-id {w(cve_id)} --jq '.body.CNA_private.state'",
            )
        if fetched in LATER:
            return out(
                "push",
                "pushed, and the record moved allocated -> review-ready",
                handoff_variant="oauth-pushed",
                state_advance="allocated->review-ready",
            )
        return out(
            "push",
            f"pushed, but the record is still {fetched}: do not post the RM hand-off; fire the fill-fields comment",
            handoff_variant="oauth-pushed",
            recap_blocker=True,
        )
    return out("push", "pushed; the record's state did not change", handoff_variant="oauth-pushed")
