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
"""Steps 3 to 8 of the public-PR import: milestone check, title, body, labels, rollup, duplicates, recap.

What stays the model's: choosing the milestone, paraphrasing a vague title,
the *Affected versions* value, and whether to override the credit or the
severity. The PR body, title and author are attacker-controlled and arrive
only in `--input` files.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import body, refs, reuse, titles
from security_management.shared.rollup import code, column_zero, label_error, one_line
from security_management.shell import dq

SHORT_TITLE = 25
DUP_LIMIT = 30
DEFAULT_LABELS = {"security_marker": "security issue", "pr_open": "pr created", "pr_merged": "pr merged"}
CVE_ALLOCATE = (
    "https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/cve-allocate/SKILL.md"
)
CREDIT_POLICY = (
    "https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-import-from-pr/"
    "SKILL.md#reporter-credit-policy-for-public-pr-imports"
)
BOT_POLICY = "https://github.com/apache/magpie/blob/main/tools/cve-tool-vulnogram/bot-credits-policy.md"


def _pr_link(upstream: str, number: int) -> str:
    return f"[{upstream}#{number}](https://github.com/{upstream}/pull/{number})"


def milestone_check(proposed: str, titles_: Sequence[object]) -> dict[str, Any]:
    """Exact match only: a near miss is reported, never substituted."""
    names = [str(t) for t in titles_]
    exists = proposed in names
    near = [] if exists else [n for n in names if n.strip().lower() == proposed.strip().lower()]
    return {
        "proposed": proposed,
        "exists": exists,
        "near_matches": near,
        "blocker": None
        if exists
        else f"milestone {proposed!r} does not exist on the tracker; creating it is a manual project-board action",
    }


def title(raw: str) -> dict[str, Any]:
    cleaned = titles.strip_pr_title(raw)
    return {"original": raw, "title": cleaned, "too_short": len(cleaned) < SHORT_TITLE}


def remediation(author: Mapping[str, Any]) -> tuple[str, bool]:
    """`(value, is_bot)`: the author's name, else login; `_No response_` for a bot."""
    name = one_line(author.get("name"))
    login = one_line(author.get("login"))
    is_bot = any(reuse.is_bot_credit(v) for v in (name, login) if v)
    if is_bot:
        return body.NO_RESPONSE, True
    return name or login, False


def render_body(data: Mapping[str, Any]) -> dict[str, Any]:
    upstream = str(data["upstream"])
    pr = data["pr"]
    number = int(pr["number"])
    url = f"https://github.com/{upstream}/pull/{number}"
    cleaned = body.inert_block(str(pr.get("body") or ""))
    if not cleaned["ok"]:
        return {
            "ok": False,
            "refused": f"the PR body is malformed ({cleaned['indicator']}); it is not rendered",
            "malformed_indicator": cleaned["indicator"],
        }
    pr_body = cleaned["text"]  # inert: references inside render as text, so they are not linked
    note = (
        f"> **Imported from public PR {_pr_link(upstream, number)}** — there is no inbound `security@` report; "
        "the PR description below is the public statement of the vulnerability."
    )
    developer, is_bot = remediation(pr.get("author") or {})
    fields = {
        "issue_description": f"{note}\n\n{pr_body}" if pr_body.strip() else note,
        "affected_versions": data.get("affected_versions"),
        "mailing_thread": f"N/A — opened from public PR {url}; no security@ thread",
        "reporter_credit": data.get("reporter_credit"),
        "pr_with_fix": url,
        "remediation_developer": developer,
        "severity": data.get("severity"),
    }
    text = body.render(fields, data.get("body_fields"), callout=bool(data.get("callout")))
    problem = body.verify(text, data.get("body_fields"))
    if problem is not None:
        return {"ok": False, "refused": f"{problem}; it is not rendered", "malformed_indicator": None}
    expected = list(body.headings(data.get("body_fields")).values())
    parsed = reuse.fields(text)
    return {
        "ok": True,
        "text": text,
        "sanitised": True,
        "sanitised_fields": body.sanitised_fields(fields),
        "escaped_lines": cleaned["escaped_lines"],
        "fields": parsed,
        "fields_ok": parsed == expected,
        "remediation_developer": developer,
        "remediation_developer_is_bot": is_bot,
        "bare_refs": refs.bare_refs(text),
    }


def labels(scope: str | None, state: str, configured: Mapping[str, Any] | None) -> dict[str, Any]:
    """Scope (when there is one), PR-state and security-marker labels; never `needs_triage`."""
    names = {**DEFAULT_LABELS, **{k: str(v) for k, v in (configured or {}).items()}}
    state = state.upper()
    out = [str(scope)] if scope else []
    warnings: list[str] = []
    if state == "OPEN":
        out.append(names["pr_open"])
    elif state == "MERGED":
        out.append(names["pr_merged"])
    else:
        warnings.append(
            f"PR state {state}: no PR-state label; confirm a tracker for an abandoned fix is wanted"
        )
    out.append(names["security_marker"])
    return {"labels": out, "warnings": warnings}


