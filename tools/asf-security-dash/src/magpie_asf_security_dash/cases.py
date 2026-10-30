# SPDX-License-Identifier: Apache-2.0
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

"""The dashboard's cases, normalised, and their comparison with a tracker.

A case is one report the ASF Security team tracks, keyed by the `Message-ID`
of the email that reported it.  Its `state` comes from the dashboard:
`untriaged`, `confirmed` (it has CVE IDs), or what it waits for —
`cve-allocation`, `disclosure`, `non-issue-feedback`, `non-issue-docs`,
`non-issue-upstream`, or any other `wf` state the security team uses.

Reconciling never changes anything.  It pairs each case with a tracker issue
and lists where the two disagree, each finding naming who can fix it: the
project's own tracker, the dashboard's triage form (which emails the reporter
itself), or the ASF Security team, who alone edit the dashboard's records.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from magpie_asf_security_dash.client import DashError, project_url

ACCEPTED_STATES = frozenset({"confirmed", "cve-allocation", "disclosure"})
#: States the dashboard gives the entries of its multi-thread labels
#: (`aaa-glasswing`, `aaa-non-fwd`): the security team's own bookkeeping.
LABEL_STATES = frozenset({"glasswing", "non-fwd"})
DECISIONS = ("undecided", "accepted", "rejected")


def message_id(value: object) -> str:
    """A `Message-ID` without angle brackets or surrounding space."""
    if not isinstance(value, str):
        return ""
    return value.strip().removeprefix("<").removesuffix(">").strip()


def stage(state: str) -> str:
    """`untriaged`, `accepted`, `rejected`, or `other` for a dashboard state."""
    if state == "untriaged":
        return "untriaged"
    if state in ACCEPTED_STATES:
        return "accepted"
    if state.startswith("non-issue"):
        return "rejected"
    return "other"


def normalise(raw: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The reports API's entries in the shape the rest of the bridge uses."""
    cases = []
    for entry in raw:
        mid = message_id(entry.get("message_id"))
        if not mid:
            raise DashError(f"a case has no message_id: {dict(entry)!r}")
        state = str(entry.get("state") or "")
        cves = entry.get("cves") or []
        if not isinstance(cves, list):
            raise DashError(f"case {mid}: cves is not a list")
        cases.append(
            {
                "message_id": mid,
                "label": state in LABEL_STATES,
                "cves": sorted({str(c).upper() for c in cves}),
                "title": str(entry.get("title") or ""),
                "state": state,
                "stage": stage(state),
                "date": str(entry.get("date") or ""),
                "thread": str(entry.get("asf_member_link") or ""),
            }
        )
    return cases


def _tracker_issue(raw: Mapping[str, Any]) -> dict[str, Any]:
    issue_id = raw.get("id")
    if issue_id in (None, ""):
        raise DashError(f"a tracker issue has no id: {dict(raw)!r}")
    state = raw.get("state", "open")
    if state not in ("open", "closed"):
        raise DashError(f"tracker issue {issue_id}: state must be open or closed, not {state!r}")
    decision = raw.get("decision", "undecided")
    if decision not in DECISIONS:
        raise DashError(f"tracker issue {issue_id}: decision must be one of {', '.join(DECISIONS)}")
    return {
        "id": str(issue_id),
        "url": str(raw.get("url") or ""),
        "state": state,
        "decision": decision,
        "cves": sorted({str(c).upper() for c in raw.get("cves") or []}),
        "message_ids": [m for m in (message_id(v) for v in raw.get("message_ids") or []) if m],
    }


def _finding(
    kind: str, fix: str, detail: str, case: dict[str, Any] | None, issue: dict[str, Any] | None
) -> dict[str, Any]:
    found: dict[str, Any] = {"kind": kind, "fix": fix, "detail": detail}
    if case is not None:
        found["case"] = {k: case[k] for k in ("message_id", "title", "state", "cves", "thread")}
    if issue is not None:
        found["issue"] = {k: issue[k] for k in ("id", "url", "state", "decision", "cves")}
    return found


