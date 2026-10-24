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
"""Steps 3, 4 and 6 of the findings-file import: body, rollup, proposal table, recap.

Every finding section becomes its own inert block (`shared.body.inert_block`),
and the rendered body must pass `shared.body.verify` or the render is refused. What stays
the model's: the duplicate judgement, the credit decision under the bot/AI
policy, and the confirmation reply.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import body, refs, reuse
from security_management.shared.rollup import code, column_zero, label_error, one_line
from security_management.shell import dq

TITLE_WIDTH = 50
SYNC = "https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-sync/SKILL.md"


class Refused(ValueError):
    """A render the skill must not emit."""


def _clean(name: str, text: object, escaped: dict[str, list[int]]) -> str:
    raw = "" if text is None else str(text).strip("\n")
    if not raw.strip():
        return body.NO_RESPONSE
    out = body.inert_block(raw)
    if not out["ok"]:
        raise Refused(f"section {name!r} is malformed ({out['indicator']}); it is not rendered")
    if out["escaped_lines"]:
        escaped[name] = list(out["escaped_lines"])
    return str(out["text"])


def _pr_url(url: object, upstream: str) -> str | None:
    text = one_line(url)
    pattern = rf"https://github\.com/{re.escape(upstream)}/pull/\d+/?"
    return text if re.fullmatch(pattern, text, re.IGNORECASE) else None


def render_body(data: Mapping[str, Any]) -> dict[str, Any]:
    finding = data["finding"]
    basename = one_line(data["basename"])
    k, n = int(data["k"]), int(data["n"])
    upstream = str(data["upstream"])
    security_list = one_line(data.get("security_list") or "security@")
    escaped: dict[str, list[int]] = {}
    try:
        details = _clean("Details", finding.get("details"), escaped)
        impact = _clean("Impact", finding.get("impact"), escaped)
        repro = _clean("Reproduction steps", finding.get("repro_steps"), escaped)
        fix = finding.get("recommended_fix")
        fix_text = _clean("Recommended fix", fix, escaped) if one_line(fix) else None
    except Refused as exc:
        return {"ok": False, "refused": str(exc)}
    note = (
        f"> **Imported from markdown file {code(basename)} (finding {k}/{n})** — there is no inbound "
        f"`{security_list}` report; the markdown sections below are the verbatim source."
    )
    description = "\n\n".join(
        [note, "**Details:**", details, "**Impact:**", impact, "**Reproduction steps:**", repro]
    )
    branch = finding.get("branch") or "unknown branch"
    fields = {
        "issue_description": description,
        "affected_versions": f"{code(finding['repository'])} @ {code(branch)} — versions to be confirmed during triage.",
        "mailing_thread": f"N/A — imported from markdown file {code(basename)}; no {security_list} thread.",
        "reporter_credit": data.get("reporter_credit"),
        "pr_with_fix": _pr_url(finding.get("location_url"), upstream),
        "cwe": finding.get("category"),
        "severity": finding.get("severity") or "UNKNOWN",
    }
    text = body.render(fields, data.get("body_fields"), callout=bool(data.get("callout")))
    if fix_text is not None:
        text += (
            "\n<details><summary>Recommended fix (per the source markdown)</summary>\n\n"
            f"{fix_text}\n</details>\n"
        )
    problem = body.verify(text, data.get("body_fields"))
    if problem is not None:
        return {"ok": False, "refused": f"{problem}; it is not rendered"}
    expected = list(body.headings(data.get("body_fields")).values())
    parsed = reuse.fields(text)
    credit = one_line(data.get("reporter_credit"))
    return {
        "ok": True,
        "text": text,
        "sanitised_fields": body.sanitised_fields(fields),
        "escaped_lines": escaped,
        "fields": parsed,
        "fields_ok": parsed == expected,
        "reporter_credit_is_bot": reuse.is_bot_credit(credit) if credit else False,
        "bare_refs": refs.bare_refs(text),
    }


def rollup(data: Mapping[str, Any], k: int, n: int) -> dict[str, Any]:
    basename = one_line(data["basename"])
    label = f"Import from markdown ({basename}, finding {k}/{n})"
    error = label_error(label)
    if error:
        return {"ok": False, "refused": error}
    finding = data["finding"]
    severity = finding.get("severity") or "UNKNOWN"
    location = one_line(finding.get("location_url")) or "none given"
    lines = [
        f"**Imported from markdown file {code(basename)} on {one_line(data['date'])}** "
        f"(severity: {code(severity)}, category: {code(finding.get('category') or 'none')}).",
        "",
        "This tracker was deliberately opened by the security team from a batch findings file. "
        + "The validity of the report has **not** been assessed yet — the tracker landed in the "
        "`Needs triage` column accordingly. Standard Step 3 discussion applies.",
        "",
        f"**Source:** {code(basename)} (finding `{k}` of `{n}` in the file).",
        f"**Location reference:** {code(location)}",
        f"**Severity (from source):** {code(severity)} (informational; CVSS scoring happens at allocation).",
        f"**Category (from source):** {code(finding.get('category') or 'none')} "
        "(informational; CWE assignment happens at allocation).",
    ]
    return {
        "ok": True,
        "label": label,
        "label_shell": dq(label),
        "text": column_zero("\n".join(lines)) + "\n",
    }


def _cell(value: object, width: int | None = None) -> str:
    text = one_line(value).replace("|", "\\|")
    if width and len(text) > width:
        text = text[: width - 1].rstrip() + "…"
    return text


def _issue_link(tracker: str, ref: object, platform: str = "github") -> str:
    if isinstance(ref, Mapping):
        return refs.tracker_link(tracker, ref.get("number", ref.get("id")), ref.get("url"), platform)
    return refs.tracker_link(tracker, ref, None, platform)


def proposal(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    findings: Sequence[Mapping[str, Any]] = data.get("findings") or []
    n = len(findings)
    lines = [
        f"{_cell(data['basename'])} — {n} findings parsed.",
        "",
        "| # | Severity | Category | Title | Possible duplicate |",
        "|---|----------|----------|-------|--------------------|",
    ]
    for f in findings:
        dups = f.get("duplicates") or []
        dup = ", ".join(_issue_link(tracker, d, platform) for d in dups) or "(none)"
        lines.append(
            f"| {int(f['index'])} | {_cell(f.get('severity'))} | {_cell(f.get('category'))} "
            f"| {_cell(f.get('title'), TITLE_WIDTH)} | {dup} |"
        )
    lines += [
        "",
        f"Default disposition: import all {n} as `Needs triage`.",
        "Reply with one of:",
        "  - `go` / `proceed` / `yes, all`     — import every finding above.",
        "  - `skip 4`                          — drop finding 4; import the rest.",
        "  - `skip 4,6`                        — drop multiple.",
        "  - `cancel` / `none`                 — bail; no trackers created.",
    ]
    text = "\n".join(lines) + "\n"
    return {"text": text, "total_findings": n, "bare_refs": refs.bare_refs(text)}


def recap(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    lines = [f"Imported from {code(data['basename'])}: {int(data['total_findings'])} findings parsed.", ""]
    lines += ["**Created**", ""]
    lines += [
        f"- {_issue_link(tracker, c, platform)} — finding {int(c['index'])}: {_cell(c.get('title'))}"
        for c in data.get("created") or []
    ] or ["- none"]
    skipped = data.get("skipped") or []
    if skipped:
        lines += ["", "**Skipped**", ""]
        lines += [
            f"- finding {int(s['index'])}: {_cell(s.get('title'))} — {_cell(s.get('reason') or 'user skip')}"
            for s in skipped
        ]
    failed = data.get("failed") or []
    if failed:
        lines += ["", "**Failed** (re-invoke for these indices once the cause is fixed)", ""]
        lines += [
            f"- finding {int(f['index'])}: {_cell(f.get('title'))} — {_cell(f.get('cause'))}" for f in failed
        ]
    lines += [
        "",
        "> Next: triage each new tracker per Step 3 of the handling process. "
        f"Run [`security-issue-sync`]({SYNC}) on each once the validity discussion progresses.",
    ]
    text = "\n".join(lines) + "\n"
    if platform == "github":
        text = refs.linkify(text, tracker)
    return {"text": text, "bare_refs": refs.bare_refs(text) if platform == "github" else []}
