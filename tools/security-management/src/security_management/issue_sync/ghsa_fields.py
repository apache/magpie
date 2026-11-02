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
"""Mirror a tracker's fields onto its GitHub repository security advisory.

The tracker is authoritative; the advisory is the mirror the reporter
watches. `fields` compares one advisory record (`GET …/security-advisories/
<GHSA>`) with the tracker and returns the smallest `PATCH` body that brings
the advisory in line, field by field, with a reason for every change and
every skip:

- `cve_id` — set when empty; a different CVE already on the advisory is a
  conflict, reported and never overwritten.
- `severity` — the team's textual score (never the reporter's), mapped onto
  `critical` / `high` / `medium` / `low`.
- `cwe_ids` — the `CWE-<n>` ids in the tracker's CWE field.
- `vulnerabilities` — `vulnerable_version_range` and `patched_versions`
  from *Affected versions* (`>= X, < Y`, `< Y`, `<= Y`), on the entry for the
  tracker's package; other entries and `vulnerable_functions` are kept. A
  single entry naming another package (often the repository slug) takes the
  tracker's package, shown as `drift`.
- `credits` — the advisory's credits kept as they are, plus the authors of
  every fix PR (`pr_author_logins`) as `remediation_developer` and their
  approvers as `remediation_reviewer`; the API replaces the list, so the whole list is sent.
  Bot or AI accounts are left out, per the bot/AI credit policy.
- `summary` — the normalised CVE title, only when one is given.
- `description` — opt-in: a *Resolution* block appended below the reporter's
  text (CVE, fix PR, fixed version, public advisory), only once the public
  advisory URL is captured; re-runs replace the block, never the text above it.

It never writes `state` or the collaborator lists: those are admin-only and
go through the admin hand-off (`ghsa-route`).

The other direction is proposals only (`tracker_proposals`): where the
tracker field is still empty and the advisory carries a value — the CVE, the
CWE, the affected range — the value is proposed for the tracker, to be
confirmed per field. The advisory's severity is never proposed (the reporter
sets it, and the team scores independently), and credits other than the
fix's are listed in `observed` for the team to decide. Where both sides hold
a value and they differ, the tracker wins the patch and `drift` shows the
advisory's value, so an edit by the reporter is seen before it is overwritten.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import reuse

ECOSYSTEMS = frozenset(
    {
        "rubygems",
        "npm",
        "pip",
        "maven",
        "nuget",
        "composer",
        "go",
        "rust",
        "erlang",
        "actions",
        "pub",
        "other",
        "swift",
    }
)
SEVERITIES = (
    ("critical", "critical"),
    ("high", "high"),
    ("medium", "medium"),
    ("moderate", "medium"),
    ("low", "low"),
)
NO_RESPONSE = "_No response_"
RESOLUTION_MARKER = "<!-- magpie: ghsa-resolution v1 -->"

_VERSION = r"[0-9][0-9A-Za-z.\-+]*"
_NEXT_VERSION = re.compile(r"<\s*NEXT\s+VERSION\b", re.IGNORECASE)
_RANGE = re.compile(rf">=?\s*(?P<low>{_VERSION})\s*,?\s*<\s*(?P<high>{_VERSION})")
_LE = re.compile(rf"^<=\s*(?P<high>{_VERSION})$")
_LT = re.compile(rf"^<\s*(?P<high>{_VERSION})$")
_CWE = re.compile(r"\bCWE-(\d+)\b", re.IGNORECASE)
_CVE = re.compile(r"^CVE-\d{4}-\d{4,7}$")


def _text(value: Any) -> str:
    text = str(value or "").strip().strip("`").strip()
    return "" if text == NO_RESPONSE else text


def version_range(value: Any) -> dict[str, Any] | None:
    """`{range, patched}` in GitHub's syntax, or None when the field does not parse."""
    text = _text(value)
    pending = bool(_NEXT_VERSION.search(text))
    text = _NEXT_VERSION.sub("", text).strip().rstrip(",").strip()
    if match := _RANGE.search(text):
        if pending:
            return None
        return {"range": f">= {match['low']}, < {match['high']}", "patched": match["high"]}
    if match := _LE.match(text):
        return {"range": f"<= {match['high']}", "patched": None}
    if match := _LT.match(text):
        return {"range": f"< {match['high']}", "patched": match["high"]}
    if pending and (match := re.match(rf"^>=?\s*(?P<low>{_VERSION})$", text)):
        return {"range": f">= {match['low']}", "patched": None}
    return None


