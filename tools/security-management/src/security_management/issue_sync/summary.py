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
"""Bulk mode: collapse many team nudges into one state-summary email to the private security list.

`nudge_summary` reads the subagent reports of a bulk run. A tracker is a
*nudge candidate* when its `pending_team_question` (a triage proposal or a
question put to named team members, unanswered by them) has waited at least
`nudge_after_days` (default 7) and carries no nudge for it yet (`nudged`). When the candidates number at least
`nudge_summary_threshold` (default 5; `off` never collapses), the per-tracker
nudges are dropped (`collapsed`) and one plain-text summary is rendered for
`security_list`, the project's private list, as a new thread; below the
threshold the candidates come back as `per_tracker_nudges` and nothing is
rendered.

The body has five groups, every tracker in at most one of the first four:

1. *Needs a decision* — a pending team question (URL, the one-line
   question, who was asked, days waiting), or `needs triage` with none;
2. *Fix work needed* — past triage, no fix PR (target release, cut date);
3. *In flight* — fix PR open or merged, release not shipped (release
   train, its date);
4. *Waiting on the release manager* — released, advisory not sent (the
   release manager, days since the release);
5. *Upcoming deadlines* — disclosure-window ends and release dates within
   `deadline_horizon_days` (default 14), overdue ones flagged.

Closed trackers and trackers in none of the groups are counted, not listed.
People are named without `@` (it is an email). A login in the operator's
`do_not_ping` list (`user`: the resolved personal `user.md`, key
`security_issue_sync.do_not_ping`; never the committed project config) is
never named, and nothing in the body shows that anyone was left out. Each
tracker appears as its title and its full URL; the body also carries the
question, names, release titles and dates, and no CVE ID, severity or
reporter detail.
It runs the Guardrails `check` over itself as an `email` surface.

Given `draft` (`{id, url}`) after the draft was created, it also returns
the recap line.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from security_management.issue_sync import render
from security_management.issue_sync.select import _time
from security_management.shared.recipients import configured
from security_management.shared.rollup import code, one_line

DEFAULT_THRESHOLD = 5
DEFAULT_AFTER_DAYS = 7
DEFAULT_HORIZON_DAYS = 14
QUESTION_CHARS = 160
_ADDRESS = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
_OFF = frozenset({"off", "never", "false", "none"})


def _threshold(value: object) -> int | None:
    """The configured threshold: a positive integer, or `None` for `off`; a bad value raises."""
    if value is None:
        return DEFAULT_THRESHOLD
    if isinstance(value, bool):
        raise ValueError("nudge_summary_threshold must be a positive integer or `off`")
    text = str(value).strip().lower()
    if text in _OFF:
        return None
    if not text.isdigit():
        raise ValueError(f"nudge_summary_threshold {value!r} is not a positive integer or `off`")
    return int(text)


def _days_setting(data: Mapping[str, Any], key: str, default: int) -> int:
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not str(value).strip().isdigit():
        raise ValueError(f"{key} {value!r} is not a non-negative integer")
    return int(str(value).strip())


def _date(value: object) -> date | None:
    text = one_line(value)
    if not text:
        return None
    try:
        return _time(text if "T" in text else text + "T00:00:00+00:00").date()
    except ValueError:
        return None


def _labels(report: Mapping[str, Any]) -> set[str]:
    return {one_line(x).lower() for x in report.get("current_labels") or []}


def _do_not_ping(data: Mapping[str, Any]) -> list[str]:
    """`security_issue_sync.do_not_ping` from the personal `user.md` only."""
    user = data.get("user")
    block = user.get("security_issue_sync") if isinstance(user, Mapping) else None
    handles = block.get("do_not_ping") if isinstance(block, Mapping) else None
    return [str(h) for h in handles] if isinstance(handles, list) else []


def _heading(report: Mapping[str, Any], url: str, prefix: str = "") -> list[str]:
    """`- <prefix><title>` then the full URL on its own line; no title, just the prefix."""
    title = one_line(report.get("title"))
    if title:
        return [f"- {prefix}{title}", f"  {url}"]
    return [f"- {prefix.rstrip(': ')}", f"  {url}"] if prefix else [f"- {url}"]


def _url(report: Mapping[str, Any], tracker: str) -> str:
    return one_line(report.get("issue_url")) or f"https://github.com/{tracker}/issues/{int(report['issue'])}"


def _closed(report: Mapping[str, Any]) -> bool:
    return one_line(report.get("state")).lower() == "closed"


def _question(report: Mapping[str, Any]) -> Mapping[str, Any] | None:
    pending = report.get("pending_team_question")
    return pending if isinstance(pending, Mapping) and _date(pending.get("since")) else None


class _Names:
    def __init__(self, people: Mapping[str, Any], excluded: Sequence[str]) -> None:
        self.people = {str(k).lstrip("@").lower(): one_line(v) for k, v in people.items()}
        self.excluded = {str(x).lstrip("@").lower() for x in excluded}

    def name(self, login: object) -> str | None:
        handle = one_line(login).lstrip("@")
        if not handle or handle.lower() in self.excluded:
            return None
        full = self.people.get(handle.lower())
        return f"{full} ({handle})" if full and full.lower() != handle.lower() else handle

    def names(self, logins: Sequence[object], fallback: str) -> str:
        named = [n for n in (self.name(x) for x in logins) if n]
        return ", ".join(named) if named else fallback


def _release(report: Mapping[str, Any]) -> tuple[str, date | None]:
    title = one_line(report.get("proposed_milestone")) or one_line(report.get("current_milestone"))
    title = re.sub(r"\s*\(create\)\s*$", "", title)
    return title, _date(report.get("milestone_due_on"))


def _when(day: date | None) -> str:
    return day.isoformat() if day else "date not set"


def _group(report: Mapping[str, Any]) -> str | None:
    labels = _labels(report)
    if _question(report) or "needs triage" in labels:
        return "decision"
    if report.get("release_shipped") is True and report.get("advisory_shipped") is not True:
        return "release_manager"
    pr = report.get("fix_pr") or {}
    state = one_line(pr.get("state")).lower() if isinstance(pr, Mapping) else ""
    if state in {"open", "merged"} or labels & {"pr created", "pr merged"}:
        return "in_flight"
    if not labels & {"fix released", "announced", "announced - emails sent"}:
        return "fix_work"
    return None


def _render(
    data: Mapping[str, Any],
    reports: list[Mapping[str, Any]],
    today: date,
    collapsed: list[int],
    horizon: int,
) -> tuple[str, str]:
    tracker = str(data["tracker"])
    names = _Names(data.get("people") or {}, _do_not_ping(data))
    project = one_line(data.get("project_name"))
    groups: dict[str, list[tuple[Mapping[str, Any], str]]] = {
        "decision": [],
        "release_manager": [],
        "in_flight": [],
        "fix_work": [],
    }
    deadlines: list[tuple[date, int, str]] = []
    unlisted = 0
    open_count = 0
    for report in sorted(reports, key=lambda r: int(r["issue"])):
        if _closed(report):
            unlisted += 1
            continue
        open_count += 1
        group = _group(report)
        release, due = _release(report)
        if group == "decision":
            pending = _question(report)
            if pending:
                since = _date(pending.get("since"))
                waited = (today - since).days if since else 0
                question = one_line(pending.get("question"))[:QUESTION_CHARS] or "decision pending"
                asked = names.names(pending.get("asked") or [], "the security team")
                line = f"  Question: {question}\n  Asked: {asked}; waiting {waited} days"
                groups[group].append((report, line))
            else:
                groups[group].append((report, "  Not triaged yet; no proposal on the tracker"))
        elif group == "release_manager":
            rm = names.name(report.get("release_manager"))
            released = _date(report.get("released_on"))
            shipped = f"{release} shipped" if release else "the release"
            held = (
                f"{(today - released).days} days since {shipped}"
                if released
                else f"since {shipped}, date unknown"
            )
            line = f"  Release manager: {rm}; waiting {held}" if rm else f"  Waiting {held}"
            groups[group].append((report, line))
        elif group == "in_flight":
            pr = report.get("fix_pr") or {}
            state = one_line(pr.get("state")).lower() if isinstance(pr, Mapping) else ""
            pr_state = {"open": "fix PR open", "merged": "fix PR merged"}.get(state, "fix PR in progress")
            train = f"release {release}, {_when(due)}" if release else "no release train set"
            groups[group].append((report, f"  {pr_state}; {train}"))
        elif group == "fix_work":
            target = f"target {release}, cut {_when(due)}" if release else "no target release set"
            groups[group].append((report, f"  {target}"))
        else:
            unlisted += 1
        if group in {"in_flight", "fix_work"} and release and due and (due - today).days <= horizon:
            deadlines.append((due, int(report["issue"]), f"release {release} cut"))
        disclosure = _date(report.get("expected_disclosure_by"))
        announced = _labels(report) & {"announced", "announced - emails sent"}
        if disclosure and not announced and (disclosure - today).days <= horizon:
            deadlines.append((disclosure, int(report["issue"]), "disclosure window ends"))

    # Longest-waiting question first; untriaged trackers (no question) after them.
    groups["decision"].sort(key=lambda pair: _date((_question(pair[0]) or {}).get("since")) or today)
    title = (
        f"{project} security tracker state, {today.isoformat()}"
        if project
        else (f"Security tracker state, {today.isoformat()}")
    )
    lines = [
        "Hello security team,",
        "",
        f"This is the state of the {open_count} open trackers in {tracker} after today's sync.",
        f"It replaces {len(collapsed)} separate reminder comments on the trackers.",
        "Please answer on each tracker, so every decision stays with its own case.",
        "",
    ]
    headings = (
        ("decision", "Needs a decision"),
        ("fix_work", "Fix work needed (valid, no fix PR yet)"),
        ("in_flight", "In flight (fix PR open or merged, awaiting release)"),
        ("release_manager", "Waiting on the release manager (released, advisory not sent)"),
    )
    for index, (key, heading) in enumerate(headings, start=1):
        entries = groups[key]
        lines += [f"{index}. {heading}: {len(entries)}", ""]
        if not entries:
            lines += ["None.", ""]
        for report, detail in entries:
            lines += [*_heading(report, _url(report, tracker)), detail, ""]
    lines += [f"5. Upcoming deadlines (next {horizon} days, and overdue)", ""]
    if not deadlines:
        lines += ["None.", ""]
    by_issue = {int(r["issue"]): r for r in reports}
    for due, issue, what in sorted(deadlines):
        late = (today - due).days
        flag = f" (OVERDUE by {late} days)" if late > 0 else ""
        report = by_issue[issue]
        lines += [*_heading(report, _url(report, tracker), f"{due.isoformat()}: {what}{flag}: "), ""]
    if unlisted:
        lines += [f"{unlisted} other trackers in this sync need nothing from the team right now.", ""]
    lines.append("Drafted by the security-issue-sync skill and reviewed before sending.")
    return title, "\n".join(lines) + "\n"


def nudge_summary(data: Mapping[str, Any]) -> dict[str, Any]:
    try:
        threshold = _threshold(data.get("nudge_summary_threshold"))
        after = _days_setting(data, "nudge_after_days", DEFAULT_AFTER_DAYS)
        horizon = _days_setting(data, "deadline_horizon_days", DEFAULT_HORIZON_DAYS)
    except ValueError as exc:
        return {"ok": False, "refused": str(exc)}
    if threshold is not None and threshold < 1:
        return {"ok": False, "refused": "nudge_summary_threshold must be at least 1, or `off`"}
    today = _time(data["now"]).date()
    reports = [r for r in data.get("reports") or [] if isinstance(r, Mapping) and r.get("issue")]
    candidates: list[int] = []
    for report in reports:
        pending = _question(report)
        since = _date(pending.get("since")) if pending else None
        nudged = bool(pending.get("nudged")) if pending else False
        if since and not nudged and not _closed(report) and (today - since).days >= after:
            candidates.append(int(report["issue"]))
    candidates.sort()
    collapse = threshold is not None and len(candidates) >= threshold
    result: dict[str, Any] = {
        "ok": True,
        "threshold": threshold if threshold is not None else "off",
        "nudge_after_days": after,
        "nudge_candidates": candidates,
        "collapse": collapse,
        "collapsed": candidates if collapse else [],
        "per_tracker_nudges": [] if collapse else candidates,
        "draft": None,
    }
    if not collapse:
        return result
    address = configured(data.get("security_list"))
    if not address or not _ADDRESS.match(address):
        return {
            "ok": False,
            "refused": "security_list is not configured: the summary goes only to the private list",
        }
    public = {str(a).strip().lower() for a in data.get("public_lists") or [] if a}
    if address.lower() in public:
        return {
            "ok": False,
            "refused": f"{address} is a public list; the summary goes only to the private security list",
        }
    subject, body = _render(data, reports, today, candidates, horizon)
    checked = render.check(
        {
            "surfaces": [{"kind": "email", "text": body}],
            "organization": data.get("organization"),
            "own_names": data.get("own_names") or [],
            "cve_tool_url": data.get("cve_tool_url"),
        }
    )
    result["draft"] = {
        "to": address,
        "subject": subject,
        "body": body,
        "new_thread": True,
        "clean": checked["clean"],
        "violations": checked["violations"],
    }
    made = data.get("draft")
    if isinstance(made, Mapping) and one_line(made.get("id")):
        where = one_line(made.get("url"))
        label = f"[{code(made['id'])}]({where})" if where else code(made["id"])
        result["recap_line"] = (
            f"- {len(candidates)} nudges replaced by summary email draft {label} to {address}: review and send it."
        )
    return result
