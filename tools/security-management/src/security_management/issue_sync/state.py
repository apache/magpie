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
"""Step 1 observations that are arithmetic on dates, labels and markers.

- `disclosure` (1a): `issue_age_days` from `createdAt`, and the flags
  `overdue_for_disclosure` (past `window_days`, not `announced`),
  `approaching_window_end` (past 80 % of it), `grace_period_expired` (`pr
  merged` / `fix released`, past `window_days + grace_period_days`) and
  `distributor_notify_pending` (`pre_announce_distributors`, `pr merged` /
  `fix released`, not `announced`). Defaults 90 / 14 / false.
- `staleness` (1c step 5): stale when the team's latest outbound message is
  older than `reporter_response_timeout_days` (default 14) and the
  reporter has not replied since; the clock never runs while the latest
  message is the reporter's.
- `closed_announced` (1g): the cve.org state as the next move (`PUBLISHED`
  → the CVE-published email unless a prior notification is recorded,
  `RESERVED` → wait, `REJECTED` → blocker, lookup error → retry), the
  security-pages checklist and reminder markers in the body and comments,
  and the advisory-records step, including the planner's exit code.
- `release_vote` (1h): an open `[VOTE]` thread on the dev list whose first
  version matches the fix-PR milestone, for a tracker in the `pr merged`
  window; a `[RESULT]` message closes a vote.
- `advisory_archive` (1d): whether a candidate archive URL may be proposed
  as the *Public advisory URL*, the field whose capture moves the CVE
  record to `PUBLIC`. A text search for the CVE ID matches any public post
  that mentions it, so the candidate is accepted only when the thread the
  archive returns is on the configured public advisory list, its root
  subject is the advisory's own (`<CVE-ID>: <description>`, the subject
  the CVE tool sends, optionally after `[...]` list tags; never a `Re:` or
  `Fwd:`), and the URL sits under the configured archive. Acceptance is a
  proposal: `requires_confirmation` is always true.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from email.utils import getaddresses
from typing import Any

from security_management.issue_sync.select import _labels, _time
from security_management.shared.rollup import one_line

CHECKLIST_DONE = re.compile(
    r"^\s*[-*] \[[xX]\] <!-- apache-magpie: security-pages-checklist v1 -->", re.MULTILINE
)
REMINDER = "<!-- apache-magpie: security-pages-reminder v1 -->"
RECORDS = "<!-- apache-magpie: advisory-records v1 -->"
NOTIFIED = re.compile(r"CVE-published reporter notification drafted", re.IGNORECASE)
_VERSION = re.compile(r"\b(\d+\.\d+(?:\.\d+)?)\b")
_VOTE = re.compile(r"\[VOTE\]", re.IGNORECASE)
_RESULT = re.compile(r"\[RESULT\]", re.IGNORECASE)


def _days(start: datetime, end: datetime) -> int:
    return (end.date() - start.date()).days


def _configured_days(data: Mapping[str, Any], key: str, default: int) -> int:
    value = data.get(key)
    return default if value is None else int(value)


def disclosure(data: Mapping[str, Any]) -> dict[str, Any]:
    now = _time(data["now"])
    age = _days(_time(data["created_at"]), now)
    window = _configured_days(data, "window_days", 90)
    if window <= 0:  # as issue-import reads it: the window must be positive
        window = 90
    grace = _configured_days(data, "grace_period_days", 14)
    labels = set(_labels(data))
    announced = bool(labels & {"announced", "announced - emails sent"})
    shipping = bool(labels & {"pr merged", "fix released"})
    expected = _time(data["created_at"]) + timedelta(days=window + grace)
    return {
        "ok": True,
        "issue_age_days": age,
        "overdue_for_disclosure": age > window and not announced,
        "approaching_window_end": age > window * 0.8 and not announced,
        "grace_period_expired": shipping and age > window + grace and not announced,
        "distributor_notify_pending": bool(data.get("pre_announce_distributors"))
        and shipping
        and not announced,
        "expected_disclosure_by": expected.date().isoformat(),
    }


def staleness(data: Mapping[str, Any]) -> dict[str, Any]:
    now = _time(data["now"])
    timeout = _configured_days(data, "timeout_days", 14)
    messages = sorted((_time(m["at"]), bool(m.get("from_team"))) for m in data.get("messages") or [])
    if not messages or not messages[-1][1]:
        return {
            "ok": True,
            "stale": False,
            "days": None,
            "reason": "the latest message is the reporter's, or there is none",
        }
    days = _days(messages[-1][0], now)
    stale = days > timeout
    return {
        "ok": True,
        "stale": stale,
        "days": days,
        "reason": f"the team's latest message is {days} days old (timeout {timeout})"
        + ("; propose proceeding without the reporter's sign-off" if stale else ""),
    }


def _texts(data: Mapping[str, Any]) -> list[str]:
    comments = data.get("comments") or []
    if isinstance(comments, Mapping):
        comments = comments.get("nodes") or []
    return [str(data.get("body") or "")] + [
        str(c.get("body") if isinstance(c, Mapping) else c) for c in comments
    ]


RECORD_EXITS = {
    0: "pending",
    4: "pending_checkout",
    3: "refused",
    2: "config_error",
}


def closed_announced(data: Mapping[str, Any]) -> dict[str, Any]:
    texts = _texts(data)
    # The state markers below are written in comments, never in the body:
    # the body carries report text, which must not be able to satisfy them.
    comments = texts[1:]
    out: dict[str, Any] = {"ok": True, "blockers": []}
    if not one_line(data.get("cve_id")):
        out["cve_org"] = "skip"
        out["note"] = "no CVE ID: a closing disposition, dropped from the closed-bucket sweep"
        return out
    state = one_line(data.get("cve_org_state")).upper()
    if data.get("lookup_failed"):
        out["cve_org"] = "retry"
        out["note"] = "cve.org lookup failed — try again next sync"
    elif state == "PUBLISHED":
        notified = any(NOTIFIED.search(t) for t in comments) and bool(data.get("notification_sent_on_thread"))
        out["cve_org"] = "already_notified" if notified else "notify"
        out["date_published"] = data.get("date_published")
    elif state == "RESERVED":
        out["cve_org"] = "wait"
        out["note"] = "cve.org shows RESERVED; propagation not complete yet"
    elif state == "REJECTED":
        out["cve_org"] = "blocker"
        out["blockers"].append(
            "the CVE record was rejected after publication: flag it to the security team, no email"
        )
    else:
        return {"ok": False, "refused": f"cve_org_state {state!r} is none of PUBLISHED, RESERVED, REJECTED"}
    records = data.get("advisory_records_configured")
    if records:
        out["security_pages_reminder_pending"] = False
        if any(t.lstrip().startswith(RECORDS) for t in comments):
            out["advisory_records"] = "done"
        elif state != "PUBLISHED":
            out["advisory_records"] = "waiting_for_cve_org"
        elif data.get("planner_exit") is None:
            out["advisory_records"] = "run_planner"
        else:
            code = int(data["planner_exit"])
            unchanged = code == 0 and one_line(data.get("planner_result")).lower() == "unchanged"
            out["advisory_records"] = (
                "already_recorded" if unchanged else RECORD_EXITS.get(code, "config_error")
            )
            if out["advisory_records"] == "refused":
                out["blockers"].append(
                    f"advisory records refused: {one_line(data.get('planner_reason')) or 'see the planner output'}"
                )
    else:
        out["advisory_records"] = "not_configured"
        populated = bool(one_line(data.get("public_advisory_url")))
        ticked = any(CHECKLIST_DONE.search(t) for t in comments)
        reminded = any(t.lstrip().startswith(REMINDER) for t in comments)
        out["security_pages_reminder_pending"] = populated and not ticked and not reminded
    return out


def _first_version(subject: str) -> str | None:
    match = _VERSION.search(subject)
    return match.group(1) if match else None


def release_vote(data: Mapping[str, Any]) -> dict[str, Any]:
    if not data.get("gating"):
        return {"ok": True, "release_vote_in_progress": False, "reason": "release-vote gating is off"}
    labels = set(_labels(data))
    if "pr merged" not in labels or "fix released" in labels:
        return {
            "ok": True,
            "release_vote_in_progress": False,
            "reason": "outside the pr merged → fix released window",
        }
    target = _first_version(str(data.get("fix_milestone") or ""))
    if not target:
        return {
            "ok": True,
            "release_vote_in_progress": False,
            "reason": "no parseable fix-PR milestone version",
        }
    threads: dict[str, dict[str, Any]] = {}
    for message in data.get("messages") or []:
        subject = one_line(message.get("subject"))
        if not _VOTE.search(subject):
            continue
        key = re.sub(r"^(?:re:\s*|\[result\]\s*)+", "", subject, flags=re.IGNORECASE).strip().lower()
        thread = threads.setdefault(key, {"subject": subject, "url": message.get("url"), "closed": False})
        if _RESULT.search(subject):
            thread["closed"] = True
        elif not thread.get("url"):
            thread["url"] = message.get("url")
    product = one_line(data.get("release_product")).lower()
    for thread in threads.values():
        subject = thread["subject"]
        version = _first_version(re.sub(r"^.*?release\s+", "", subject, flags=re.IGNORECASE))
        if version != target or thread["closed"]:
            continue
        if product and product not in subject.lower():
            continue
        return {
            "ok": True,
            "release_vote_in_progress": True,
            "release_vote_thread_url": thread["url"],
            "reason": f"open vote for {version}, matching the fix-PR milestone",
        }
    return {"ok": True, "release_vote_in_progress": False, "reason": f"no open [VOTE] thread for {target}"}


_CVE = re.compile(r"^CVE-\d{4}-\d{4,7}$")


def _list_address(value: object) -> str:
    """`users@foo.apache.org` from that address or PonyMail's `<users.foo.apache.org>` list id."""
    text = one_line(value).strip().strip("<>").strip().lower()
    if text and "@" not in text and "." in text:
        local, _, domain = text.partition(".")
        text = f"{local}@{domain}"
    return text