def severity(value: Any) -> str | None:
    text = _text(value).lower()
    hits = [(text.find(word), level) for word, level in SEVERITIES if re.search(rf"\b{word}\b", text)]
    return min(hits)[1] if hits else None


def _credits(advisory: Mapping[str, Any]) -> list[dict[str, str]]:
    detailed = advisory.get("credits_detailed")
    if isinstance(detailed, list):
        found = [
            {"login": str((c.get("user") or {}).get("login") or ""), "type": str(c.get("type") or "")}
            for c in detailed
        ]
    else:
        found = [
            {"login": str(c.get("login") or ""), "type": str(c.get("type") or "")}
            for c in advisory.get("credits") or []
        ]
    return [c for c in found if c["login"] and c["type"]]


def _resolution_block(tracker: Mapping[str, Any], fixed: str | None, package: str | None) -> str:
    lines = [RESOLUTION_MARKER, "### Resolution", ""]
    cve = _text(tracker.get("cve_id"))
    if cve:
        lines.append(f"- CVE: [{cve}](https://www.cve.org/CVERecord?id={cve})")
    if pr := _text(tracker.get("pr_with_fix")):
        lines.append(f"- Fix: {pr}")
    if fixed:
        lines.append(f"- Fixed in: {package + ' ' if package else ''}{fixed}")
    lines.append(f"- Public advisory: {_text(tracker.get('public_advisory_url'))}")
    return "\n".join(lines)


