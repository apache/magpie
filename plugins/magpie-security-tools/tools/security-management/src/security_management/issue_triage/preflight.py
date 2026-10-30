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
"""Step 2 pre-flight skip: trackers whose newest comment is our own unanswered proposal.

A tracker is skipped only when all four signals of `gather.md` § *Pre-flight
skip* hold; any signal that fails or cannot be evaluated keeps it:

1. the newest comment carries both proposal markers;
2. its author is on the security-team roster / collaborator set;
3. the issue's `updatedAt` is at most 60 seconds after that comment;
4. when the *Security mailing list thread* field names a Gmail `threadId`,
   the thread's newest message is no later than that comment.

Rule 4 needs a mail read, so it runs in two passes: a tracker passing rules
1-3 with a thread and no `mail` entry yet comes back under `mail_checks`
(decision `pending`); the agent makes the one MINIMAL read per tracker and
runs the command again with `mail[<number>] = {"newest": <date>}` (or
`{"error": true}`). The field is read through github-body-field; a field it
will not decide on keeps the tracker.

`--retriage`, `--no-preflight` and an explicitly numbered selector disable
the skip; for explicit numbers the rule still runs, for the Step 5 note only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.shared import dispositions, fields, threads

SLACK_SECONDS = 60
RULE = "last comment is our unanswered triage proposal; no later update or reporter mail"


def flatten(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Issue nodes from `trackers` and/or raw GraphQL `responses`; aliases that came back `null`."""
    nodes: list[dict[str, Any]] = [dict(t) for t in data.get("trackers") or []]
    missing: list[str] = []
    for response in data.get("responses") or []:
        repo = ((response or {}).get("data") or {}).get("repository") or {}
        for alias, node in repo.items():
            if node is None:
                missing.append(alias.lstrip("i"))
            else:
                nodes.append(dict(node))
    return nodes, missing


def _comments(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    comments = node.get("comments") or []
    if isinstance(comments, Mapping):
        comments = comments.get("nodes") or []
    return list(comments)


def _login(comment: Mapping[str, Any]) -> str:
    author: Any = comment.get("author") or {}
    return str(author.get("login") if isinstance(author, Mapping) else author)


def evaluate(
    node: Mapping[str, Any],
    roster: set[str],
    mail: Mapping[str, Any] | None,
    body_fields: Mapping[str, str] | None,
) -> dict[str, Any]:
    """`{decision: skip|keep|pending, failed_rule, proposal_date, proposed_class, thread_id}` for one tracker."""
    out: dict[str, Any] = {
        "number": int(node["number"]),
        "decision": "keep",
        "failed_rule": None,
        "proposal_date": None,
        "proposed_class": None,
        "thread_id": None,
    }
    comments = _comments(node)
    dated = [(dispositions.parse_time(c.get("createdAt")), c) for c in comments]
    if not dated or any(t is None for t, _ in dated):
        out["failed_rule"] = 1
        return out
    created, newest = max(dated, key=lambda pair: pair[0])  # type: ignore[arg-type,return-value]
    proposed = dispositions.proposal_class(str(newest.get("body") or ""))
    if proposed is None:
        out["failed_rule"] = 1
        return out
    out["proposal_date"] = str(newest.get("createdAt"))
    out["proposed_class"] = proposed or None
    if _login(newest).lower() not in roster:
        out["failed_rule"] = 2
        return out
    updated = dispositions.parse_time(node.get("updatedAt"))
    if updated is None or created is None or (updated - created).total_seconds() > SLACK_SECONDS:
        out["failed_rule"] = 3
        return out
    read = fields.read(str(node.get("body") or ""), ["mailing_thread"], body_fields)
    if read["undecided"]:
        out["failed_rule"] = 4
        return out
    thread_id = threads.classify(read["values"].get("mailing_thread"))["thread_id"]
    out["thread_id"] = thread_id
    if thread_id:
        if mail is None:
            out["decision"] = "pending"
            return out
        newest_mail = dispositions.parse_time(mail.get("newest"))
        if mail.get("error") or newest_mail is None or newest_mail > created:
            out["failed_rule"] = 4
            return out
    out["decision"] = "skip"
    return out


def run(data: Mapping[str, Any]) -> dict[str, Any]:
    nodes, missing = flatten(data)
    roster = {str(r).lower().lstrip("@") for r in data.get("roster") or []}
    if not roster:
        raise ValueError("roster is empty: resolve the security-team roster at Step 0 first")
    mail: Mapping[str, Any] = data.get("mail") or {}
    disabled = (
        "--retriage"
        if data.get("retriage")
        else "--no-preflight"
        if data.get("no_preflight")
        else "explicit selector"
        if data.get("explicit")
        else None
    )
    kept: list[int] = []
    skipped: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []
    for node in nodes:
        verdict = evaluate(node, roster, mail.get(str(node["number"])), data.get("body_fields"))
        number = verdict["number"]
        if verdict["decision"] == "pending" and not disabled:
            checks.append({"number": number, "thread_id": verdict["thread_id"]})
            continue
        if verdict["decision"] == "skip" and not disabled:
            skipped.append(
                {
                    "number": number,
                    "proposal_date": verdict["proposal_date"],
                    "proposed_class": verdict["proposed_class"],
                    "rule": RULE,
                }
            )
            continue
        kept.append(number)
        if disabled == "explicit selector" and verdict["decision"] in ("skip", "pending"):
            notes.append({"number": number, "unanswered_proposal_since": verdict["proposal_date"]})
    return {
        "disabled": disabled,
        "kept": kept,
        "skipped": skipped,
        "mail_checks": checks,
        "explicit_notes": notes,
        "missing_numbers": missing,
        "all_skipped": bool(skipped) and not kept and not checks,
    }
