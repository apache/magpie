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
"""Steps 5b, 5e and 7: the closing comment, the rollup entry and the recap.

The closing comment is brief and process-shaped: it links the deciding
comment and the rollup, and says where the reporter reply is (never the
reasoning). The rollup entry carries at most 5 verbatim quotes, the canned
section, exactly one *Reporter notification* line (refused when no case
applies), the board state and the terminal next step, every line at column
0. The recap links every permalink and ends with the hand-off line.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import body, refs, rollup
from security_management.shared.rollup import code, one_line
from security_management.shell import dq

LABEL = "Closed as invalid"
MAX_QUOTES = 5
POLICY = (
    "[Reporter credit policy](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/"
    "issue-import-from-pr/SKILL.md#reporter-credit-policy-for-public-pr-imports)"
)
HANDOFF = (
    "> Terminal disposition. No further skill runs are expected on\n"
    "> `{tracker}#{number}`. If the team later changes its mind, re-open\n"
    "> the tracker manually and re-run the discussion at Step 5;\n"
    "> there is no `un-invalidate` skill (and there should not be —\n"
    "> reversing an invalid close is a deliberate team action that\n"
    "> deserves a fresh discussion)."
)
_COMMENT_ID = re.compile(r"(?:#issuecomment-)?(\d+)$")


def comment_id(value: object) -> str:
    match = _COMMENT_ID.search(one_line(value))
    if not match:
        raise ValueError(f"{value!r} is not a comment URL or id")
    return match.group(1)


def _where(backend: object) -> str:
    return "the Maildir drafts" if str(backend or "") == "maildir" else "Gmail"


def close_comment(data: Mapping[str, Any]) -> dict[str, Any]:
    decided = comment_id(data["decision_comment"])
    rollup_id = comment_id(data["rollup_comment"])
    case = str(data.get("notification_case") or "")
    first = f"Closing as `invalid` per team consensus in [this discussion](#issuecomment-{decided})."
    summary = f"Reasoning summary in the [status rollup](#issuecomment-{rollup_id})"
    if case.startswith(("direct", "via_forwarder", "ghsa_forwarder")):
        who = "the reporter" if case.startswith("direct") else "the forwarder"
        second = f"{summary}; a draft reply to {who} is in {_where(data.get('backend'))} awaiting review."
    elif case == "pr_imported":
        second = f"{summary}; no reporter notification (PR-imported tracker — see the import-from-pr skill's {POLICY})."
    elif case == "ghsa_comment":
        second = f"{summary}; the closure is communicated on the GHSA advisory."
    elif case == "internal_audit":
        second = f"{summary}; no reporter notification (internal audit finding)."
    else:
        second = f"{summary}."
    return {"ok": True, "text": f"{first}\n\n{second}\n"}


def _anchor(heading: str) -> str:
    slug = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return slug.replace(" ", "-")


def _notification(n: Mapping[str, Any], upstream: str) -> str | None:
    case = str(n.get("case") or "")
    draft = code(n.get("draft_id") or "<pending>")
    thread = code(n.get("thread_id"))
    contact = code(n.get("forwarder_contact"))
    ghsa = code(n.get("ghsa_id") or "GHSA-XXXX-XXXX-XXXX")
    kind = "Maildir draft" if str(n.get("backend") or "") == "maildir" else "Gmail draft"
    lines = {
        "direct": (
            f"{kind} {draft} created on thread {thread} anchored at message {code(n.get('message_id'))} — "
            "awaiting user review."
        ),
        "via_forwarder": (
            f"Forwarder-relay draft {draft} to {contact} on thread {thread} per the matching adapter's "
            "`reporter_addressing_block` convention (clickable URL + paste-ready reporter-voice block) — "
            "awaiting user review."
        ),
        "internal_audit": (
            "No reporter notification owed — internal audit finding, no inbound `security@` thread"
            f" (imported from {code(n.get('source_markdown') or 'a project-internal markdown audit')})."
        ),
        "ghsa_comment": (
            f"GHSA-relay-only reporter channel ({ghsa}) — closure communicated as GHSA comment "
            f"{one_line(n.get('ghsa_comment_url') or '<URL>')} / advisory state set to "
            f"`{one_line(n.get('ghsa_state') or 'withdrawn')}`; no Gmail reply needed."
        ),
        "ghsa_forwarder": (
            f"GHSA-relay-only reporter channel ({ghsa}); operator lacks GHSA-write access on `{upstream}`. "
            f"Forwarder-relay draft {draft} queued to {contact} requesting they post the closure comment on "
            "the GHSA on our behalf — awaiting user review."
        ),
        "pr_imported": f"none (no reporter; per {POLICY}).",
        "indeterminate": "none (flag from Step 2 surfaced; user explicitly chose silent close).",
        "silent": f"none — `silent` close chosen: {one_line(n.get('reason') or 'reporter unreachable')}.",
    }
    base = case.removesuffix("_duplicate")
    if base not in lines or (case.endswith("_duplicate") and base not in ("direct", "via_forwarder")):
        return None
    line = lines[base]
    if case.endswith("_duplicate"):
        line += f" The draft names the canonical {code(n.get('canonical_cve') or '<CVE-ID>')}."
    return line


def rollup_entry(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    note = _notification(data.get("notification") or {}, str(data.get("upstream") or "<upstream>"))
    if note is None:
        return {
            "ok": False,
            "refused": "no Reporter notification case applies: surface it as a blocker before closing",
        }
    quotes: Sequence[Mapping[str, Any]] = data.get("quotes") or []
    if not quotes:
        return {
            "ok": False,
            "refused": "no reasoning quote: mine the discussion (Step 3) or record the user's reason",
        }
    canned = one_line(data.get("canned_section"))
    if not canned:
        return {"ok": False, "refused": "the canned response selected in Step 4 is required"}
    branch = one_line(data.get("tracker_default_branch") or "main")
    config = one_line(data.get("project_config") or ".apache-magpie-overrides").strip("/")
    canned_url = f"https://github.com/{tracker}/blob/{branch}/{config}/canned-responses.md#{_anchor(canned)}"
    lines = [
        f"**Closed as `invalid` on {one_line(data['date'])}** (decided in "
        f"[comment](#issuecomment-{comment_id(data['decision_comment'])})).",
        "",
        "**Reasoning** (verbatim from the team's discussion, capped at ~5 quotes):",
        "",
    ]
    for quote in quotes[:MAX_QUOTES]:
        text = body.short_field(one_line(quote["quote"]))
        lines.append(
            f"- @{one_line(quote['author']).lstrip('@')}: > {text} "
            f"([source](#issuecomment-{comment_id(quote['comment'])}))"
        )
    board = data.get("board") or {}
    board_line = (
        f"archived (item {code(board['item_id'])})."
        if board.get("archived") and board.get("item_id")
        else "not on the board (already removed or never added) — nothing archived."
    )
    lines += [
        "",
        f"**Canned response selected:** *{canned}* in [`canned-responses.md`]({canned_url}).",
        "",
        f"**Reporter notification:** {note}",
        "",
        f"**Project board:** {board_line}",
        "",
        "**Next:** none — terminal disposition.",
    ]
    text = rollup.column_zero(refs.linkify("\n".join(lines), tracker)) + "\n"
    notification = data.get("notification") or {}
    return {
        "ok": True,
        "label": LABEL,
        "label_shell": dq(LABEL),
        "text": text,
        "quotes_dropped": max(0, len(quotes) - MAX_QUOTES),
        "needs_amend": "<pending>" in text
        and bool(notification.get("case", "").startswith(("direct", "via", "ghsa_f"))),
        "bare_refs": refs.bare_refs(text),
    }


def recap(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    lines: list[str] = []
    for item in data.get("closed") or []:
        number = int(item["number"])
        board = item.get("board") or {}
        draft = item.get("draft") or {}
        lines += [
            f"**Closed as invalid:** {refs.tracker_link(tracker, number)} — new state `closed - not planned`.",
            f"- Labels: added {', '.join(code(x) for x in item.get('labels_added') or ['invalid'])}; "
            f"removed {', '.join(code(x) for x in item.get('labels_removed') or []) or 'none'}.",
            f"- Rollup entry: [permalink]({one_line(item['rollup_url'])})",
            f"- Closing comment: [permalink]({one_line(item['close_url'])})",
            "- Project board: "
            + (f"archived (item {code(board['item_id'])})" if board.get("archived") else "not on board"),
            "- Reporter draft: "
            + (
                f"{code(draft['id'])}" + (f" — {one_line(draft['url'])}" if draft.get("url") else "")
                if draft.get("id")
                else f"none — {one_line(draft.get('reason') or 'no draft owed')}"
            ),
            "",
            HANDOFF.format(tracker=tracker, number=number),
            "",
        ]
    for item in data.get("awaiting") or []:
        lines.append(f"- {refs.tracker_link(tracker, item['number'])}: awaiting consensus — skipped.")
    failed = data.get("failed")
    if failed:
        lines += [
            "",
            f"**Stopped at** {refs.tracker_link(tracker, failed['number'])}, sub-step {one_line(failed.get('substep'))}: "
            f"{one_line(failed.get('error'))}.",
        ]
        remaining = [int(n) for n in data.get("remaining") or []]
        if remaining:
            lines.append(f"Not started: {', '.join(refs.tracker_link(tracker, n) for n in remaining)}.")
    text = "\n".join(lines).rstrip("\n") + "\n"
    return {"text": text, "bare_refs": refs.bare_refs(text)}