def fields(data: Mapping[str, Any]) -> dict[str, Any]:
    advisory = data.get("advisory")
    tracker = data.get("tracker")
    if not isinstance(advisory, Mapping) or not isinstance(tracker, Mapping):
        return {
            "ok": False,
            "refused": "advisory (the GET record) and tracker (its body fields) are required",
        }
    ghsa = str(advisory.get("ghsa_id") or "")
    patch: dict[str, Any] = {}
    changes: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    proposals: list[dict[str, Any]] = []
    drift: list[dict[str, Any]] = []
    observed: list[str] = []

    def propose(field: str, value: Any, why: str) -> None:
        proposals.append({"tracker_field": field, "value": value, "why": why})

    def change(field: str, old: Any, new: Any, why: str) -> None:
        patch[field] = new
        changes.append({"field": field, "from": old, "to": new, "why": why})

    # cve_id
    cve = _text(tracker.get("cve_id"))
    current_cve = advisory.get("cve_id")
    if not cve:
        skipped.append({"field": "cve_id", "reason": "the tracker has no CVE yet"})
        if current_cve:
            propose(
                "cve-id",
                current_cve,
                "the advisory carries a CVE the tracker lacks; confirm it was not assigned outside the project's CVE tool",
            )
    elif not _CVE.match(cve):
        skipped.append({"field": "cve_id", "reason": f"`{cve}` is not a CVE id"})
    elif current_cve and current_cve != cve:
        conflicts.append({"field": "cve_id", "advisory": str(current_cve), "tracker": cve})
    elif current_cve != cve:
        change("cve_id", current_cve, cve, "link the tracker's CVE")

    # severity
    level = severity(tracker.get("severity"))
    if level is None:
        skipped.append({"field": "severity", "reason": "the tracker's severity is not scored yet"})
    elif advisory.get("severity") != level:
        change("severity", advisory.get("severity"), level, "the team's score replaces the reporter's")
    if level is None and advisory.get("severity"):
        observed.append(
            f"advisory severity `{advisory.get('severity')}`: never proposed for the tracker (the team scores independently)"
        )

    # cwe_ids
    cwes = sorted({f"CWE-{n}" for n in _CWE.findall(_text(tracker.get("cwe")))}, key=lambda c: int(c[4:]))
    advisory_cwes = list(advisory.get("cwe_ids") or [])
    if not cwes:
        skipped.append({"field": "cwe_ids", "reason": "the tracker has no CWE"})
        if advisory_cwes:
            propose("cwe", ", ".join(advisory_cwes), "the advisory names a CWE the tracker lacks")
    elif sorted(advisory_cwes) != sorted(cwes):
        if advisory_cwes:
            drift.append({"field": "cwe_ids", "advisory": advisory_cwes, "tracker": cwes})
        change("cwe_ids", advisory_cwes, cwes, "mirror the tracker's CWE")

    # vulnerabilities
    fixed: str | None = None
    package_name: str | None = None
    parsed = version_range(tracker.get("affected_versions"))
    raw_pkg = tracker.get("package")
    pkg: Mapping[str, Any] = raw_pkg if isinstance(raw_pkg, Mapping) else {}
    entries = [dict(v) for v in advisory.get("vulnerabilities") or []]
    if parsed is None:
        skipped.append(
            {
                "field": "vulnerabilities",
                "reason": "*Affected versions* is empty, pending, or not `>= X, < Y` / `< Y` / `<= Y`",
            }
        )
        ranges = [str(e.get("vulnerable_version_range") or "").strip() for e in entries]
        ranges = [r for r in ranges if r]
        if not _text(tracker.get("affected_versions")) and len(ranges) == 1:
            propose("affected-versions", ranges[0], "the advisory states an affected range the tracker lacks")
    else:
        fixed = parsed["patched"]
        want_name = _text(pkg.get("name")) or None
        want_eco = _text(pkg.get("ecosystem")).lower() or None
        if want_eco and want_eco not in ECOSYSTEMS:
            return {"ok": False, "refused": f"package ecosystem `{want_eco}` is not one GitHub accepts"}
        index = None
        if want_name:
            named = [
                i for i, e in enumerate(entries) if ((e.get("package") or {}).get("name") or "") == want_name
            ]
            index = named[0] if named else None
        if index is None and len(entries) == 1:
            index = 0
        if index is None and not entries and want_name and want_eco:
            entries.append({"package": {"ecosystem": want_eco, "name": want_name}})
            index = 0
        if index is None:
            skipped.append(
                {
                    "field": "vulnerabilities",
                    "reason": "no single advisory entry matches the tracker's package; name it",
                }
            )
        else:
            entry = entries[index]
            package = dict(entry.get("package") or {})
            if want_name and package.get("name") != want_name:
                # One entry that names something else (a reporter often types the
                # repository slug): the tracker's package replaces it, ecosystem
                # included, and the old one is shown as drift. A name and a foreign
                # ecosystem never get combined into a package that does not exist.
                if package.get("name"):
                    drift.append({"field": "package", "advisory": dict(package), "tracker": dict(pkg)})
                package = {"ecosystem": want_eco or package.get("ecosystem") or "other", "name": want_name}
            elif want_eco and package.get("ecosystem") in (None, "", "other") and want_eco != "other":
                package["ecosystem"] = want_eco
            package_name = package.get("name")
            updated = {
                **entry,
                "package": package,
                "vulnerable_version_range": parsed["range"],
                "patched_versions": fixed if fixed else entry.get("patched_versions"),
            }
            old_range = str(entry.get("vulnerable_version_range") or "").strip()
            if old_range and old_range != parsed["range"]:
                drift.append(
                    {"field": "vulnerable_version_range", "advisory": old_range, "tracker": parsed["range"]}
                )
            if updated != entry:
                before = [dict(e) for e in advisory.get("vulnerabilities") or []]
                entries[index] = updated
                body = [
                    {
                        "package": e.get("package"),
                        "vulnerable_version_range": e.get("vulnerable_version_range"),
                        "patched_versions": e.get("patched_versions"),
                        "vulnerable_functions": e.get("vulnerable_functions") or [],
                    }
                    for e in entries
                ]
                change("vulnerabilities", before, body, "mirror *Affected versions* and the fixed release")

    # credits
    credits = _credits(advisory)
    have = {(c["login"].lower(), c["type"]) for c in credits}
    added: list[dict[str, str]] = []
    bots: list[str] = []
    authors = [_text(tracker.get("pr_author_login"))] + [
        _text(a) for a in tracker.get("pr_author_logins") or []
    ]
    authors = list(dict.fromkeys(a for a in authors if a))
    wanted = [(a, "remediation_developer") for a in authors]
    wanted += [
        (login, "remediation_reviewer")
        for login in dict.fromkeys(tracker.get("pr_approver_logins") or [])
        if login and login not in authors
    ]
    for login, kind in wanted:
        if login.endswith("[bot]") or reuse.is_bot_credit(login):
            bots.append(login)
            continue
        if (login.lower(), kind) not in have:
            have.add((login.lower(), kind))
            added.append({"login": login, "type": kind})
    for c in credits:
        if c["type"] not in ("reporter", "remediation_developer", "remediation_reviewer"):
            observed.append(f"advisory credits `{c['login']}` as `{c['type']}`: check *Reporter credited as*")
    if added:
        change("credits", credits, credits + added, "credit the fix's author and reviewers")
    elif not wanted:
        skipped.append({"field": "credits", "reason": "no fix PR author or approvers given"})

    # summary
    title = _text(tracker.get("cve_title"))
    if title and title != advisory.get("summary"):
        change("summary", advisory.get("summary"), title, "the normalised CVE title")

    # description — opt-in Resolution block
    if data.get("resolution"):
        if not _text(tracker.get("public_advisory_url")):
            skipped.append({"field": "description", "reason": "the public advisory URL is not captured yet"})
        else:
            original = str(advisory.get("description") or "")
            head = original.split(RESOLUTION_MARKER, 1)[0].rstrip()
            head = head[: -len("---")].rstrip() if head.endswith("---") else head
            block = _resolution_block(tracker, fixed, package_name)
            new = f"{head}\n\n---\n{block}\n" if head else f"{block}\n"
            if new.strip() != original.strip():
                change(
                    "description",
                    "(reporter's text kept above the block)",
                    new,
                    "append the Resolution block",
                )

    return {
        "ok": True,
        "ghsa_id": ghsa,
        "html_url": advisory.get("html_url"),
        "patch": patch,
        "changes": changes,
        "skipped": skipped,
        "conflicts": conflicts,
        "drift": drift,
        "tracker_proposals": proposals,
        "observed": observed,
        "bots_not_credited": bots,
        "unchanged": not patch,
        "requires_confirmation": bool(patch),
        "never_writes": ["state", "collaborating_users", "collaborating_teams"],
        "command": (
            f"gh api --method PATCH repos/<upstream>/security-advisories/{ghsa} --input <patch-file>"
            if patch
            else None
        ),
    }


def backfill(data: Mapping[str, Any]) -> dict[str, Any]:
    """One `fields` plan per (advisory, tracker) pair; unchanged advisories listed apart."""
    items = data.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return {"ok": False, "refused": "items must be a list of {advisory, tracker, tracker_number}"}
    plans: list[dict[str, Any]] = []
    unchanged: list[str] = []
    refused: list[dict[str, str]] = []
    for item in items:
        result = fields({**item, "resolution": data.get("resolution", False)})
        ghsa = str((item.get("advisory") or {}).get("ghsa_id") or "")
        if result.get("ok") is False:
            refused.append({"ghsa_id": ghsa, "reason": str(result["refused"])})
        elif result["unchanged"] and not (result["conflicts"] or result["tracker_proposals"]):
            unchanged.append(ghsa)
        else:
            plans.append({"tracker_number": item.get("tracker_number"), **result})
    return {
        "ok": True,
        "plans": plans,
        "unchanged": unchanged,
        "refused": refused,
        "one_patch_per_advisory": True,
    }