def rollup(data: Mapping[str, Any]) -> dict[str, Any]:
    upstream = str(data["upstream"])
    number = int(data["pr_number"])
    scope = one_line(data.get("scope")) or "no scope"
    label = f"Import from PR ({scope}, {upstream}#{number})"
    error = label_error(label)
    if error:
        return {"ok": False, "refused": error}
    url = f"https://github.com/{upstream}/pull/{number}"
    developer = one_line(data.get("remediation_developer"))
    if data.get("remediation_developer_is_bot") or not developer or developer == body.NO_RESPONSE:
        developer = f"`_No response_` (the PR author matches the [bot/AI credit policy]({BOT_POLICY}))"
    else:
        developer = code(developer)
    lines = [
        f"**Imported from public PR {_pr_link(upstream, number)} on {one_line(data['date'])}** "
        f"(scope: {code(scope)}, PR state: {code(data['state'])}).",
        "",
        "This tracker was deliberately opened by the security team for a public fix that did **not** arrive on "
        f"`{one_line(data.get('security_list') or 'security@')}`. The validity assessment was made informally "
        "before invocation; the tracker landed in the `Assessed` column accordingly.",
        "",
        f"**Next:** allocate the CVE with the [`security-cve-allocate`]({CVE_ALLOCATE}) skill.",
        "",
        f"Provenance: public PR {url}, author {code('@' + one_line(data['author_login']))}.",
        f"Extracted fields: scope={code(scope)}, *PR with the fix*={url}, *Remediation developer*={developer}, "
        f"*Affected versions*={code(data.get('affected_versions') or '_No response_')}, "
        f"Severity={code(data.get('severity') or 'Unknown')}.",
        "",
        (
            f"*Reporter credited as* set to {code(credit)} at confirmation — an override of the default blank, "
            "for a project-specific reason; public-PR imports do not credit the PR author as the CVE reporter. "
            f"See the [Reporter credit policy]({CREDIT_POLICY})."
            if (credit := one_line(data.get("reporter_credit")))
            else "*Reporter credited as* intentionally left blank — public-PR imports do not credit the PR author "
            "as the CVE reporter (no responsible disclosure). See the "
            f"[Reporter credit policy]({CREDIT_POLICY}) for the rationale."
        ),
    ]
    return {
        "ok": True,
        "label": label,
        "label_shell": dq(label),
        "text": column_zero("\n".join(lines)) + "\n",
    }


def dup_query(
    number: int, tracker: str, hits: Sequence[Mapping[str, Any]] | None = None, platform: str = "github"
) -> dict[str, Any]:
    query = f'in:body "pull/{number}" OR {number}'
    out: dict[str, Any] = {
        "query": query,
        "command": f"gh search issues --repo {tracker} {dq(query)} --limit {DUP_LIMIT} --json number,title,state",
    }
    if hits is None:
        return out
    found = [
        {
            "id": one_line(h.get("number", h.get("id"))),
            "state": str(h.get("state") or ""),
            "link": refs.tracker_link(tracker, h.get("number", h.get("id")), h.get("url"), platform),
        }
        for h in hits
    ]
    out.update(
        hits=found,
        duplicate=bool(found),
        truncated=len(found) >= DUP_LIMIT,
        warning=(
            f"{len(found)} hits: the bare number matches too broadly to rule a duplicate out; list them and ask"
            if len(found) >= DUP_LIMIT
            else None
        ),
    )
    return out


def recap(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    link = refs.tracker_link(tracker, data.get("number", data.get("id")), data.get("url"), platform)
    milestone = one_line(data.get("milestone")) or "none set"
    labels_ = ", ".join(code(label) for label in data.get("labels") or []) or "none"
    rollup_url = one_line(data.get("rollup_url"))
    lines = [
        f"- Tracker: {link}",
        f"- Imported from: {one_line(data['pr_url'])}",
        f"- Board column: `{one_line(data.get('column') or 'Assessed')}`",
        f"- Labels: {labels_}",
        f"- Milestone: {milestone}",
        f"- Status rollup: [{rollup_url}]({rollup_url})" if rollup_url else "- Status rollup: not posted",
        "",
        f"> Next: allocate the CVE for this tracker. Run `security-cve-allocate` on {link}.",
    ]
    text = "\n".join(lines) + "\n"
    return {"text": text, "bare_refs": refs.bare_refs(text)}
