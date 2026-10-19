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
"""Step 3: the kept tracker's body with the dropped tracker merged in.

The kept body is rewritten field by field with github-body-field's
`replace_field`, which refuses a rewrite that would change any other field,
so the CVE JSON attachment, a project's extra fields and every unchanged
value stay byte-exact.

- *The issue description*: the kept report as it is, then a *Second
  independent report* line (the drop tracker linked, the merge date, the
  model's one-sentence headline) over a collapsed `<details>` holding the
  model's analysis paragraph and the dropped report **verbatim**, except:
  reporter-supplied CVSS vectors, scores and severity labels are removed
  (`scores_removed`), a line that would end a field or carries a machine
  marker gains a leading `\\`, and an unmatched `</details>` is escaped so
  the disclosure cannot close early.
- *Reporter credited as*, *Security mailing list thread*, *PR with the fix*:
  both sides, one line each, never re-synthesised (threads earliest report
  first); a bot-shaped finder credit stays and is listed in `tool_credits`
  (the generator credits it as a tool), a bot-shaped *Remediation
  developer* from the dropped side is skipped (`skipped_credits`).
- *Short public summary*, *Affected versions*: the one populated side, or,
  when both are and differ, the model's merged value (`merged_summary`,
  `affected_versions`), which is required then.
- *CWE*: the one populated side; two different CWEs are a blocker unless
  the user picked one (`cwe`).
- *Severity*, *CVE tool link*, *Public advisory URL*: the kept side's, never
  the dropped side's.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from github_body_field import parser as gbf

from security_management.issue_deduplicate.gate import ROLES, _cwe_id
from security_management.shared import body, refs, reuse
from security_management.shared import fields as body_fields
from security_management.shared.rollup import one_line

REMOVED = "[reporter-supplied score removed]"
_VECTOR = re.compile(r"\bCVSS:[234]\.\d(?:/[A-Za-z]{1,3}:[A-Za-z])+|\bAV:[NALP](?:/[A-Za-z]{1,3}:[A-Za-z])+")
# Bounded gaps keep both patterns linear on reporter text (no adjacent open-ended runs).
_SCORE = re.compile(
    r"\bCVSS[^\n\d]{0,30}(?:[234](?:\.\d)?[^\n\d]{0,30})?\d{1,2}(?:\.\d)?"
    r"(?: ?\(?(?:none|low|medium|high|critical)\b\)?)?",
    re.IGNORECASE,
)
_SEVERITY = re.compile(
    r"^(?P<lead>[ \t>*_-]{0,20})severity(?:\*\*|__)?[ \t]{0,10}[:=][ \t]{0,10}(?:\*\*|__)?"
    r"(?:none|low|moderate|medium|high|critical|important)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_DETAILS_OPEN = re.compile(r"<details\b", re.IGNORECASE)
_DETAILS_CLOSE = re.compile(r"</details\s*>", re.IGNORECASE)


def strip_scores(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []

    def take(match: re.Match[str]) -> str:
        removed.append(match.group(0).strip())
        return match.group("lead") + REMOVED if "lead" in match.re.groupindex else REMOVED

    for pattern in (_SEVERITY, _VECTOR, _SCORE):
        text = pattern.sub(take, text)
    return text, removed


def _inert_lines(text: str) -> str:
    lines = text.split("\n")
    opens = 0
    for index, line in enumerate(lines):
        if gbf.loose_heading_name(line) is not None or line.lstrip(" \t").startswith("<!--"):
            line = "\\" + line
        opens += len(_DETAILS_OPEN.findall(line))
        closes = len(_DETAILS_CLOSE.findall(line))
        if closes > opens:
            line = _DETAILS_CLOSE.sub("&lt;/details>", line)
            closes = 0
        opens -= min(opens, closes)
        lines[index] = line
    return "\n".join(lines)


def _lines(value: str | None) -> list[str]:
    return [line for line in (value or "").split("\n") if line.strip()]


def _union(*values: str | None) -> str:
    out: list[str] = []
    for value in values:
        for line in _lines(value):
            if line.strip() not in (o.strip() for o in out):
                out.append(line)
    return "\n".join(out)


def _paragraph(text: object) -> str:
    return body.short_field(body.normalise(str(text or "").strip()))


def merge_body(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    config = data.get("body_fields")
    headings = body.headings(config)
    keep_body = body.normalise(str(data["keep"]["body"]))
    drop_body = body.normalise(str(data["drop"]["body"]))
    sides = {}
    for key, text in (("keep", keep_body), ("drop", drop_body)):
        read = body_fields.read(text, ROLES, config)
        if read["undecided"]:
            names = ", ".join(sorted({u["field"] for u in read["undecided"]}))
            return {
                "ok": False,
                "refused": f"the {key} body has fields github-body-field will not decide on ({names})",
            }
        sides[key] = read
    keep, drop = sides["keep"]["values"], sides["drop"]["values"]
    headline = one_line(data.get("headline"))
    analysis = str(data.get("analysis") or "").strip()
    if not headline or not analysis:
        return {
            "ok": False,
            "refused": "the merge needs the model's one-sentence headline and analysis paragraph",
        }
    if not keep["issue_description"]:
        return {"ok": False, "refused": "the kept body has no issue description to merge into"}
    blockers: list[str] = []
    new: dict[str, str] = {}

    drop_link = refs.tracker_link(tracker, data["drop"]["number"], data["drop"].get("url"), platform)
    reporter = body.escape_html(
        one_line(_lines(drop["reporter_credit"])[0] if drop["reporter_credit"] else "the second reporter")
    )
    report, removed = strip_scores(drop["issue_description"] or "_No description on the dropped tracker._")
    new["issue_description"] = (
        f"{keep['issue_description'].rstrip()}\n\n---\n\n"
        f"**Second independent report: {drop_link} — merged on {one_line(data['date'])}.** {body.short_field(headline)}\n\n"
        f"<details>\n<summary>Full report from {reporter} (click to expand)</summary>\n\n"
        f"{_paragraph(analysis)}\n\n{_inert_lines(report.rstrip())}\n\n</details>"
    )

    def either(role: str, merged_key: str, what: str) -> None:
        a, b = keep[role], drop[role]
        if b and not a:
            new[role] = body.short_field(b)
        elif a and b and a.strip() != b.strip():
            merged = str(data.get(merged_key) or "").strip()
            if not merged:
                raise ValueError(
                    f"both trackers have a different {what}: pass the merged value as {merged_key}"
                )
            new[role] = _paragraph(merged)

    try:
        either("public_summary", "merged_summary", "public summary")
        either("affected_versions", "affected_versions", "affected-versions value (widen it to cover both)")
    except ValueError as exc:
        return {"ok": False, "refused": str(exc)}

    created = (str(data["keep"].get("created") or ""), str(data["drop"].get("created") or ""))
    order = [keep["mailing_thread"], drop["mailing_thread"]]
    if created[0] and created[1] and created[1] < created[0]:
        order.reverse()
    threads = _union(*order)
    if threads != (keep["mailing_thread"] or "").strip():
        new["mailing_thread"] = threads

    tool_credits = [
        {"line": line, "tracker": side}
        for side, values in (("keep", keep), ("drop", drop))
        for line in _lines(values["reporter_credit"])
        if reuse.is_bot_credit(line)
    ]
    credits = _union(keep["reporter_credit"], drop["reporter_credit"])
    if credits != (keep["reporter_credit"] or "").strip():
        new["reporter_credit"] = credits
    prs = _union(keep["pr_with_fix"], drop["pr_with_fix"])
    if prs != (keep["pr_with_fix"] or "").strip():
        new["pr_with_fix"] = prs
    skipped = [line for line in _lines(drop["remediation_developer"]) if reuse.is_bot_credit(line)]
    developers = _union(
        keep["remediation_developer"],
        *[ln for ln in _lines(drop["remediation_developer"]) if ln not in skipped],
    )
    if developers != (keep["remediation_developer"] or "").strip():
        new["remediation_developer"] = developers

    a, b = keep["cwe"], drop["cwe"]
    choice = one_line(data.get("cwe"))
    if a and b and _cwe_id(a) != _cwe_id(b):
        if choice:
            if choice not in (a.strip(), b.strip()):
                return {"ok": False, "refused": f"cwe {choice!r} is neither tracker's CWE"}
            if choice != a.strip():
                new["cwe"] = choice
        else:
            blockers.append(
                f"CWE conflict: kept tracker has {a.strip()}, drop tracker has {b.strip()} — triager to resolve"
            )
    elif b and not a:
        new["cwe"] = body.short_field(b)

    severity_note = None
    if drop["severity"] and drop["severity"] not in ("Unknown", keep["severity"]):
        severity_note = (
            f"the drop tracker's severity {drop['severity']!r} is not carried over (independent scoring)"
        )

    text = keep_body
    changes = []
    for role, value in new.items():
        heading = headings[role]
        if role in sides["keep"]["absent"]:
            return {
                "ok": False,
                "refused": f"the kept body has no `### {heading}` field to write the merged value into",
            }
        if any(gbf.is_boundary(line) for line in value.split("\n")):
            return {"ok": False, "refused": f"the merged {heading} would hold a field heading"}
        try:
            text = gbf.replace_field(text, heading, value + "\n")
        except gbf.AmbiguousFieldError as exc:
            return {"ok": False, "refused": str(exc)}
        changes.append(role)
    result = gbf.normalise(text, list(headings.values()))
    if result.needs_decision:
        return {"ok": False, "refused": "the merged body has a field markdown readers could disagree on"}
    return {
        "ok": True,
        "text": text if text.endswith("\n") else text + "\n",
        "changed_fields": [headings[r] for r in changes],
        "blockers": blockers,
        "scores_removed": removed,
        "severity_note": severity_note,
        "tool_credits": tool_credits,
        "skipped_credits": skipped,
        "bare_refs": refs.bare_refs(new["issue_description"]),
    }