def reconcile(pmc: str, cases: list[dict[str, Any]], tracker: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Pair the dashboard's open cases with tracker issues and list every disagreement.

    A case pairs with the issue that records its `Message-ID`, else with the
    one issue sharing one of its CVE IDs.  `fix` names who acts on a finding:
    `tracker` (propose the change to the project's tracker), `import`
    (`security-issue-import` the thread), `dashboard-triage` (the PMC triages on
    the project page — that sends the reporter an email of its own), or
    `asf-security` (only the ASF Security team edits the dashboard's records).
    """
    issues = [_tracker_issue(raw) for raw in tracker]
    by_mid: dict[str, list[dict[str, Any]]] = {}
    by_cve: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        for mid in issue["message_ids"]:
            by_mid.setdefault(mid, []).append(issue)
        for cve in issue["cves"]:
            by_cve.setdefault(cve, []).append(issue)

    findings: list[dict[str, Any]] = []
    paired: set[str] = set()
    # Issues an ambiguous case might belong to: not known to be off the dashboard.
    undetermined: set[str] = set()
    page = project_url(pmc)
    labels = [case for case in cases if case["label"]]
    for case in cases:
        if case["label"]:
            continue
        candidates = by_mid.get(case["message_id"]) or [
            issue for cve in case["cves"] for issue in by_cve.get(cve, [])
        ]
        unique = {issue["id"]: issue for issue in candidates}
        if len(unique) > 1:
            findings.append(
                _finding(
                    "ambiguous",
                    "tracker",
                    f"the case matches issues {', '.join(sorted(unique))}; record its Message-ID on one of them",
                    case,
                    None,
                )
            )
            undetermined.update(unique)
            continue
        if not unique:
            findings.append(_untracked(case))
            continue
        issue = next(iter(unique.values()))
        paired.add(issue["id"])
        findings.extend(_compare(case, issue, page))

    for issue in issues:
        if issue["id"] in paired | undetermined or issue["state"] == "closed" or not issue["message_ids"]:
            continue
        if issue["decision"] == "rejected":
            continue
        findings.append(
            _finding(
                "not-on-dashboard",
                "asf-security",
                "no open dashboard case: the report may not have reached security@apache.org, "
                "or the security team has closed it",
                None,
                issue,
            )
        )
    return {
        "pmc": pmc,
        "cases": len(cases),
        "issues": len(issues),
        "paired": len(paired),
        "labels_skipped": len(labels),
        "findings": findings,
    }


def _untracked(case: dict[str, Any]) -> dict[str, Any]:
    """A case with no issue: import it, unless it may be one of the standing labels.

    The dashboard lists the security team's catch-all labels, such as
    `aaa-support`, as untriaged cases, and the API does not say which entries
    they are, so a human looks before an untriaged case is imported.
    """
    if case["stage"] == "untriaged":
        return _finding(
            "untracked",
            "review",
            "the tracker has no issue for this case; the dashboard does not say whether it is a report "
            "or one of the security team's standing labels (aaa-…, zzz-…), so check the thread before importing",
            case,
            None,
        )
    return _finding(
        "untracked",
        "import",
        "the dashboard tracks this report but the tracker has no issue for it",
        case,
        None,
    )


def _compare(case: dict[str, Any], issue: dict[str, Any], page: str) -> list[dict[str, Any]]:
    out = []
    only_dash = sorted(set(case["cves"]) - set(issue["cves"]))
    only_tracker = sorted(set(issue["cves"]) - set(case["cves"]))
    if only_dash:
        out.append(
            _finding(
                "cve-missing-in-tracker",
                "tracker",
                f"the dashboard records {', '.join(only_dash)}",
                case,
                issue,
            )
        )
    if only_tracker:
        out.append(
            _finding(
                "cve-missing-on-dashboard",
                "asf-security",
                f"the tracker records {', '.join(only_tracker)}",
                case,
                issue,
            )
        )
    # Decisions are compared whatever the issue's state: an issue closed as
    # invalid still has to be recorded on the dashboard, which tells the reporter.
    triage = case["stage"] == "untriaged" and issue["decision"] != "undecided"
    if triage:
        out.append(
            _finding(
                "triage-on-dashboard",
                "dashboard-triage",
                f"the tracker has {issue['decision']} the report; record it at {page} — "
                "the dashboard then emails the reporter itself, so send no separate reply",
                case,
                issue,
            )
        )
    elif case["stage"] in ("accepted", "rejected") and issue["decision"] == "undecided":
        out.append(
            _finding(
                "decision-missing-in-tracker",
                "tracker",
                f"the dashboard has the report {case['stage']}; the tracker issue is still undecided",
                case,
                issue,
            )
        )
    elif {case["stage"], issue["decision"]} == {"accepted", "rejected"}:
        out.append(
            _finding(
                "decision-conflict",
                "tracker",
                f"the dashboard has the report {case['stage']}, the tracker {issue['decision']}",
                case,
                issue,
            )
        )
    if issue["state"] == "closed":
        # Triaging on the dashboard moves the case on, so only ask the
        # security team to close it when there is no triage to record.
        if not triage:
            out.append(
                _finding(
                    "closed-in-tracker",
                    "asf-security",
                    "the tracker issue is closed but the dashboard still lists the case as open",
                    case,
                    issue,
                )
            )
    elif case["state"] == "disclosure":
        out.append(
            _finding(
                "disclosure-pending",
                "tracker",
                "the dashboard says the fix is released and the announcement is still to go out",
                case,
                issue,
            )
        )
    return out
