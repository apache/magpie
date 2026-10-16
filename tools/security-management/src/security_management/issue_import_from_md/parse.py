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
"""Steps 0 and 1: the shape check and the findings-file parser (findings-format.md).

The file is split on `(?m)^---\\s*$`; whitespace-only blocks are dropped; each
block carrying a `**Severity:**` line is a metadata block and pairs with the
block immediately before it, which carries `# Title` and the `## Section`s.
Every value is attacker-controlled text: it is returned as data, never
interpreted, and a directive in a title is just part of the title.
"""

from __future__ import annotations

import re
from typing import Any

from security_management.shared import body, titles

NOT_A_FINDINGS_FILE = "not-a-findings-file"
SEVERITIES = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
REQUIRED_SECTIONS = ("Details", "Impact", "Reproduction steps")
_SPLIT = re.compile(r"(?m)^---\s*$")
_TITLE = re.compile(r"^# (.+?)\s*$", re.M)
_SEVERITY_LINE = re.compile(r"^\*\*Severity:\*\*", re.M)
_META = re.compile(r"^\*\*([A-Za-z][A-Za-z ]*):\*\*[ \t]*(.*?)\s*$")
_SECTION = re.compile(r"^## (.+?)\s*$")
_LINK = re.compile(r"\[([^\]\n]*)\]\((\S+?)\)")
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$")
_CREDIT_KEYS = ("reporter", "finder", "discovered by")


def shape_ok(text: str) -> bool:
    """At least one `# ` title heading and at least one `**Severity:**` line."""
    return bool(_TITLE.search(text)) and bool(_SEVERITY_LINE.search(text))


def _sections(narrative: str) -> tuple[str, dict[str, str]]:
    title = ""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    in_fence = False
    for line in narrative.split("\n"):
        if body.is_fence(line):
            in_fence = not in_fence
        if not in_fence and not title and current is None and (m := _TITLE.match(line)):
            title = m.group(1).strip()
            continue
        if not in_fence and (m := _SECTION.match(line)):
            current = m.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return title, {k: "\n".join(v).strip("\n") for k, v in sections.items()}


def _metadata(block: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in block.split("\n"):
        if m := _META.match(line.strip()):
            meta.setdefault(m.group(1).strip().lower(), m.group(2))
    return meta


def _finding(index: int, narrative: str, meta_block: str, upstream: str) -> dict[str, Any]:
    title, sections = _sections(narrative)
    meta = _metadata(meta_block)
    warnings: list[str] = []
    raw = meta.get("severity", "").strip()
    severity = raw.upper()
    if severity not in SEVERITIES:
        warnings.append(f"Severity '{raw}' is not one of HIGH, MEDIUM, LOW, UNKNOWN — recorded as UNKNOWN.")
        severity = "UNKNOWN"
    repository = meta.get("repository", "").strip()
    if not _REPO.fullmatch(repository):
        what = f"'{repository}' is not owner/repo" if repository else "missing"
        warnings.append(f"Repository {what} — fell back to {upstream}.")
        repository = upstream
    for name in REQUIRED_SECTIONS:
        if not (sections.get(name) or "").strip():
            warnings.append(
                f"Section '## {name}' is missing — tracker body field will use '_No response_' "
                f"for the {name.lower()} section."
            )
    location = sections.get("Location") or ""
    link = _LINK.search(location)
    credit = next((meta[k] for k in _CREDIT_KEYS if meta.get(k, "").strip()), None)
    return {
        "index": index,
        "title": title,
        "tracker_title": titles.md_title(title),
        "severity": severity,
        "status": meta.get("status") or None,
        "category": meta.get("category") or None,
        "repository": repository,
        "branch": meta.get("branch") or None,
        "date_created": meta.get("date created") or None,
        "credited_handle": credit,
        "details": sections.get("Details") or "",
        "impact": sections.get("Impact") or "",
        "repro_steps": sections.get("Reproduction steps") or "",
        "recommended_fix": sections.get("Recommended fix") or "",
        "location_label": link.group(1) if link else location.strip() or None,
        "location_url": link.group(2) if link else None,
        "has_details": bool((sections.get("Details") or "").strip()),
        "has_impact": bool((sections.get("Impact") or "").strip()),
        "has_repro_steps": bool((sections.get("Reproduction steps") or "").strip()),
        "warnings": warnings,
    }


def parse(text: str, upstream: str) -> dict[str, Any]:
    """`{ok, findings, warnings, total_findings}`, or `{ok: false, refused: not-a-findings-file}`."""
    if not shape_ok(text):
        return {"ok": False, "refused": NOT_A_FINDINGS_FILE}
    blocks = [b for b in _SPLIT.split(text) if b.strip()]
    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    previous: str | None = None
    for position, block in enumerate(blocks, start=1):
        if not _SEVERITY_LINE.search(block):
            if previous is not None:
                warnings.append(f"Block {position - 1} has no metadata block after it — ignored.")
            previous = block
            continue
        if previous is None:
            warnings.append(f"Metadata block {position} has no narrative block before it — ignored.")
            continue
        finding = _finding(len(findings) + 1, previous, block, upstream)
        previous = None
        if not finding["title"]:
            warnings.append(f"Block {position - 1} has no '# Title' heading — ignored.")
            continue
        findings.append(finding)
        warnings.extend(f"Finding {finding['index']}: {w}" for w in finding["warnings"])
    if previous is not None:
        warnings.append(f"Block {len(blocks)} has no metadata block after it — ignored.")
    if not findings:
        return {"ok": False, "refused": NOT_A_FINDINGS_FILE, "warnings": warnings}
    return {"ok": True, "findings": findings, "warnings": warnings, "total_findings": len(findings)}
