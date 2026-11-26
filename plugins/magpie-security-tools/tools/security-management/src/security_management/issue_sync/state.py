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
  security-pages checklist and reminder markers in team comments (author
  association `OWNER` / `COLLABORATOR`, or a login in `collaborators`), and
  the advisory-records step, including the planner's exit code and, when
  the records are published through a pull request, that pull request's
  state. Records are first written when the advisory is announced, so once
  cve.org lists the CVE `PUBLISHED` the site's copy is checked once more
  against the regenerated record (`recheck`) and refreshed only if it differs.
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
RECORDS_MERGED = "<!-- apache-magpie: advisory-records-merged v1 -->"
RECORDS_REFRESH = "<!-- apache-magpie: advisory-records-refresh v1 -->"
#: Posted once when the re-check found the site's record matching: it ends the
#: check, so the site is read once, not on every pass.
RECORDS_RECHECKED = "<!-- apache-magpie: advisory-records-recheck v1 -->"
#: What the caller found comparing the site's copy of the record with the
#: regenerated one, once cve.org lists the CVE (`site_recheck`).
RECHECK_RESULTS = frozenset({"unchanged", "differs", "failed"})
_PULL_URL = re.compile(r"https://[^\s<>()\[\]`]+/pull/\d+")
PR_STATES = frozenset({"OPEN", "MERGED", "CLOSED", "NONE"})
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


#: GitHub author associations that mean access to the tracker repository
#: itself. `MEMBER` is left out: it means membership of the organization,
#: not of the tracker's team; such a member counts through `collaborators`.
TEAM_ASSOCIATIONS = frozenset({"OWNER", "COLLABORATOR"})


def _login(author: Any) -> str:
    """A comment author's login: GitHub's `{login}` object, or the plain name other backends give."""
    if isinstance(author, Mapping):
        author = author.get("login")
    return str(author or "").strip().lstrip("@").casefold()


def _team_comments(data: Mapping[str, Any]) -> list[str]:
    """Bodies of the comments the tracker's team wrote.

    A comment counts when its author association (GraphQL
    `authorAssociation`, REST `author_association`) is `OWNER` or
    `COLLABORATOR`, or its author (`author`, REST `user`) is in
    `collaborators` (the tracker's collaborator list, which also covers
    access through a team and backends without associations). The
    local-files tracker's status rollup (`kind: rollup`), which only the
    tracker tool writes, counts too. Anything else does not.
    """
    comments = data.get("comments") or []
    if isinstance(comments, Mapping):
        comments = comments.get("nodes") or []
    team = {_login(login) for login in data.get("collaborators") or []} - {""}
    out: list[str] = []
    for c in comments:
        if not isinstance(c, Mapping):
            continue
        association = str(c.get("authorAssociation") or c.get("author_association") or "").upper()
        author = _login(c.get("author") or c.get("user"))
        if association in TEAM_ASSOCIATIONS or author in team or c.get("kind") == "rollup":
            out.append(str(c.get("body") or ""))
    return out


RECORD_EXITS = {
    0: "pending",
    4: "pending_checkout",
    3: "refused",
    2: "config_error",
}


