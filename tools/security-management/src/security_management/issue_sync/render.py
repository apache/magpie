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
"""The Guardrails check over everything the proposal would write, and the Step 6 recap.

`check` reads each tracker- or reporter-bound passage the proposal carries
(`surfaces`: `{kind, text}` with `kind` one of `body_patch`,
`status_comment`, `rollup`, `issue_body`, `email`; `observed` is the one
place a reporter score may appear) and reports, one per passage and
guardrail, in passage order, content guardrails before formatting ones:

- *Never propagate a reporter-supplied CVSS score* — a CVSS score, vector
  or a score with a qualitative label outside `observed`;
- *Never name or describe other ASF projects' vulnerabilities* — another
  ASF project's name, or a cross-project phrase;
- *Linking CVEs* — a bare CVE ID on a markdown surface; in a reporter
  email the bare ID is right and the CVE-tool URL is the violation;
- *Linking tracker issues* — a bare `#NNN`.

The model still reads the surfaces for what a pattern cannot see; this is
the floor, not the whole check.

`recap` links the tracker, the rollup comment, the embedded CVE JSON (or
says no CVE is allocated), the milestone, the draft and its thread, and
repeats the next step.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.cve_allocate.gate import record_url
from security_management.shared import drafting, refs
from security_management.shared.rollup import code, one_line

CVSS = "Never propagate a reporter-supplied CVSS score"
OTHER_ASF = "Never name or describe other ASF projects' vulnerabilities"
LINK_CVE = "Linking CVEs"
LINK_TRACKER = "Linking tracker issues"
MARKDOWN = ("body_patch", "status_comment", "rollup", "issue_body")
_CVSS = re.compile(
    r"\bCVSS\b|\bAV:[NALP](?:/[A-Za-z]{1,3}:[A-Za-z])+|\b\d{1,2}\.\d[ \t]?\(?(?:low|medium|high|critical)\b",
    re.IGNORECASE,
)
_CVE = re.compile(r"CVE-\d{4}-\d{4,7}")
_CROSS = re.compile(
    r"also reported against|cross-project|other apache projects|sister project|the same finder also",
    re.IGNORECASE,
)


# The CVE-tool host as a URL host, not a substring check: this scans text, it sanitises nothing.
def _cve_tool_pattern(cve_tool_url: object = None) -> re.Pattern[str] | None:
    host = drafting.cve_tool_host(cve_tool_url)
    if host in drafting.PUBLIC_CVE_HOSTS:
        return None
    return re.compile(r"(?:https?://)?(?<![\w.-])" + re.escape(host) + r"(?![\w-])", re.IGNORECASE)


_BREAK = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    """`text` as sentences: a break is `.`, `!` or `?` then whitespace, so a URL stays whole."""
    joined = re.sub(r"\s*\n\s*", " ", text.strip())
    return [s.strip() for s in _BREAK.split(joined) if s.strip()]


def _bare_cves(sentence: str) -> list[str]:
    linked = {m.group(1) for m in re.finditer(r"\[`?(CVE-\d{4}-\d{4,7})`?\]\(", sentence)}
    in_urls = {c for url in re.findall(r"https?://\S+", sentence) for c in _CVE.findall(url)}
    return [c for c in _CVE.findall(sentence) if c not in linked and c not in in_urls]


def check(data: Mapping[str, Any]) -> dict[str, Any]:
    own = {str(n).lower() for n in data.get("own_names") or []}
    is_asf = str(data.get("organization") or "ASF").strip().upper() == "ASF"  # unset fails closed
    names = [n for n in drafting.ASF_PROJECTS if n.lower() not in own] if is_asf else []
    other = re.compile(r"\b(?:Apache\s+)?(?:" + "|".join(names) + r")\b") if names else None
    cve_tool = _cve_tool_pattern(data.get("cve_tool_url"))
    violations: list[dict[str, str]] = []
    for surface in data.get("surfaces") or []:
        kind = str(surface.get("kind") or "")
        if kind == "observed":
            continue
        for sentence in _sentences(str(surface.get("text") or "")):
            found: list[str] = []
            if _CVSS.search(sentence):
                found.append(CVSS)
            if (other is not None and other.search(sentence)) or _CROSS.search(sentence):
                found.append(OTHER_ASF)
            if kind == "email":
                if cve_tool is not None and cve_tool.search(sentence):
                    found.append(LINK_CVE)
            elif kind in MARKDOWN:
                if _bare_cves(sentence):
                    found.append(LINK_CVE)
                if refs.bare_refs(sentence):
                    found.append(LINK_TRACKER)
            violations.extend({"surface": kind, "guardrail": g, "evidence": sentence} for g in found)
    return {"ok": True, "clean": not violations, "violations": violations}


def recap(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    issue = data["issue"]
    platform = str(data.get("platform") or "github")
    issue_url = one_line(data.get("issue_url")) or (
        f"https://github.com/{tracker}/issues/{int(issue)}" if platform == "github" else ""
    )
    lines = [
        f"**Sync complete on {refs.tracker_link(tracker, issue, data.get('issue_url'), platform)}.**",
        "",
    ]
    applied = [one_line(c) for c in data.get("applied") or []]
    skipped = [one_line(c) for c in data.get("skipped") or []]
    lines.append("- Changed: " + ("; ".join(applied) if applied else "nothing") + ".")
    if skipped:
        lines.append("- Skipped: " + "; ".join(skipped) + ".")
    comment = one_line(data.get("rollup_comment"))
    if comment:
        cid = re.search(r"(\d+)$", comment)
        anchor = f"#issuecomment-{cid.group(1)}" if cid else ""
        lines.append(
            f"- Status rollup: [entry]({issue_url}{anchor})" if issue_url else f"- Status rollup: `{anchor}`"
        )
    milestone = data.get("milestone") or {}
    if milestone.get("number"):
        url = f"https://github.com/{tracker}/milestone/{int(milestone['number'])}"
        lines.append(f"- Milestone: [{one_line(milestone.get('title'))}]({url})")
    else:
        lines.append("- Milestone: none set.")
    cve_id = one_line(data.get("cve_id"))
    if cve_id:
        link = record_url(str(data["record_url_template"]), cve_id)
        anchor = f"#cve-json--paste-ready-for-{cve_id.lower()}"
        json_link = f"[embedded CVE JSON]({issue_url}{anchor})" if issue_url else code(anchor)
        lines.append(f"- CVE: [`{cve_id}`]({link}); {json_link}.")
    else:
        lines.append("- CVE: none allocated yet, so the CVE JSON regeneration was skipped.")
        if data.get("allocate_url"):
            lines.append(f"- Allocate one at {one_line(data['allocate_url'])} (`security-cve-allocate`).")
    for draft in data.get("drafts") or []:
        thread = one_line(draft.get("thread_url"))
        where = f" on [the thread]({thread})" if thread else ""
        lines.append(
            f"- Draft {code(draft.get('id') or 'pending')} waiting in Gmail{where}: review and send it."
        )
    lines += ["", f"**Next:** {one_line(data.get('next_step'))}"]
    text = refs.linkify("\n".join(lines), tracker) + "\n"
    return {"text": text, "bare_refs": refs.bare_refs(text)}
