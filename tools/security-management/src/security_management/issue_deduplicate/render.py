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
"""Steps 4, 5 and 6: the two rollup entries, the numbered proposal and the recap.

The entries are the bodies `rollup-append` wraps under `Merge (kept) (from
<drop>)` and `Merge (dropped) (into <keep>)`: every line at column 0, every
cross-tracker reference a link, both credits and both threads on the kept
side, the *Second independent report* pointer and the hand-off to the kept
tracker on the dropped side, and the *Reporter notification* line of
`shared.rollup`. The headline and the analysis are the model's; everything
around them is fixed.

The proposal numbers the items: 1 the merged body, 2 and 3 the rollup
entries, 4 the `duplicate` label, 5 the close, 6 the CVE JSON (and its
`push_update` when the kept tracker has a CVE), 7 the retraction of the
dropped side's CVE, only when both had one.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.cve_allocate.gate import record_url
from security_management.issue_deduplicate.gate import DUPLICATE
from security_management.shared import refs, rollup
from security_management.shared.rollup import code, one_line
from security_management.shell import dq

CANONICAL = (1, 2, 3, 4, 5, 6, 7)


def _ref(data: Mapping[str, Any], side: str) -> str:
    entry = data[side]
    return refs.tracker_link(
        str(data["tracker"]), entry["number"], entry.get("url"), str(data.get("platform") or "github")
    )


def _id(value: object) -> str:
    text = str(value)
    return f"#{text}" if text.isdigit() else text


def labels(data: Mapping[str, Any]) -> tuple[str, str]:
    keep, drop = _id(data["keep"]["number"]), _id(data["drop"]["number"])
    return f"Merge (kept) (from {drop})", f"Merge (dropped) (into {keep})"


def _lines(value: object) -> list[str]:
    return [one_line(line) for line in str(value or "").split("\n") if line.strip()]


def _cve_line(data: Mapping[str, Any]) -> str:
    cve_id = one_line(data.get("cve_id"))
    drop = _ref(data, "drop")
    if not cve_id:
        return f"- CVE: none allocated yet; {drop} is being closed as duplicate."
    url = record_url(str(data["record_url_template"]), cve_id)
    line = f"- CVE: [`{cve_id}`]({url}) stays allocated here; {drop} is being closed as duplicate."
    retract = one_line(data.get("retract_cve"))
    if retract:
        line += f" Its own {code(retract)} is retracted at the CVE tool."
    return line


def rollup_kept(data: Mapping[str, Any]) -> dict[str, Any]:
    headline = one_line(data.get("headline"))
    if not headline:
        return {"ok": False, "refused": "the one-sentence headline is required"}
    keep_credits = _lines(data["keep"].get("credit"))
    drop_credits = _lines(data["drop"].get("credit"))
    if not keep_credits or not drop_credits:
        return {"ok": False, "refused": "both reporters' credit lines are required, verbatim"}
    try:
        note = rollup.notification_line(data.get("notification") or {"case": "omitted"})
    except ValueError as exc:
        return {"ok": False, "refused": str(exc)}
    credits = " + ".join(f"**{c}**" for c in [*keep_credits, *drop_credits])
    lines = [
        f"**Merged {_ref(data, 'drop')} into this tracker.** {headline}",
        "",
        f"- Body: {keep_credits[0]}'s original report preserved; {drop_credits[0]}'s report appended as "
        '*"Second independent report"*.',
        f"- Credits: {credits}.",
        "- Mailing threads: both listed — "
        + "; ".join(
            code(t) for t in [*_lines(data["keep"].get("thread")), *_lines(data["drop"].get("thread"))]
        )
        + ".",
        _cve_line(data),
        "",
        f"**Next:** {one_line(data.get('next_step') or 'confirm the credit preferences of both reporters, then continue the CVE work here.')}",
    ]
    if note:
        lines += ["", note]
    analysis = one_line(data.get("analysis"))
    if analysis:
        lines += ["", analysis]
    details = [
        f"- *{one_line(f['field'])}*: {one_line(f['change'])}." for f in data.get("field_changes") or []
    ]
    blockers = [f"- BLOCKER: {one_line(b)}" for b in data.get("blockers") or []]
    if details or blockers:
        lines += ["", "Per-field hand-off:", "", *details, *blockers]
    if data.get("cve_json_url"):
        lines += ["", f"CVE JSON attachment regenerated: {one_line(data['cve_json_url'])}."]
    return _entry(data, labels(data)[0], lines)


def rollup_dropped(data: Mapping[str, Any]) -> dict[str, Any]:
    headline = one_line(data.get("headline"))
    if not headline:
        return {"ok": False, "refused": "the one-sentence headline is required"}
    try:
        note = rollup.notification_line(data.get("notification") or {"case": "omitted"})
    except ValueError as exc:
        return {"ok": False, "refused": str(exc)}
    keep = _ref(data, "keep")
    drop_credit = (_lines(data["drop"].get("credit")) or ["the reporter"])[0]
    keep_credit = (_lines(data["keep"].get("credit")) or ["the original reporter"])[0]
    lines = [
        f"**Closing as duplicate of {keep}.** {headline}",
        "",
        f'Full content merged into {keep} as *"Second independent report"*; {drop_credit} credited alongside '
        f"{keep_credit} there.",
        "",
        f"**Next:** all triage and advisory work continues on {keep}.",
    ]
    analysis = one_line(data.get("analysis"))
    if analysis:
        lines += ["", analysis]
    artifacts = one_line(data.get("artifacts"))
    if artifacts:
        lines += ["", f"Specific artifacts merged: {artifacts}."]
    lines += ["", f"See the merge entry in the status rollup of {keep} for the full hand-off record."]
    if note:
        lines += ["", note]
    return _entry(data, labels(data)[1], lines)


def _entry(data: Mapping[str, Any], label: str, lines: list[str]) -> dict[str, Any]:
    error = rollup.label_error(label)
    if error:
        return {"ok": False, "refused": error}
    text = rollup.column_zero(refs.linkify("\n".join(lines), str(data["tracker"]))) + "\n"
    return {
        "ok": True,
        "label": label,
        "label_shell": dq(label),
        "text": text,
        "needs_amend": "`<pending>`" in text,
        "bare_refs": refs.bare_refs(text),
    }


def proposal(data: Mapping[str, Any]) -> dict[str, Any]:
    keep, drop = _ref(data, "keep"), _ref(data, "drop")
    duplicate = str(data.get("duplicate_label") or DUPLICATE)
    cve_id = one_line(data.get("cve_id"))
    items = [
        {
            "n": 1,
            "key": "body",
            "text": f"Update the body of {keep} with the merged body (shown in full below)",
        },
        {
            "n": 2,
            "key": "rollup_kept",
            "text": f"Append the `Merge (kept)` entry to the status rollup of {keep}",
        },
        {
            "n": 3,
            "key": "rollup_dropped",
            "text": f"Append the `Merge (dropped)` entry to the status rollup of {drop}",
        },
        {"n": 4, "key": "label", "text": f"Add the `{duplicate}` label to {drop}"},
        {"n": 5, "key": "close", "text": f"Close {drop} as not planned"},
        {
            "n": 6,
            "key": "cve_json",
            "text": f"Regenerate the CVE JSON of {keep}"
            + (
                f" and push the merged credits and references to {code(cve_id)} (`push_update`, no state change)"
                if cve_id
                else ""
            ),
        },
    ]
    retract = one_line(data.get("retract_cve"))
    if retract:
        items.append(
            {
                "n": 7,
                "key": "retract",
                "text": f"Retract {code(retract)} at the CVE tool (governance-gated), merged into {code(cve_id)}",
            }
        )
    blockers = [one_line(b) for b in data.get("blockers") or []]
    text = "\n".join(f"{i['n']}. {i['text']}" for i in items)
    if blockers:
        text += "\n\n" + "\n".join(f"**Blocker:** {b}" for b in blockers)
    text = refs.linkify(text, str(data["tracker"]))
    return {
        "ok": True,
        "items": items,
        "blocked": bool(blockers),
        "text": text + "\n",
        "bare_refs": refs.bare_refs(text),
    }


def recap(data: Mapping[str, Any]) -> dict[str, Any]:
    applied = {int(n) for n in data.get("applied") or []}
    keep, drop = _ref(data, "keep"), _ref(data, "drop")
    credits = ", ".join(_lines(data.get("credits"))) or "both reporters"
    lines = [
        f"**Kept:** {keep} — "
        + (
            "merged body with " + credits + " credited and both mailing threads"
            if 1 in applied
            else "body not updated"
        ),
        f"**Dropped:** {drop} — "
        + (
            "closed as not planned, labelled `duplicate`"
            if {4, 5} <= applied
            else "still open: finish items 4 and 5"
        ),
    ]
    if 6 in applied:
        url = one_line(data.get("cve_json_url"))
        lines.append(f"- CVE JSON: {url or 'regenerated'}")
    if 7 in applied:
        lines.append(f"- Retracted: {code(data.get('retract_cve'))}")
    failed = data.get("failed")
    if failed:
        lines.append(f"- **Stopped at item {int(failed['item'])}:** {one_line(failed.get('error'))}.")
    blockers = [one_line(b) for b in data.get("blockers") or []]
    if blockers:
        lines += ["", "**Still to resolve:**", *[f"- {b}" for b in blockers]]
    text = refs.linkify("\n".join(lines), str(data["tracker"])) + "\n"
    return {"text": text, "blockers": blockers, "bare_refs": refs.bare_refs(text)}