def _records_pull_request(
    data: Mapping[str, Any], comments: list[str], state: str, out: dict[str, Any]
) -> str | None:
    """The advisory-records steps that come before the planner.

    Sets ``out["advisory_records"]`` when the marker comments or the
    pull-request lookup decide the step, leaves it unset when the planner
    decides it, and returns a refusal for input it cannot act on.

    In ``pull-request`` mode the `advisory-records v1` comment records the
    pull request it opened; the record is live only once that pull request
    merges, which a second marker comment (`advisory-records-merged v1`)
    records. Before the first comment, a pull request sync opened earlier
    without recording it (the comment failed, or another operator ran the
    commands) is found by its branch, so a second one is never proposed;
    the caller passes an open or merged one in preference to a closed one.
    """
    if any(t.lstrip().startswith(RECORDS_MERGED) for t in comments):
        out["advisory_records"] = "done"
        return None
    marker = next((t for t in comments if t.lstrip().startswith(RECORDS)), None)
    recorded = None
    if marker is not None:
        recorded = _PULL_URL.search(marker)
        if recorded is None:
            # Direct mode: the comment follows a successful commit (and push).
            out["advisory_records"] = "done"
            return None
        out["records_pr_url"] = recorded.group(0)
    elif state != "PUBLISHED" or one_line(data.get("advisory_records_publish")).lower() != "pull-request":
        # Not public yet, or published directly: the planner decides.
        return None
    if data.get("records_pr_lookup_failed"):
        out["advisory_records"] = "retry_pr_lookup"
        out["note"] = "advisory records: pull-request lookup failed — try again next sync"
        return None
    raw = one_line(data.get("records_pr_state")).upper()
    if not raw:
        out["advisory_records"] = "check_pr" if recorded else "find_pr"
        return None
    if raw not in PR_STATES:
        return f"records_pr_state {raw!r} is none of {', '.join(sorted(PR_STATES))}"
    if raw == "NONE":
        if recorded:
            return f"records_pr_state NONE, but the advisory-records comment names {recorded.group(0)}"
        return None
    out["records_pr_state"] = raw
    if not recorded:
        url = one_line(data.get("records_pr_url"))
        if not _PULL_URL.fullmatch(url):
            return f"records_pr_url {url!r} is not a pull-request URL"
        out["records_pr_url"] = url
    if raw == "CLOSED" and not recorded:
        # Only a closed one, and no status comment: the team removed the comment
        # to try again (or the pull request was closed before it was recorded).
        # The planner decides; the proposal names the closed one.
        out["records_pr_closed_url"] = out.pop("records_pr_url")
        del out["records_pr_state"]
        return None
    if raw == "CLOSED":
        out["advisory_records"] = "pr_closed"
        out["blockers"].append(
            f"advisory records: {out['records_pr_url']} was closed without merging; "
            "sync proposes nothing more for this CVE until the team decides how to record it"
        )
    elif not recorded:
        out["advisory_records"] = "record_pr"
    else:
        out["advisory_records"] = "pr_open" if raw == "OPEN" else "pr_merged"
    return None


def _records_recheck(data: Mapping[str, Any], comments: list[str], out: dict[str, Any]) -> str | None:
    """Once cve.org lists the CVE, compare the site's record with the regenerated one, once.

    The record went to the site when the advisory was announced; what cve.org
    publishes can still differ from it. A refresh is proposed only when the
    contents differ, and its status comment (`advisory-records-refresh v1`)
    ends the check; a matching record is recorded once with the
    `advisory-records-recheck v1` comment (`recheck_unchanged`), which ends it
    too. Returns a refusal for input it cannot act on.
    """
    if any(t.lstrip().startswith((RECORDS_REFRESH, RECORDS_RECHECKED)) for t in comments):
        return None
    raw = one_line(data.get("site_recheck")).lower()
    if not raw:
        out["advisory_records"] = "recheck"
        return None
    if raw not in RECHECK_RESULTS:
        return f"site_recheck {raw!r} is none of {', '.join(sorted(RECHECK_RESULTS))}"
    if raw == "failed":
        out["advisory_records"] = "retry_recheck"
        out["note"] = "advisory records: the site record could not be read — try again next sync"
    elif raw == "differs":
        out["advisory_records"] = "refresh"
    else:
        out["advisory_records"] = "recheck_unchanged"
        out["note"] = "advisory records: the site record matches the published record"
    return None


def closed_announced(data: Mapping[str, Any]) -> dict[str, Any]:
    # The state markers below are written in the team's comments, never in
    # the body or anyone else's comment: those carry report text, which must
    # not be able to satisfy them.
    comments = _team_comments(data)
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
        refused = _records_pull_request(data, comments, state, out)
        if refused:
            return {"ok": False, "refused": refused}
        if out.get("advisory_records") == "done" and state == "PUBLISHED":
            refused = _records_recheck(data, comments, out)
            if refused:
                return {"ok": False, "refused": refused}
        elif "advisory_records" in out:
            pass  # decided by a marker comment or the pull-request lookup
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
    elif data.get("security_pages_configured") is False:
        # No security page to update and no records to write: the
        # post-announcement step does not exist for this project, so
        # there is nothing to remind anyone about. Only an explicit
        # `false` counts; a caller that does not pass the flag keeps
        # the reminder.
        out["advisory_records"] = "not_configured"
        out["security_pages"] = "not_configured"
        out["security_pages_reminder_pending"] = False
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
