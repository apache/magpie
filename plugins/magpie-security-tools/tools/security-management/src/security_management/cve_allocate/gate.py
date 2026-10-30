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
"""Inputs, Step 0 item 5, Step 1, and the CVE ID that comes back.

- `selector`: one tracker (`242`, `#242`, `<tracker>#242`, the issue URL, or
  a backend ID) and an optional `CVE-YYYY-NNNNN` override; a token that
  looks like a CVE ID but is malformed is refused, never repaired.
- `blockers`: the Step 1 checks as a function of state, labels and the *CVE
  tool link* value `body-field-get` printed. The `needs triage` warning
  only fires when no hard blocker did.
- `preflight`: the two `vulnogram-api-check` exits as the Step 3 path.
- `cve`: the one `CVE-YYYY-NNNNN` in text the user pasted back.
- `allocate_result`: what a `vulnogram-api-allocate` exit means next. The
  allocation is never re-run automatically.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import selectors
from security_management.shared.rollup import one_line
from security_management.shell import dq, w

CVE_FIELD = "CVE tool link"
CVE_ALLOCATED = "cve allocated"
DUPLICATE = "duplicate"
NEEDS_TRIAGE = "needs triage"
OAUTH_API = "<framework>/tools/cve-tool-vulnogram/oauth-api"
READ = "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-cve-allocate"

_CVE_IN_FIELD = re.compile(r"CVE-\d{4}-\d+")
_CVE_LIKE = re.compile(r"(?<![\w-])CVE-[\w-]*", re.IGNORECASE)
_SKILL = re.compile(r"^/?(?:magpie-security:)?(?:security-)?cve-allocate$", re.IGNORECASE)
_BACKEND_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _names(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        value = value.get("nodes") or []
    return [str(v.get("name") if isinstance(v, Mapping) else v) for v in value or []]


def _cve_tokens(text: str) -> tuple[list[str], list[str]]:
    """`(valid, malformed)` CVE-like tokens in `text`, valid ones upper-cased and de-duplicated."""
    valid: list[str] = []
    malformed: list[str] = []
    for match in _CVE_LIKE.finditer(text):
        token = match.group(0).rstrip(".,;:-_")
        upper = token.upper()
        if selectors.CVE.match(upper):
            if upper not in valid:
                valid.append(upper)
        else:
            malformed.append(token)
    return valid, malformed


def selector(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    field = str(data.get("cve_field") or CVE_FIELD)
    words = str(data.get("invocation") or "").split()
    if words and _SKILL.match(words[0]):
        words = words[1:]
    valid, malformed = _cve_tokens(" ".join(words))
    if malformed:
        return {
            "ok": False,
            "refused": f"{malformed[0]!r} is not a CVE ID of the form CVE-YYYY-NNNNN: ask for the correct one",
        }
    if len(valid) > 1:
        return {"ok": False, "refused": f"more than one CVE ID given ({', '.join(valid)}): name one"}
    rest = " ".join(word for word in words if not _CVE_LIKE.fullmatch(word.rstrip(".,;:")))
    if not rest.strip():
        return {"ok": False, "refused": "no tracker given: ask for the issue number first"}
    if platform == "github":
        try:
            numbers = selectors.issue_numbers(rest, tracker)
        except ValueError as exc:
            return {"ok": False, "refused": str(exc)}
        if len(numbers) != 1:
            return {"ok": False, "refused": "this skill allocates for one tracker at a time"}
        issue: int | str = numbers[0]
        commands = [
            f"gh issue view {issue} --repo {w(tracker)} --json number,title,state,labels,milestone,assignees,author",
            f"{READ} body-field-get {issue} {dq(field)}",
        ]
    else:
        tokens = rest.split()
        if len(tokens) != 1 or not _BACKEND_ID.match(tokens[0]):
            return {"ok": False, "refused": f"{rest!r} is not one {platform} tracker ID"}
        issue = tokens[0]
        commands = [f"{READ} issue-view {w(issue)}", f"{READ} body-field-get {w(issue)} {dq(field)}"]
    override = valid[0] if valid else None
    return {
        "ok": True,
        "issue": issue,
        "cve_override": override,
        "resume_step": 4 if override else 1,
        "commands": commands,
    }


def _either(names: Sequence[str]) -> str:
    if len(names) <= 2:
        return " or ".join(names)
    return f"{', '.join(names[:-1])}, or {names[-1]}"


def blockers(data: Mapping[str, Any]) -> dict[str, Any]:
    labels = _names(data.get("labels"))
    scopes = [str(s) for s in data.get("scope_labels") or []]
    if not scopes:
        return {"ok": False, "refused": "scope_labels is empty: read the scope labels from project.md"}
    allocated = str(data.get("cve_allocated_label") or CVE_ALLOCATED)
    duplicate = str(data.get("duplicate_label") or DUPLICATE)
    needs_triage = str(data.get("needs_triage_label") or NEEDS_TRIAGE)
    override = one_line(data.get("cve_override")).upper() or None
    link = str(data.get("cve_tool_link") or "")
    existing = _CVE_IN_FIELD.findall(link)
    found: list[str] = []
    resumed = bool(override) and existing == [override]

    if str(data.get("state") or "").upper() != "OPEN":
        found.append(
            "Issue is closed — allocating a CVE for a closed tracker is almost always a mistake "
            "(closed as invalid, duplicate or already announced); ask the user what they intend"
        )
    if data.get("cve_tool_link_undecided"):
        found.append(
            "The CVE tool link field cannot be read unambiguously (a repeated or ambiguous heading) — "
            "fix the body before allocating"
        )
    elif existing and not resumed:
        found.append(f"CVE already allocated: {existing[0]} found in the CVE tool link body field")
    if allocated in labels and not resumed:
        found.append(f"`{allocated}` label already present")
    if duplicate in labels:
        found.append(
            "Tracker is marked duplicate — the canonical tracker already carries the CVE; "
            "allocating here would create a second CVE for the same root cause"
        )
    set_scopes = [s for s in scopes if s in labels]
    if not set_scopes:
        found.append(
            f"No scope label set ({_either(scopes)}) — scope is required to map the product/packageName "
            "in the CVE record; set the scope label before allocating"
        )
    elif len(set_scopes) > 1:
        found.append(
            f"More than one scope label set ({', '.join(set_scopes)}) — the CVE record names one product; "
            "keep one scope label before allocating"
        )
    warnings = []
    if not found and needs_triage in labels:
        warnings.append(
            f"{needs_triage} label is still set — confirm the valid/invalid decision has landed before allocating"
        )
    return {
        "verdict": "blocked" if found else "proceed",
        "blockers": found,
        "warnings": warnings,
        "existing_cve": existing[0] if existing else None,
        "already_wired": resumed,
        "scope_label": set_scopes[0] if len(set_scopes) == 1 else None,
    }


def _check(scope: str, oauth_api: str) -> str:
    flags = "--server --quiet" if scope == "server" else "--allocate"
    return f"uv run --project {w(oauth_api)} vulnogram-api-check {flags}"


def preflight(data: Mapping[str, Any]) -> dict[str, Any]:
    oauth_api = str(data.get("oauth_api") or OAUTH_API)
    pmc = one_line(data.get("pmc"))
    setup = f"uv run --project {w(oauth_api)} vulnogram-api-setup --pmc {w(pmc or '<pmc>')}"

    def out(
        path: str | None, why: str, *, offer_setup: bool = False, command: str | None = None
    ) -> dict[str, Any]:
        return {
            "path": path,
            "reason": why,
            "offer_setup": offer_setup,
            "setup_command": setup if offer_setup else None,
            "command": command,
        }

    if data.get("governance_member") is not True:
        return out("recipe", "API allocation is only for a governance-authorised user")
    if data.get("server_exit") is None:
        return out(None, "run the server check first", command=_check("server", oauth_api))
    server = int(data["server_exit"])
    if server == 4:
        return out(
            "recipe", "the server has neither browser-approved tokens nor JSON answers from /allocatecve"
        )
    if server == 3:
        return out("recipe", "network error on the server check; mention it")
    if server != 0:
        return out("recipe", f"unexpected server-check exit {server}")
    if data.get("allocate_exit") is None:
        return out(
            None, "the server supports it: check the allocate token", command=_check("allocate", oauth_api)
        )
    code = int(data["allocate_exit"])
    if code == 0:
        lines = [one_line(line) for line in str(data.get("allocate_stdout") or "").splitlines()]
        if pmc and f"allocate token for {pmc}" in lines:
            return out("api", f"a live allocate token for {pmc}")
        return out(
            None,
            f"the live allocate token is not for {pmc or '<pmc>'}: run the setup for it",
            offer_setup=True,
        )
    if code in (1, 2):
        state = "expired" if code == 1 else "not-configured"
        return out(None, f"allocate token {state}: offer the setup, then re-run the check", offer_setup=True)
    if code == 4:
        return out("recipe", "unsupported: the server answers HTML")
    return out("recipe", f"allocate check failed (exit {code}); mention the error")


def cve(data: Mapping[str, Any]) -> dict[str, Any]:
    valid, malformed = _cve_tokens(str(data.get("text") or ""))
    if len(valid) > 1:
        return {
            "ok": False,
            "refused": f"more than one CVE ID ({', '.join(valid)}): ask which one was allocated",
        }
    if not valid:
        if malformed:
            return {
                "ok": False,
                "refused": f"{malformed[0]!r} is not of the form CVE-YYYY-NNNNN: ask for the correct ID",
            }
        return {"ok": False, "refused": "no CVE-YYYY-NNNNN in the reply: wait for the allocated ID"}
    out: dict[str, Any] = {"ok": True, "cve_id": valid[0], "ignored_malformed": malformed}
    template = one_line(data.get("record_url_template"))
    if template:
        out["record_url"] = record_url(template, valid[0])
    return out


def record_url(template: str, cve_id: str) -> str:
    if not selectors.CVE.match(cve_id):
        raise ValueError(f"{cve_id!r} is not a CVE ID")
    for token in ("<CVE-ID>", "{cve_id}", "<CVE-YYYY-NNNNN>", "{CVE-ID}"):
        if token in template:
            return template.replace(token, cve_id)
    raise ValueError(f"record_url_template {template!r} has no <CVE-ID> placeholder")


def allocate_result(data: Mapping[str, Any]) -> dict[str, Any]:
    code = int(data["exit"])
    first = next((one_line(line) for line in str(data.get("stdout") or "").splitlines() if line.strip()), "")
    stderr = str(data.get("stderr") or "")
    pmc = one_line(data.get("pmc")) or "<pmc>"
    check = f"ask the user to check {pmc}'s records in Vulnogram before anything else"

    def out(next_step: str, why: str, cve_id: str | None = None) -> dict[str, Any]:
        return {"next": next_step, "cve_id": cve_id, "message": why, "rerun_allocate": False}

    if code in (0, 6):
        if not selectors.CVE.match(first):
            return out(
                "check-records",
                f"exit {code} without a CVE ID on the first line: {check}; never re-run the allocation",
            )
        if code == 0:
            return out("step-4", "allocated; no paste-back needed", first)
        return out(
            "step-4",
            "the ID is reserved but Vulnogram did not save its record; the sync push creates it",
            first,
        )
    if code == 5:
        return out(
            "stop",
            "the PMC cannot allocate directly and Vulnogram mailed the security team: resume later with the ID as an override",
        )
    if code == 1:
        result = out(
            "setup",
            "the token expired and nothing was sent: re-run the setup, then allocate once more after a fresh yes",
        )
        result["rerun_allocate"] = True
        return result
    if code == 4:
        return out(
            "check-records",
            f"Vulnogram answered HTML with no ID: {check} (it may have allocated), then use the recipe",
        )
    if "may still have gone through" in stderr:
        return out("check-records", f"the request may still have gone through: {check}, then use the recipe")
    return out("recipe", "allocation failed: show stderr, then use the recipe")
