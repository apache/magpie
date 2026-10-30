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
"""Steps C to F of the scanner on-ramp: what a bucket allows, the report, the decision, the scrub.

- `bucket_action` enforces Golden rule 3 in code: only `import-as-tracker`
  creates a tracker; PR-worth and defense-in-depth are open-a-PR-or-skip;
  the rest take no action.
- `render_report` lays out the per-scan report (distribution line, one
  section per bucket, a row per finding) and, for several scans, the
  cross-scan outcome table, the aggregate breakdown with percentages and the
  severity-vs-disposition table. Which bucket a finding goes in, and its
  grounding, are the model's; the "what the scanner is good for" prose too.
- `parse_decision` reads the Step E reply grammar; anything it cannot place
  holds every action.
- `scrub` finds what a public surface must not carry and never rewrites it.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import body
from security_management.shared.rollup import one_line

BUCKETS = (
    "import-as-tracker",
    "PR-worth",
    "defense-in-depth",
    "by-design",
    "duplicate",
    "already-fixed",
)
_ALIASES = {b.lower(): b for b in BUCKETS} | {
    "invalid": "by-design",
    "by-design/invalid": "by-design",
    "pr": "PR-worth",
}
ACTIONS = {
    "import-as-tracker": ("tracker", "security-issue-import Step 7: one Needs triage tracker"),
    "PR-worth": ("pr-or-skip", "security-issue-fix: a public PR, or skip"),
    "defense-in-depth": ("pr-or-skip", "security-issue-fix: a public PR, or skip"),
    "by-design": ("none", "recorded in the report"),
    "duplicate": ("none", "link the existing tracker"),
    "already-fixed": ("none", "note the fixing PR or commit"),
}
SEVERITIES = ("Critical", "High", "Medium", "Low", "Info", "Unknown")


def bucket(name: object) -> str:
    text = one_line(name)
    canonical = _ALIASES.get(text.lower())
    if canonical is None:
        raise ValueError(f"unknown disposition bucket {text!r}; one of {', '.join(BUCKETS)}")
    return canonical


def bucket_action(name: object) -> dict[str, Any]:
    canonical = bucket(name)
    action, route = ACTIONS[canonical]
    return {
        "bucket": canonical,
        "creates_tracker": canonical == "import-as-tracker",
        "action": action,
        "route": route,
    }


def _severity(value: object) -> str:
    text = one_line(value).capitalize()
    return text if text in SEVERITIES else "Unknown"


def _cell(value: object) -> str:
    return body.short_field(one_line(value)).replace("|", "\\|")


def _rows(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for f in findings:
        b = bucket(f["bucket"])
        grounding = one_line(f.get("grounding"))
        if b != "import-as-tracker" and b not in ("PR-worth", "defense-in-depth") and not grounding:
            raise ValueError(f"finding {one_line(f.get('id'))}: a {b} disposition needs its grounding")
        rows.append({**f, "bucket": b, "severity": _severity(f.get("severity")), "grounding": grounding})
    return rows


def _pct(n: int, total: int) -> str:
    return f"{(100 * n / total):.0f}%" if total else "0%"


def _scan_report(name: str, rows: Sequence[Mapping[str, Any]]) -> list[str]:
    counts = Counter(r["bucket"] for r in rows)
    lines = [f"## {_cell(name)}", ""]
    lines.append(
        f"{len(rows)} findings: " + ", ".join(f"{counts[b]} {b}" for b in BUCKETS if counts[b]) + "."
    )
    for b in BUCKETS:
        members = [r for r in rows if r["bucket"] == b]
        if not members:
            continue
        lines += [
            "",
            f"### {b} ({len(members)})",
            "",
            "| ID | Title | Severity | Grounding | Recommended action |",
            "|---|---|---|---|---|",
        ]
        route = ACTIONS[b][1]
        lines += [
            f"| {_cell(r.get('id'))} | {_cell(r.get('title'))} | {r['severity']} | {_cell(r['grounding']) or '—'} | {route} |"
            for r in members
        ]
    return lines


def render_report(scans: Sequence[Mapping[str, Any]], title: str = "Scan triage report") -> dict[str, Any]:
    """The markdown report: one section per scan, and the cross-scan analysis when there are several."""
    if not scans:
        raise ValueError("no scans to report on")
    per_scan = [
        (one_line(s.get("name") or f"scan {i + 1}"), _rows(s.get("findings") or []))
        for i, s in enumerate(scans)
    ]
    lines = [f"# {_cell(title)}", ""]
    for name, rows in per_scan:
        lines += [*_scan_report(name, rows), ""]
    every = [r for _, rows in per_scan for r in rows]
    total = len(every)
    counts = Counter(r["bucket"] for r in every)
    result: dict[str, Any] = {
        "total_findings": total,
        "distribution": {b: counts[b] for b in BUCKETS},
        "trackers_possible": counts["import-as-tracker"],
    }
    if len(per_scan) > 1:
        lines += ["## Cross-scan processing report", "", "| Scan | Findings | " + " | ".join(BUCKETS) + " |"]
        lines.append("|---|---|" + "---|" * len(BUCKETS))
        for name, rows in per_scan:
            c = Counter(r["bucket"] for r in rows)
            lines.append(f"| {_cell(name)} | {len(rows)} | " + " | ".join(str(c[b]) for b in BUCKETS) + " |")
        lines += ["", "| Disposition | Findings | Share |", "|---|---|---|"]
        lines += [f"| {b} | {counts[b]} | {_pct(counts[b], total)} |" for b in BUCKETS]
        real = ("import-as-tracker", "PR-worth")
        lines += [
            "",
            "| Scanner severity | Findings | Real vulnerabilities (import-as-tracker) | Real code fixes (PR-worth) |",
            "|---|---|---|---|",
        ]
        for sev in SEVERITIES:
            at = [r for r in every if r["severity"] == sev]
            if at:
                lines.append(
                    f"| {sev} | {len(at)} | {sum(r['bucket'] == real[0] for r in at)} | {sum(r['bucket'] == real[1] for r in at)} |"
                )
        lines += ["", "<!-- the model adds: what the scanner is / is not good for -->"]
        result["percentages"] = {b: _pct(counts[b], total) for b in BUCKETS}
    result["text"] = "\n".join(lines).rstrip("\n") + "\n"
    return result


_ALL = frozenset({"all", "go", "yes", "proceed"})
_CANCEL = frozenset({"cancel", "none", "stop", "hold off", "abort"})


def parse_decision(reply: str, findings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Step E: `all` / `NN,MM` / `bucket:<name>` / `skip` / `cancel` over the numbered findings."""
    known = {int(f["n"]): bucket(f["bucket"]) for f in findings}
    actionable = {n for n, b in known.items() if ACTIONS[b][0] != "none"}
    text = reply.strip().lower()
    empty = {"action": "", "confirmed": [], "skipped": [], "ambiguous_tokens": []}
    if text in _CANCEL:
        return {**empty, "action": "cancel"}
    if text in ("skip", "skip all"):
        return {**empty, "action": "skip", "skipped": sorted(actionable)}
    chosen: set[int] = set()
    ambiguous: list[str] = []
    for token in [t for t in re.split(r"[,\s]+", text) if t]:
        if token in _ALL:
            chosen |= actionable
        elif token.isdigit() or (token.startswith("#") and token[1:].isdigit()):
            n = int(token.lstrip("#"))
            if n in actionable:
                chosen.add(n)
            else:
                ambiguous.append(token)
        elif token.startswith("bucket:"):
            try:
                b = bucket(token.split(":", 1)[1])
            except ValueError:
                ambiguous.append(token)
                continue
            members = {n for n, kb in known.items() if kb == b}
            if not members & actionable:
                ambiguous.append(token)
            chosen |= members & actionable
        else:
            ambiguous.append(token)
    if ambiguous:
        return {**empty, "action": "ambiguous", "ambiguous_tokens": ambiguous}
    plan = [{"n": n, **bucket_action(known[n])} for n in sorted(chosen)]
    return {
        "action": "apply",
        "confirmed": plan,
        "skipped": sorted(actionable - chosen),
        "ambiguous_tokens": [],
    }


