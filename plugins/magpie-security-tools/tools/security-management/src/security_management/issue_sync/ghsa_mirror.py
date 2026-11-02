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
"""Two-way comment sync between a GitHub repository security advisory and its tracker.

**Advisory → tracker.** Every advisory comment is copied into the tracker as
one tracker comment, keyed by a hidden marker
`<!-- magpie: ghsa-comment v1 <GHSA> <comment id> <updated_at> -->`: a comment
with no copy yet is created, a copy older than the comment's `updated_at` is
rewritten, a current copy is left alone. The copy quotes the body, names the
author in backticks (never an `@`-mention: the reporter is not on the tracker)
with their role, and links the comment. A comment the sync posted from a
tracker comment is not copied back: the original is already there.

**Tracker → advisory.** Only a comment by a member of the team (the tracker
collaborator roster) that the team marked for the reporter — a
`<!-- to-reporter -->` line, or a first line starting `To reporter:` — is
proposed for the advisory, with the marker or prefix removed and a hidden
`<!-- magpie: from-tracker <tracker comment id> -->` appended so the next run
recognises it. Each post is a confirmed write; a marked comment edited after
it was posted is proposed as an edit of the advisory comment. Nothing else on
the tracker ever leaves it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

COPY = re.compile(r"<!-- magpie: ghsa-comment v1 (?P<ghsa>GHSA-[0-9a-z-]+) (?P<id>\d+) (?P<updated>\S+) -->")
FROM_TRACKER = re.compile(r"<!-- magpie: from-tracker (?P<id>\d+) -->")
TO_REPORTER_MARKER = re.compile(r"^\s*<!--\s*to-reporter\s*-->\s*$", re.IGNORECASE | re.MULTILINE)
TO_REPORTER_PREFIX = re.compile(r"\A\s*to reporter:\s*", re.IGNORECASE)


def _login(comment: Mapping[str, Any]) -> str:
    return str((comment.get("user") or {}).get("login") or "")


def _role(login: str, reporter: str, team: set[str]) -> str:
    if login and login.lower() == reporter:
        return "reporter"
    return "team" if login.lower() in team else "other"


def _defang(text: str) -> str:
    """Quoted external text cannot forge one of the markers this module keys on."""
    return text.replace("<!--", "&lt;!--")


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in _defang(text).splitlines()) or ">"


def _for_reporter(body: str) -> str | None:
    """The reporter-facing text of a marked tracker comment, else None."""
    if TO_REPORTER_MARKER.search(body):
        text = TO_REPORTER_MARKER.sub("", body)
    elif TO_REPORTER_PREFIX.match(body):
        text = TO_REPORTER_PREFIX.sub("", body, count=1)
    else:
        return None
    text = text.strip()
    return text or None


def _strip_origin(body: str) -> str:
    return FROM_TRACKER.sub("", body).strip()


def copy_body(ghsa: str, comment: Mapping[str, Any], role: str) -> str:
    login = _login(comment) or "ghost"
    when = str(comment.get("created_at") or "")[:10]
    edited = comment.get("updated_at") and comment.get("updated_at") != comment.get("created_at")
    head = (
        f"**Advisory comment** by `{login}` ({role}) on {when}"
        f"{' (edited)' if edited else ''} — [view on {ghsa}]({comment.get('html_url')})"
    )
    marker = f"<!-- magpie: ghsa-comment v1 {ghsa} {comment.get('id')} {comment.get('updated_at') or comment.get('created_at')} -->"
    return f"{marker}\n{head}\n\n{_quote(str(comment.get('body') or ''))}\n"


def mirror(data: Mapping[str, Any]) -> dict[str, Any]:
    ghsa = str(data.get("ghsa_id") or "")
    advisory_comments = data.get("advisory_comments")
    tracker_comments = data.get("tracker_comments")
    if not re.fullmatch(r"GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}", ghsa):
        return {"ok": False, "refused": "ghsa_id must be a GHSA id"}
    if not isinstance(advisory_comments, Sequence) or not isinstance(tracker_comments, Sequence):
        return {
            "ok": False,
            "refused": "advisory_comments and tracker_comments must be the two comment lists",
        }
    reporter = str(data.get("reporter_login") or "").lower()
    team = {str(login).lower() for login in data.get("team_logins") or []}

    copies: dict[str, tuple[Mapping[str, Any], str]] = {}
    for tc in tracker_comments:
        for match in COPY.finditer(str(tc.get("body") or "")):
            if match["ghsa"] == ghsa and _login(tc).lower() in team | {""}:
                copies[match["id"]] = (tc, match["updated"])

    posted_from: dict[str, Mapping[str, Any]] = {}
    to_tracker: list[dict[str, Any]] = []
    for ac in sorted(
        advisory_comments, key=lambda c: (str(c.get("created_at") or ""), int(c.get("id") or 0))
    ):
        body = str(ac.get("body") or "")
        origin = FROM_TRACKER.search(body)
        login = _login(ac)
        if origin and login.lower() in team:
            posted_from[origin["id"]] = ac
            continue
        role = _role(login, reporter, team)
        updated = str(ac.get("updated_at") or ac.get("created_at") or "")
        existing = copies.get(str(ac.get("id")))
        if existing is None:
            to_tracker.append(
                {
                    "action": "create",
                    "advisory_comment_id": ac.get("id"),
                    "role": role,
                    "body": copy_body(ghsa, ac, role),
                }
            )
        elif existing[1] < updated:
            to_tracker.append(
                {
                    "action": "update",
                    "advisory_comment_id": ac.get("id"),
                    "tracker_comment_id": existing[0].get("id"),
                    "role": role,
                    "body": copy_body(ghsa, ac, role),
                }
            )

    to_advisory: list[dict[str, Any]] = []
    ignored_marked: list[dict[str, Any]] = []
    for tc in tracker_comments:
        body = str(tc.get("body") or "")
        if COPY.search(body):
            continue
        text = _for_reporter(body)
        if text is None:
            continue
        login = _login(tc)
        if login.lower() not in team:
            ignored_marked.append(
                {"tracker_comment_id": tc.get("id"), "author": login, "reason": "not on the team roster"}
            )
            continue
        outgoing = f"{text}\n\n<!-- magpie: from-tracker {tc.get('id')} -->"
        posted = posted_from.get(str(tc.get("id")))
        if posted is None:
            to_advisory.append(
                {"action": "create", "tracker_comment_id": tc.get("id"), "author": login, "body": outgoing}
            )
        elif _strip_origin(str(posted.get("body") or "")) != text:
            to_advisory.append(
                {
                    "action": "update",
                    "tracker_comment_id": tc.get("id"),
                    "advisory_comment_id": posted.get("id"),
                    "author": login,
                    "body": outgoing,
                    "editable_by": "the comment's author, or an admin / security manager",
                }
            )

    return {
        "ok": True,
        "ghsa_id": ghsa,
        "to_tracker": to_tracker,
        "to_advisory": to_advisory,
        "ignored_marked": ignored_marked,
        "in_sync": not to_tracker and not to_advisory,
        "requires_confirmation": bool(to_tracker or to_advisory),
        "advisory_visibility": "regular comments: the reporter and every advisory collaborator see them",
    }
