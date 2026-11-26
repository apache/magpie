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

`nudge_summary` reads the subagent reports of a bulk run, plus a minimal
report for every open tracker pre-flight skipped (`preflight_trackers`: the
pre-flight GraphQL nodes of the `skip-noop` trackers, read for number,
state, title, labels and milestone only, never a comment body).

**Preview** (`stage: preview`, the default, Step 4b). A tracker is a *nudge
candidate* when its `pending_team_question` (a triage proposal or a question
put to named team members, unanswered by them) has waited at least
`nudge_after_days` (default 7) and carries no nudge for it yet (`nudged`).
At or above `nudge_summary_threshold` (default 5; `off` never collapses) the
nudges collapse: none is proposed (`collapsed`) and one plain-text summary is
rendered for `security_list`, the project's private list, as a new thread.
Below the threshold the candidates come back as `per_tracker_nudges`.

**Final** (`stage: final`, Step 6, after the apply loop and the sweep). The
collapse Step 4b decided stands: `collapsed` (its list) is required, the
threshold is not recounted, and only applied state is read (`current_*`
values; every `proposed_*` value is ignored).

The body has five groups, every open tracker in at most one of the first
four, terminal state checked first (a closing disposition such as
`invalid` / `duplicate` / `wontfix` / `not CVE worthy`, or an `announced`
label, lists nowhere):

1. *Needs a decision* — a pending team question, or `needs triage` with none;
2. *Fix work needed* — past triage, no fix PR (target release, cut date);
3. *In flight* — fix PR open or merged, `fix released` not set and the
   release not shipped (release train, its date);
4. *Waiting on the release manager* — `fix released`, or a shipped release,
   with the advisory not sent (the release manager, days since the release);
5. *Upcoming deadlines* — disclosure-window ends and, for groups 2 and 3,
   release dates, within `deadline_horizon_days` (default 14) or overdue.

Each tracker appears as its title over its full URL. A `issue_url` is used
only when it is this tracker's own (`https://github.com/<tracker>/issues/<N>`,
or `<issue_url_prefix><N>` / `<issue_url_prefix><KEY>-<N>` for a non-GitHub tracker); anything else gets
the canonical URL. Titles and questions are scrubbed before rendering: CVE
and GHSA IDs, bare `#NNN` / `owner/repo#NNN` references and every
`do_not_ping` handle and name are removed, and an `@handle` loses its `@`.
People are named without `@`. A login in the operator's `do_not_ping`
(`user`: the `security_issue_sync` block of the resolved personal `user.md`,
`{"do_not_ping": [...]}`; never committed config) is never named, and
nothing shows that anyone was left out. The Guardrails `check` runs over the
body as an `email` surface, plus a residue check for `@`, CVE IDs and bare
references; `draft.clean` must be true before the draft is created.

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
from security_management.shared import refs
from security_management.shared.recipients import configured
from security_management.shared.rollup import code, one_line

DEFAULT_THRESHOLD = 5
DEFAULT_AFTER_DAYS = 7
DEFAULT_HORIZON_DAYS = 14
QUESTION_CHARS = 160
_ADDRESS = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
_OFF = frozenset({"off", "never", "false", "none"})
CLOSING = frozenset({"invalid", "duplicate", "wontfix", "not cve worthy"})
ANNOUNCED = frozenset({"announced", "announced - emails sent"})
_RECORD_ID = re.compile(r"\b(?:CVE-\d{4}-\d{4,7}|GHSA(?:-[0-9a-z]{4}){3})\b", re.IGNORECASE)
_REF = re.compile(r"(?<![\w/])(?:[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+)?#\d{1,7}\b")
_MENTION = re.compile(r"(?<![\w.@])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))\b")
_RESIDUE = (
    ("an @-mention", re.compile(r"(?<![\w.])@[A-Za-z0-9]")),
    ("a CVE or GHSA ID", _RECORD_ID),
)
STAGES = ("preview", "final")


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
    """`do_not_ping` of the `user` input: the `security_issue_sync` block of the personal `user.md`.

    The documented shape is the block itself, `{"do_not_ping": [...]}`; the whole
    `user.md` (`{"security_issue_sync": {"do_not_ping": [...]}}`) is read too, so
    either shape excludes. A `do_not_ping` anywhere else in the input is ignored.
    """
    user = data.get("user")
    if not isinstance(user, Mapping):
        return []
    handles = user.get("do_not_ping")
    nested = user.get("security_issue_sync")
    if handles is None and isinstance(nested, Mapping):
        handles = nested.get("do_not_ping")
    if isinstance(handles, str):
        handles = [handles]
    return [str(h) for h in handles] if isinstance(handles, list) else []