_CVE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
_EMBARGO = re.compile(
    r"\b(?:embargo(?:ed)?|unpublished|not yet public|pre-disclosure|private (?:report|advisory)|security fix)\b",
    re.IGNORECASE,
)
_BARE = re.compile(r"(?<![\w\[/#&`])#\d{1,7}\b")


def scrub(text: str, tracker: str, allowed_cves: Sequence[str] = ()) -> dict[str, Any]:
    """What a public report surface must not carry; the text is never rewritten."""
    allowed = {c.upper() for c in allowed_cves}
    owner_repo = re.escape(tracker)
    private = re.compile(
        rf"(?:https?://github\.com/{owner_repo}(?:/(?:issues|pull|discussions)/\d+)?|\b{owner_repo}#\d+)",
        re.IGNORECASE,
    )
    hits: list[dict[str, Any]] = []
    for number, line in enumerate(text.split("\n"), start=1):
        for m in private.finditer(line):
            hits.append({"kind": "private-tracker-ref", "match": m.group(0), "line": number})
        for m in _CVE.finditer(line):
            if m.group(0).upper() not in allowed:
                hits.append({"kind": "cve-id", "match": m.group(0), "line": number})
        for m in _EMBARGO.finditer(line):
            hits.append({"kind": "embargo-term", "match": m.group(0), "line": number})
        for m in _BARE.finditer(private.sub("", line)):
            hits.append({"kind": "bare-ref", "match": m.group(0), "line": number})
    return {"clean": not hits, "hits": hits}
