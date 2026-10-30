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
"""Step 8: the recap, rendered from what Step 7 recorded.

The skipped list is exhaustive — user skips, canned rejections (naming the
canned response), public-fix rejections, already-tracked candidates (full
`owner/repo#NNN`, never a bare `#NNN`) — and every pre-filtered thread gets
its own line. Pre-filtered `cve-tool-bookkeeping` threads count toward the
bookkeeping total. A receipt covering several trackers from one thread is listed once, under the first
candidate it covers.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.shared import refs
from security_management.shared.rollup import one_line

NEXT_STEP = (
    "Step 2: the triager starts the validity discussion on the newly created tracker, "
    "tagging at least one other security-team member."
)
_FULL_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+#\d+$")


def _tracker_ref(tracker: str, existing: object, platform: str = "github") -> str:
    text = one_line(existing)
    if _FULL_REF.fullmatch(text):
        return text
    number = text.lstrip("#")
    if platform == "github" and number.isdigit():
        return f"{tracker}#{number}"
    return refs.tracker_link(tracker, text, None, platform)


def _created(tracker: str, entry: Mapping[str, Any], platform: str) -> dict[str, Any]:
    """`{number, url}` on GitHub, `{id, url}` on a backend that names its issues itself."""
    if platform == "github" and entry.get("number") is not None:
        number = int(entry["number"])
        return {
            "number": number,
            "url": str(entry.get("url") or f"https://github.com/{tracker}/issues/{number}"),
        }
    ident = one_line(entry.get("id") or entry.get("number"))
    return {"id": ident, "url": one_line(entry.get("url")) or None}


def _created_link(tracker: str, issue: Mapping[str, Any], platform: str) -> str:
    return refs.tracker_link(tracker, issue.get("number", issue.get("id")), issue.get("url"), platform)


def _reason(tracker: str, entry: Mapping[str, Any], platform: str = "github") -> str:
    kind = entry.get("kind")
    if kind == "user":
        return "user skipped"
    if kind == "canned":
        return f"rejected with canned response: {one_line(entry['canned_name'])}"
    if kind == "public-fix":
        return f"rejected with the fix-already-public reply: {', '.join(entry.get('pr_urls') or [])}"
    if kind == "tracked":
        return f"already tracked as {_tracker_ref(tracker, entry['existing'], platform)}"
    if kind == "answered":
        return f"already answered on-thread: {one_line(entry.get('note'))}"
    if kind == "other":
        return one_line(entry["reason"])
    raise ValueError(f"unknown skip kind {kind!r}")


def render(state: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(state["tracker"])
    platform = str(state.get("platform") or "github")
    issues = [_created(tracker, i, platform) for i in state.get("created") or []]
    seen: set[str] = set()
    drafts: list[dict[str, Any]] = []
    for draft in state.get("drafts") or []:
        draft_id = str(draft["draft_id"])
        if draft_id in seen:
            continue
        seen.add(draft_id)
        drafts.append({"draft_id": draft_id, "candidate": int(draft["candidate"])})
    skipped = [
        {"candidate": int(s["candidate"]), "reason": _reason(tracker, s, platform)}
        for s in state.get("skipped") or []
    ]
    prefiltered = list(state.get("prefiltered") or [])
    bookkeeping = int(state.get("bookkeeping_dropped") or 0) + sum(
        1 for p in prefiltered if p.get("class") == "cve-tool-bookkeeping"
    )
    notes = [one_line(n) for n in state.get("notes") or [] if one_line(n)]
    lines = ["**Created**", ""]
    lines += [f"- {_created_link(tracker, i, platform)}" for i in issues] or ["- none"]
    lines += ["", "**Drafts waiting for your review**", ""]
    lines += [f"- `{d['draft_id']}` (candidate {d['candidate']})" for d in drafts] or ["- none"]
    lines += ["", "**Not imported**", ""]
    lines += [f"- candidate {s['candidate']}: {s['reason']}" for s in skipped] or ["- none"]
    if prefiltered:
        lines += ["", "**Dropped by the Step 1 pre-filter**", ""]
        lines += [
            f"- `{one_line(p.get('thread_id'))}` — {one_line(p.get('subject'))} "
            f"({one_line(p.get('class'))}, rule {one_line(p.get('rule'))})"
            for p in prefiltered
        ]
    lines += ["", f"{bookkeeping} CVE-tool-bookkeeping emails dropped."]
    if notes:
        lines += ["", "**Notes**", ""] + [f"- {n}" for n in notes]
    lines += ["", f"**Next:** {NEXT_STEP}"]
    return {
        "issues_created": issues,
        "drafts_waiting": drafts,
        "skipped": skipped,
        "cve_tool_bookkeeping_dropped": bookkeeping,
        "next_step_reminder": True,
        "text": refs.linkify("\n".join(lines) + "\n", tracker)
        if platform == "github"
        else "\n".join(lines) + "\n",
    }