class _Names:
    def __init__(self, people: Mapping[str, Any], excluded: Sequence[str]) -> None:
        self.people = {str(k).lstrip("@").lower(): one_line(v) for k, v in people.items()}
        self.excluded = {str(x).lstrip("@").strip().lower() for x in excluded if str(x).strip()}

    def name(self, login: object) -> str | None:
        handle = one_line(login).lstrip("@")
        if not handle or handle.lower() in self.excluded:
            return None
        full = self.people.get(handle.lower())
        return f"{full} ({handle})" if full and full.lower() != handle.lower() else handle

    def names(self, logins: Sequence[object], fallback: str) -> str:
        named = [n for n in (self.name(x) for x in logins) if n]
        return ", ".join(named) if named else fallback

    def scrub(self, text: str) -> str:
        """`text` without record IDs, bare references or excluded people, and with no `@`."""
        text = _RECORD_ID.sub("", text)
        text = _REF.sub("", text)
        hidden = set(self.excluded)
        hidden |= {self.people[h].lower() for h in self.excluded if self.people.get(h)}
        for word in sorted(hidden, key=len, reverse=True):
            text = re.sub(rf"(?<![\w-])@?{re.escape(word)}(?![\w-])", "", text, flags=re.IGNORECASE)
        text = _MENTION.sub(r"\1", text)
        text = re.sub(r"\(\s*[,;]?\s*\)", "", text)
        text = re.sub(r"\s+([,;:.?!)])", r"\1", text)
        text = re.sub(r"([,;])(\s*[,;])+", r"\1", text)
        text = re.sub(r"(^|[(\s])[,;]\s*", r"\1", text)
        return re.sub(r"\s{2,}", " ", text).strip(" ,;")


def _url(report: Mapping[str, Any], tracker: str, prefix: str) -> str:
    """The tracker's own URL: a reported `issue_url` only when it points at this tracker and issue."""
    number = int(report["issue"])
    canonical = f"https://github.com/{tracker}/issues/{number}"
    given = one_line(report.get("issue_url"))
    if given == canonical:
        return given
    if (
        prefix
        and given.startswith(prefix)
        and re.fullmatch(rf"(?:[A-Z][A-Z0-9]*-)?{number}", given[len(prefix) :])
    ):
        return given
    return canonical


def _closed(report: Mapping[str, Any]) -> bool:
    return one_line(report.get("state")).lower() == "closed"


def _question(report: Mapping[str, Any]) -> Mapping[str, Any] | None:
    pending = report.get("pending_team_question")
    return pending if isinstance(pending, Mapping) and _date(pending.get("since")) else None


def _release(report: Mapping[str, Any], final: bool) -> tuple[str, date | None]:
    title = one_line(report.get("current_milestone"))
    if not final:
        title = one_line(report.get("proposed_milestone")) or title
    title = re.sub(r"\s*\(create\)\s*$", "", title)
    return title, _date(report.get("milestone_due_on"))


def _when(day: date | None) -> str:
    return day.isoformat() if day else "date not set"


def _group(report: Mapping[str, Any]) -> str | None:
    labels = _labels(report)
    if _closed(report) or labels & CLOSING or labels & ANNOUNCED or report.get("advisory_shipped") is True:
        return None
    if _question(report) or "needs triage" in labels:
        return "decision"
    if "fix released" in labels or report.get("release_shipped") is True:
        return "release_manager"
    pr = report.get("fix_pr") or {}
    state = one_line(pr.get("state")).lower() if isinstance(pr, Mapping) else ""
    if state in {"open", "merged"} or labels & {"pr created", "pr merged"}:
        return "in_flight"
    return "fix_work"


