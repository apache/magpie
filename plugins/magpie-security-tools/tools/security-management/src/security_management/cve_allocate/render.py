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
"""Steps 4 and 7: the numbered proposal, the rollup entry and the recap.

The proposal is items 1-4 always (*CVE tool link* field, `cve allocated`
label, rollup entry, CVE JSON) and item 5 only when this run creates a
reporter draft; a draft already waiting on the thread is surfaced instead.
A tracker merging several independent reporters passes one plan per
reporter (`drafts`), and item 5 creates one draft per reporter thread.

The rollup entry is the body `rollup-append` wraps under the
`CVE allocated (<CVE-ID>)` label: every line at column 0, every tracker
reference a link, and one *Reporter notification* line per reporter (none for
`omitted`), each named by its thread when there are several. A draft id is claimed as pending only when the caller verified
it is still in Drafts; a draft created after the entry carries `<pending>`
and is amended in.

The recap links the tracker, the CVE record, the CVE JSON anchor and the
rollup comment, names the draft (or why there is none), and repeats the next
step.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.cve_allocate.gate import CVE_ALLOCATED, record_url
from security_management.shared import refs, rollup
from security_management.shared.rollup import code, one_line
from security_management.shared.selectors import CVE
from security_management.shell import dq

NEXT_STEP = "design the fix (`security-issue-fix` skill)."
_COMMENT_ID = re.compile(r"(?:#issuecomment-)?(\d+)$")


def label(cve_id: str) -> str:
    return f"CVE allocated ({cve_id})"


def _cve(data: Mapping[str, Any]) -> str:
    cve_id = one_line(data.get("cve_id")).upper()
    if not CVE.match(cve_id):
        raise ValueError(f"{cve_id!r} is not a CVE ID of the form CVE-YYYY-NNNNN")
    return cve_id


def _link(data: Mapping[str, Any]) -> str:
    return refs.tracker_link(
        str(data["tracker"]), data["issue"], data.get("issue_url"), str(data.get("platform") or "github")
    )


def _issue_url(data: Mapping[str, Any]) -> str | None:
    if data.get("issue_url"):
        return one_line(data["issue_url"])
    if str(data.get("platform") or "github") == "github":
        return f"https://github.com/{data['tracker']}/issues/{int(data['issue'])}"
    return None


def _plans(data: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """The per-reporter list (`drafts`, `notifications`), else the single value under ``key``."""
    many = data.get(key + "s")
    if many:
        return [p for p in many if p]
    one = data.get(key)
    return [one] if one else []


def proposal(data: Mapping[str, Any]) -> dict[str, Any]:
    cve_id = _cve(data)
    url = record_url(str(data["record_url_template"]), cve_id)
    allocated = str(data.get("cve_allocated_label") or CVE_ALLOCATED)
    folds = list(data.get("legacy_comments") or [])
    plans = _plans(data, "draft")
    items = [
        {"n": 1, "key": "cve_tool_link", "text": f"Set the *CVE tool link* body field to {url}"},
        {"n": 2, "key": "label", "text": f"Add the `{allocated}` label"},
        {
            "n": 3,
            "key": "rollup",
            "text": f"Append a `{label(cve_id)}` entry to the status rollup"
            + (f", after folding {len(folds)} legacy comment(s) into it, oldest first" if folds else ""),
        },
        {"n": 4, "key": "cve_json", "text": "Regenerate the CVE JSON attachment in the tracker body"},
    ]
    notes = []
    creates = [p for p in plans if p.get("action") == "create"]
    if len(creates) == 1:
        draft = creates[0]
        items.append(
            {
                "n": 5,
                "key": "draft",
                "text": f"Create a reporter status draft to {one_line(draft.get('to'))} "
                f"({one_line(draft.get('subject'))}) via {draft.get('backend')}",
            }
        )
    elif creates:
        # one draft per reporter, each on its own thread: never one email to all
        each = "; ".join(
            f"to {one_line(d.get('to'))} ({one_line(d.get('subject'))}) via {d.get('backend')}"
            for d in creates
        )
        items.append(
            {
                "n": 5,
                "key": "draft",
                "text": f"Create {len(creates)} reporter status drafts, one per reporter thread: {each}",
            }
        )
    for draft in plans:
        where = f" on thread {code(draft['thread_id'])}" if len(plans) > 1 and draft.get("thread_id") else ""
        if draft.get("action") == "surface_existing":
            notes.append(
                f"A draft already waits on the inbound thread{where} "
                f"({code(draft['notification']['draft_id'])}): no new draft is created."
            )
        elif draft.get("action") != "create" and draft.get("reason"):
            notes.append(f"No reporter draft{where}: {one_line(draft['reason'])}.")
    text = "\n".join(f"{item['n']}. {item['text']}" for item in items)
    if notes:
        text += "\n\n" + "\n".join(notes)
    return {
        "ok": True,
        "items": items,
        "proposal_items_count": len(items),
        "record_url": url,
        "cve_tool_link_value": url,
        "notes": notes,
        "text": text + "\n",
        "bare_refs": refs.bare_refs(text),
    }


def rollup_entry(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    try:
        cve_id = _cve(data)
        url = record_url(str(data["record_url_template"]), cve_id)
        given = _plans(data, "notification")
        notes = []
        for n in given:
            line = rollup.notification_line(n)
            if line and len(given) > 1 and n.get("thread_id"):
                # one line per reporter, named by the thread its draft answers
                line = f"Thread {code(n['thread_id'])}: {line}"
            if line:
                notes.append(line)
    except ValueError as exc:
        return {"ok": False, "refused": str(exc)}
    allocated = str(data.get("cve_allocated_label") or CVE_ALLOCATED)
    vulnogram = "vulnogram" in str(data.get("cve_tool") or "tools/cve-tool-vulnogram")
    source = one_line(data.get("source_tab_url_template"))
    push = "push it to the record via the adapter's `push_update` method"
    if vulnogram:
        push += f" (for Vulnogram: `vulnogram-api-record-update --cve-id {cve_id} --json-file <path>`)"
        if source:
            push += (
                f" or, as a fallback, paste it into the record's [`source` tab]({record_url(source, cve_id)})"
            )
    scope = one_line(data.get("scope_label"))
    product = one_line(data.get("product"))
    package = one_line(data.get("package_name"))
    lines = [
        f"**Sync {one_line(data['date'])} — CVE [`{cve_id}`]({url}) allocated for {_link(data)}.**",
        "",
        "- Body *CVE tool link* field now points at the configured CVE tool.",
        f"- Label `{allocated}` added.",
        f"- CVE JSON attachment embedded in the issue body — {push}.",
        "",
        f"**Next:** {one_line(data.get('next_step') or NEXT_STEP)}",
    ]
    if notes:
        lines += ["", *notes]
    allocated_via = f"Allocated via the project's CVE tool at {one_line(data.get('allocate_url') or 'the allocation form')}"
    if one_line(data.get("allocated_by")) == "api":
        allocated_via = "Allocated through the CVE tool's API"
    mapping = (
        f" Scope `{scope}` → product `{product}` → `packageName` `{package}`." if scope and product else ""
    )
    lines += [
        "",
        f"{allocated_via}; the CVE ID is now the canonical reference in every downstream artifact "
        f"(CVE JSON, advisory email, credit lines, cross-links).{mapping}",
    ]
    facts = [
        f"CWE {code(data['cwe'])}" if data.get("cwe") else None,
        f"severity {code(data['severity'])}" if data.get("severity") else None,
        f"affected {code(data['affected'])}" if data.get("affected") else None,
        f"{int(data['credits'])} credits" if data.get("credits") is not None else None,
        f"{int(data['references'])} references" if data.get("references") is not None else None,
    ]
    state = ", ".join(f for f in facts if f)
    lines += [
        "",
        "Paste-ready JSON was regenerated from the current body state"
        + (f" ({state})" if state else "")
        + " and embedded in the issue body; regenerate it after any body change to keep it in sync.",
    ]
    text = rollup.column_zero(refs.linkify("\n".join(lines), tracker)) + "\n"
    action = label(cve_id)
    error = rollup.label_error(action)
    if error:
        return {"ok": False, "refused": error}
    return {
        "ok": True,
        "label": action,
        "label_shell": dq(action),
        "text": text,
        "needs_amend": "`<pending>`" in text,
        "bare_refs": refs.bare_refs(text),
    }


def _comment_anchor(value: object) -> str:
    match = _COMMENT_ID.search(one_line(value))
    if not match:
        raise ValueError(f"{value!r} is not a comment URL or id")
    return f"#issuecomment-{match.group(1)}"


def recap(data: Mapping[str, Any]) -> dict[str, Any]:
    cve_id = _cve(data)
    applied = {int(n) for n in data.get("applied") or []}
    allocated = str(data.get("cve_allocated_label") or CVE_ALLOCATED)
    issue = _issue_url(data)
    url = record_url(str(data["record_url_template"]), cve_id)
    state = []
    if 1 in applied:
        state.append("*CVE tool link* set")
    if 2 in applied:
        state.append(f"label `{allocated}` added")
    lines = [
        f"**CVE allocated:** {_link(data)} — {', '.join(state) or 'no tracker change applied'}.",
        f"- CVE: [`{cve_id}`]({url})",
    ]
    if 4 in applied:
        anchor = f"#cve-json--paste-ready-for-{cve_id.lower()}"
        lines.append(
            f"- CVE JSON: [embedded in the body]({issue}{anchor})" if issue else f"- CVE JSON: `{anchor}`"
        )
    if 3 in applied and data.get("rollup_comment"):
        anchor = _comment_anchor(data["rollup_comment"])
        lines.append(
            f"- Status rollup: [entry]({issue}{anchor})" if issue else f"- Status rollup: `{anchor}`"
        )
    drafts = _plans(data, "draft") or [{}]
    for draft in drafts:
        label_ = "Reporter draft"
        if len(drafts) > 1 and draft.get("thread_id"):
            label_ += f" on thread {code(draft['thread_id'])}"
        if draft.get("id"):
            where = "the Maildir drafts folder" if draft.get("backend") == "maildir" else "Gmail"
            lines.append(f"- {label_}: {code(draft['id'])} — open {where} to review and send it.")
        else:
            lines.append(
                f"- {label_}: none — {one_line(draft.get('reason') or 'no reporter notification owed')}."
            )
    failed = data.get("failed")
    if failed:
        lines.append(f"- **Stopped at item {int(failed['item'])}:** {one_line(failed.get('error'))}.")
    lines.append(f"- **Next:** {one_line(data.get('next_step') or NEXT_STEP)}")
    text = "\n".join(lines) + "\n"
    return {"text": text, "bare_refs": refs.bare_refs(text)}