def _sender_address(value: object) -> str:
    """The mailbox of a `From`-style value (`Name <a@b>` or `a@b`), lower-cased,
    parsed as a mail header so an address in the display name is not taken
    for it; empty when there is not exactly one address."""
    pairs = [addr for _name, addr in getaddresses([one_line(value)]) if addr]
    if len(pairs) != 1 or "@" not in pairs[0]:
        return ""
    return pairs[0].strip().lower()


def advisory_archive(data: Mapping[str, Any]) -> dict[str, Any]:
    cve = one_line(data.get("cve_id")).strip()
    if not _CVE.match(cve):
        return {"ok": False, "refused": f"cve_id {cve!r} is not of the form CVE-YYYY-NNNN"}
    advisory_list = _list_address(data.get("advisory_list"))
    if "@" not in advisory_list:
        return {"ok": False, "refused": "advisory_list (the project's users_list) is not configured"}
    url = one_line(data.get("url")).strip()
    raw_thread = data.get("thread")
    thread: Mapping[str, Any] = raw_thread if isinstance(raw_thread, Mapping) else {}
    thread_list = _list_address(thread.get("list"))
    subject = one_line(thread.get("subject")).strip()
    sender = _sender_address(thread.get("from"))
    raw_senders = data.get("authorized_senders")
    authorized = {_sender_address(s) for s in raw_senders} if isinstance(raw_senders, list) else set()
    authorized.discard("")
    archive = one_line(data.get("mail_archive_url")).strip().rstrip("/")
    reasons: list[str] = []
    if not url.startswith("https://"):
        reasons.append("the URL is not an https archive URL")
    elif not archive:
        reasons.append("mail_archive_url is not configured, so the URL's archive cannot be checked")
    elif not (url == archive or url.startswith(archive + "/")):
        reasons.append(f"the URL is not under the configured archive {archive}")
    if not authorized:
        reasons.append("no authorized_senders (release managers / security team) were given")
    elif not sender:
        reasons.append("the archive did not report who sent the root message; fetch the thread first")
    elif sender not in authorized:
        reasons.append(
            f"the root message is from {sender}, not from a release manager or security-team member"
        )
    if not thread_list:
        reasons.append("the archive did not report which list the thread is on; fetch the thread first")
    elif thread_list != advisory_list:
        reasons.append(f"the thread is on {thread_list}, not on the public advisory list {advisory_list}")
    pattern = re.compile(r"^(?:\[[^\]]*\]\s*)*" + re.escape(cve) + r"\s*:\s*\S", re.IGNORECASE)
    if not subject:
        reasons.append("the thread's root subject is unknown; fetch the thread first")
    elif not pattern.match(subject):
        reasons.append(f"the root subject is not the advisory subject `{cve}: <description>`")
    return {
        "ok": True,
        "accepted": not reasons,
        "reasons": reasons,
        "url": url,
        "list": thread_list or None,
        "subject": subject or None,
        "sender": sender or None,
        "requires_confirmation": True,
    }