def _node_report(node: Mapping[str, Any]) -> dict[str, Any] | None:
    """A minimal report from a pre-flight GraphQL node: number, state, title, labels, milestone."""
    if not isinstance(node, Mapping) or not node.get("number"):
        return None
    labels = node.get("labels") or []
    if isinstance(labels, Mapping):
        labels = labels.get("nodes") or []
    names = [one_line(x.get("name") if isinstance(x, Mapping) else x) for x in labels]
    raw = node.get("milestone")
    milestone: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    return {
        "issue": int(node["number"]),
        "state": one_line(node.get("state")).lower(),
        "title": one_line(node.get("title")),
        "current_labels": [n for n in names if n],
        "current_milestone": one_line(milestone.get("title")) or None,
        "milestone_due_on": one_line(milestone.get("dueOn")) or None,
    }


def _reports(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The subagent reports, then a minimal one for each pre-flight-skipped tracker without a report."""
    reports = [r for r in data.get("reports") or [] if isinstance(r, Mapping) and r.get("issue")]
    seen = {int(r["issue"]) for r in reports}
    for node in data.get("preflight_trackers") or []:
        report = _node_report(node)
        if report and report["issue"] not in seen:
            reports.append(report)
            seen.add(report["issue"])
    return reports


def _render(
    data: Mapping[str, Any],
    reports: list[Mapping[str, Any]],
    today: date,
    collapsed: list[int],
    horizon: int,
    final: bool,
) -> tuple[str, str]:
    tracker = str(data["tracker"])
    prefix = one_line(data.get("issue_url_prefix"))
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

    def heading(report: Mapping[str, Any], lead: str = "") -> list[str]:
        title = names.scrub(one_line(report.get("title")))
        url = _url(report, tracker, prefix)
        if title:
            return [f"- {lead}{title}", f"  {url}"]
        return [f"- {lead.rstrip(': ')}", f"  {url}"] if lead else [f"- {url}"]

    for report in sorted(reports, key=lambda r: int(r["issue"])):
        if _closed(report):
            continue
        open_count += 1
        group = _group(report)
        release, due = _release(report, final)
        if group == "decision":
            pending = _question(report)
            if pending:
                since = _date(pending.get("since"))
                waited = (today - since).days if since else 0
                question = names.scrub(one_line(pending.get("question")))[:QUESTION_CHARS]
                asked = names.names(pending.get("asked") or [], "the security team")
                line = (
                    f"  Question: {question or 'decision pending'}\n  Asked: {asked}; waiting {waited} days"
                )
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
            labels = _labels(report)
            if not state:
                state = "merged" if "pr merged" in labels else "open" if "pr created" in labels else ""
            pr_state = {"open": "fix PR open", "merged": "fix PR merged"}.get(state, "fix PR in progress")
            train = f"release {release}, {_when(due)}" if release else "no release train set"
            groups[group].append((report, f"  {pr_state}; {train}"))
        elif group == "fix_work":
            target = f"target {release}, cut {_when(due)}" if release else "no target release set"
            groups[group].append((report, f"  {target}"))
        else:
            unlisted += 1
            continue
        if group in {"in_flight", "fix_work"} and release and due and (due - today).days <= horizon:
            deadlines.append((due, int(report["issue"]), f"release {release} cut"))
        disclosure = _date(report.get("expected_disclosure_by"))
        if disclosure and (disclosure - today).days <= horizon:
            deadlines.append((disclosure, int(report["issue"]), "disclosure window ends"))

    # Longest-waiting question first; untriaged trackers (no question) after them.
    groups["decision"].sort(key=lambda pair: _date((_question(pair[0]) or {}).get("since")) or today)
    subject = (
        f"{project} security tracker state, {today.isoformat()}"
        if project
        else f"Security tracker state, {today.isoformat()}"
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
    for index, (key, label) in enumerate(headings, start=1):
        entries = groups[key]
        lines += [f"{index}. {label}: {len(entries)}", ""]
        if not entries:
            lines += ["None.", ""]
        for report, detail in entries:
            lines += [*heading(report), detail, ""]
    lines += [f"5. Upcoming deadlines (next {horizon} days, and overdue)", ""]
    if not deadlines:
        lines += ["None.", ""]
    by_issue = {int(r["issue"]): r for r in reports}
    for due, issue, what in sorted(deadlines):
        late = (today - due).days
        flag = f" (OVERDUE by {late} days)" if late > 0 else ""
        lines += [*heading(by_issue[issue], f"{due.isoformat()}: {what}{flag}: "), ""]
    if unlisted:
        lines += [f"{unlisted} other open trackers need nothing from the team right now.", ""]
    lines.append("Drafted by the security-issue-sync skill and reviewed before sending.")
    return subject, "\n".join(lines) + "\n"


def _residue(body: str) -> list[dict[str, str]]:
    """What the scrub must have removed: an @-mention, a record ID or a bare reference, line by line."""
    found: list[dict[str, str]] = []
    for line in body.splitlines():
        for what, pattern in _RESIDUE:
            if pattern.search(line):
                found.append({"surface": "email", "guardrail": f"Summary carries {what}", "evidence": line})
        if refs.bare_refs(line):
            found.append(
                {"surface": "email", "guardrail": "Summary carries a bare reference", "evidence": line}
            )
    return found


def nudge_summary(data: Mapping[str, Any]) -> dict[str, Any]:
    stage = one_line(data.get("stage")) or "preview"
    if stage not in STAGES:
        return {"ok": False, "refused": f"stage {stage!r} is not one of {', '.join(STAGES)}"}
    final = stage == "final"
    try:
        threshold = _threshold(data.get("nudge_summary_threshold"))
        after = _days_setting(data, "nudge_after_days", DEFAULT_AFTER_DAYS)
        horizon = _days_setting(data, "deadline_horizon_days", DEFAULT_HORIZON_DAYS)
    except ValueError as exc:
        return {"ok": False, "refused": str(exc)}
    if threshold is not None and threshold < 1:
        return {"ok": False, "refused": "nudge_summary_threshold must be at least 1, or `off`"}
    today = _time(data["now"]).date()
    reports = _reports(data)
    candidates: list[int] = []
    for report in reports:
        pending = _question(report)
        since = _date(pending.get("since")) if pending else None
        nudged = bool(pending.get("nudged")) if pending else False
        if since and not nudged and not _closed(report) and (today - since).days >= after:
            candidates.append(int(report["issue"]))
    candidates.sort()
    if final:
        kept = sorted({int(n) for n in data.get("collapsed") or []})
        if not kept:
            return {
                "ok": False,
                "refused": "stage final needs `collapsed`, the nudges Step 4b replaced; without it there is no summary",
            }
        collapse, collapsed = True, kept
    else:
        collapse = threshold is not None and len(candidates) >= threshold
        collapsed = candidates if collapse else []
    result: dict[str, Any] = {
        "ok": True,
        "stage": stage,
        "threshold": threshold if threshold is not None else "off",
        "nudge_after_days": after,
        "nudge_candidates": candidates,
        "collapse": collapse,
        "collapsed": collapsed,
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
    subject, body = _render(data, reports, today, collapsed, horizon, final)
    checked = render.check(
        {
            "surfaces": [{"kind": "email", "text": body}],
            "organization": data.get("organization"),
            "own_names": data.get("own_names") or [],
            "cve_tool_url": data.get("cve_tool_url"),
        }
    )
    violations = list(checked["violations"]) + _residue(body)
    result["draft"] = {
        "to": address,
        "subject": subject,
        "body": body,
        "new_thread": True,
        "clean": not violations,
        "violations": violations,
    }
    made = data.get("draft")
    if isinstance(made, Mapping) and one_line(made.get("id")):
        where = one_line(made.get("url"))
        label = f"[{code(made['id'])}]({where})" if where else code(made["id"])
        result["recap_line"] = (
            f"- {len(collapsed)} nudges replaced by summary email draft {label} to {address}: review and send it."
        )
    return result
