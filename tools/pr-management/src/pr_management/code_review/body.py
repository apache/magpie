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
"""Steps 7a-8 — compose what gets posted, from findings the agent wrote.

The agent writes the findings (Step 4 shape) and the summary line; everything
else is assembled here: the section order, the blocking / major / smaller
observations layout, the inline-comment set and its anchors, the suggested
reviewers, the conflict and security notes, and the verbatim AI-attribution
footer. Every handle is backtick-quoted, so nothing posted live-mentions
anyone; `mention_scan` re-checks the result outside code spans and fences.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from typing import Any

from . import diff as difflib

_MENTION = re.compile(r"(?<![\w`@./])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:/[A-Za-z0-9_.-]+)?)\b")
_FENCE = re.compile(r"^\s*(```|~~~)")
_CRON = frozenset(
    {"yearly", "annually", "monthly", "weekly", "daily", "hourly", "midnight", "once", "reboot"}
)
_DECORATOR = re.compile(r"^\s*@[A-Za-z_][\w.]*(\(|$)")


def template(name: str) -> str:
    text = (
        resources.files("pr_management.code_review")
        .joinpath("templates", f"{name}.tmpl")
        .read_text(encoding="utf-8")
    )
    return re.sub(r"\A<!--.*?-->\n*", "", text, flags=re.DOTALL)


def footer(variant: str, project: str, contributing_url: str | None) -> str:
    text = template(f"footer-{variant}").replace("<PROJECT>", project)
    if contributing_url:
        return text.replace("<upstream_contributing_docs_url>", contributing_url).rstrip("\n")
    lines = text.rstrip("\n").splitlines()
    # No contributing-docs URL: drop the "More on how …" line, its link and the spacer before them.
    return "\n".join(lines[:-3]).rstrip("\n")


def _footer_regex(variant: str) -> re.Pattern[str]:
    raw = template(f"footer-{variant}").replace("<PROJECT>", " PROJECTSLOT ")
    raw = raw.replace("<upstream_contributing_docs_url>", " URLSLOT ")
    words = re.sub(r"[>*\[\]()]", " ", raw).split()
    parts = []
    for word in words:
        if word == "PROJECTSLOT":
            parts.append(r"\S+(?:\s+\S+){0,3}?")
        elif word == "URLSLOT":
            parts.append(r"\S+")
        else:
            parts.append(re.escape(word))
    return re.compile(r"\s+".join(parts) + r"\s*$", re.DOTALL)


def verify_footer(body: str, variant: str | None = None) -> dict[str, Any]:
    """Golden rule 5: does the body end with a verbatim footer (any variant, or the one named)?"""
    flat = re.sub(r"[>*\[\]()]", " ", body)
    variants = (
        [variant] if variant else ["approve", "request-changes", "comment-maintainer", "comment-role-neutral"]
    )
    for name in variants:
        if _footer_regex(name).search(flat):
            return {"footer_present": True, "variant": name, "action": "post"}
    return {"footer_present": False, "variant": None, "action": "block"}


def escape_handles(text: str) -> str:
    """Backtick every live `@handle` outside code, so posting it notifies nobody."""
    out = []
    inside = False
    for line in text.splitlines():
        if _FENCE.match(line):
            inside = not inside
            out.append(line)
            continue
        if inside or _DECORATOR.match(line):
            out.append(line)
            continue
        pieces = re.split(r"(`[^`]*`)", line)
        pieces = [p if p.startswith("`") else _MENTION.sub(lambda m: f"`@{m.group(1)}`", p) for p in pieces]
        out.append("".join(pieces))
    return "\n".join(out)


def mention_scan(text: str) -> list[dict[str, Any]]:
    """Live `@`-mentions outside code spans, fences, decorators and cron aliases."""
    hits = []
    inside = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            inside = not inside
            continue
        if inside or _DECORATOR.match(line):
            continue
        prose = re.sub(r"`[^`]*`", "", line)
        for match in _MENTION.finditer(prose):
            handle = match.group(1)
            if handle.lower() in _CRON:
                continue
            hits.append({"handle": handle, "line": number, "text": line.strip()})
    return hits


def pick(spec: str, count: int) -> dict[str, Any]:
    """The inline picker's answer: `A`, `N`, `1,3` (keep), `-2,-3` (drop), `E 2` (edit)."""
    spec = spec.strip()
    every = list(range(1, count + 1))
    if spec.upper() in ("", "A", "ALL"):
        return {"keep": every, "edit": None}
    if spec.upper() in ("N", "NONE"):
        return {"keep": [], "edit": None}
    edit = re.fullmatch(r"[Ee]\s*(\d+)", spec)
    if edit:
        index = int(edit.group(1))
        if not 1 <= index <= count:
            raise ValueError(f"no comment {index}; there are {count}")
        return {"keep": every, "edit": index}
    items = [p.strip() for p in spec.split(",") if p.strip()]
    if items and all(re.fullmatch(r"-\d+", p) for p in items):
        drop = {int(p[1:]) for p in items}
        bad = sorted(d for d in drop if not 1 <= d <= count)
        if bad:
            raise ValueError(f"no comment {bad[0]}; there are {count}")
        return {"keep": [i for i in every if i not in drop], "edit": None}
    if items and all(p.isdigit() for p in items):
        keep = sorted({int(p) for p in items})
        bad = [k for k in keep if not 1 <= k <= count]
        if bad:
            raise ValueError(f"no comment {bad[0]}; there are {count}")
        return {"keep": keep, "edit": None}
    raise ValueError(f"cannot read the picker answer {spec!r}: use A, N, 1,3, -2 or E 2")


def _where(finding: dict[str, Any]) -> str:
    line = finding.get("line")
    return f"`{finding['file']}:{line}`" if line else f"`{finding.get('file') or 'general'}`"


def _block(finding: dict[str, Any], prefix: str) -> str:
    lines = [
        f"### {prefix}{finding.get('rule_id') or finding.get('category') or 'Finding'} ({_where(finding)})",
        "",
    ]
    if finding.get("quoted_rule"):
        lines += ["> " + q for q in str(finding["quoted_rule"]).strip().splitlines()] + [""]
    if finding.get("excerpt"):
        lines += ["```text", str(finding["excerpt"]).rstrip(), "```", ""]
    if finding.get("explanation") or finding.get("suggestion"):
        lines += [str(finding.get("explanation") or finding.get("suggestion")).strip(), ""]
    if finding.get("suggestion_block"):
        lines += ["```suggestion", str(finding["suggestion_block"]).rstrip(), "```", ""]
    if finding.get("source") in ("adversarial", "both"):
        lines += [
            "*Flagged by both the primary and adversarial reviewers.*"
            if finding["source"] == "both"
            else f"*Flagged by {finding.get('reviewers') or 'the adversarial reviewer'} (adversarial review); "
            "cross-checked.*",
            "",
        ]
    return "\n".join(lines).rstrip()


def compose(
    *,
    summary: str,
    findings: list[dict[str, Any]],
    inline_kept: list[int],
    footer_text: str,
    reviewers: list[dict[str, Any]] | None = None,
    conflict_note: str | None = None,
    security_note: str | None = None,
) -> str:
    """The review body, in the template's section order; empty sections are omitted."""
    anchored = [i for i, f in enumerate(findings, start=1) if f.get("line")]
    inline_set = {anchored[k - 1] for k in inline_kept if 0 < k <= len(anchored)}
    parts = []
    if security_note:
        parts.append(security_note.strip())
    parts.append(summary.strip())
    if conflict_note:
        parts.append(conflict_note)
    blocking = [f for f in findings if f.get("severity") == "blocking"]
    major = [f for f in findings if f.get("severity") == "major"]
    smaller = [(i, f) for i, f in enumerate(findings, start=1) if f.get("severity") in ("minor", "nit")]
    parts += [_block(f, "Blocking — ") for f in blocking]
    parts += [_block(f, "") for f in major]
    folded = [f for i, f in smaller if i not in inline_set]
    inline_smaller = [f for i, f in smaller if i in inline_set]
    if folded or inline_smaller:
        bullets = [
            f"- {_where(f)} — {str(f.get('explanation') or f.get('rule_id') or '').strip()}" for f in folded
        ]
        if inline_smaller:
            bullets.append("- See inline comments on " + ", ".join(_where(f) for f in inline_smaller) + ".")
        parts.append("### Smaller observations\n\n" + "\n".join(bullets))
    if reviewers:
        rows = [f"- `@{r['login']}` — {r['reason']}" for r in reviewers]
        parts.append(
            "### Worth a second look from\n\nFolks with the most context on these paths:\n\n"
            + "\n".join(rows)
            + "\n\nNone of them have been notified — asking any of them for an\nextra pass is the maintainer's call, "
            "and optional."
        )
    parts.append(footer_text)
    return escape_handles("\n\n".join(p for p in parts if p))


def inline_comments(
    findings: list[dict[str, Any]], kept: list[int], files: list[difflib.DiffFile]
) -> dict[str, Any]:
    """The picked comments as review threads (line/side), and the ones the diff cannot anchor."""
    anchored = [f for f in findings if f.get("line")]
    threads, unanchorable = [], []
    for index in kept:
        if not 0 < index <= len(anchored):
            continue
        finding = anchored[index - 1]
        spot = difflib.anchor(
            files, str(finding["file"]), int(finding["line"]), str(finding.get("side") or "RIGHT")
        )
        text = escape_handles(
            str(finding.get("comment") or finding.get("explanation") or finding.get("rule_id") or "")
        )
        if spot is None:
            unanchorable.append({"index": index, "file": finding["file"], "line": finding["line"]})
            continue
        threads.append(
            {
                "path": spot["path"],
                "line": spot["line"],
                "side": spot["side"],
                "body": text,
                "position": spot["position"],
            }
        )
    return {"threads": threads, "unanchorable": unanchorable}


REVIEW_MUTATION = """mutation($pullRequestId: ID!, $event: PullRequestReviewEvent!, $body: String, $threads: [DraftPullRequestReviewThread!]) {
  addPullRequestReview(input: {pullRequestId: $pullRequestId, event: $event, body: $body, threads: $threads}) {
    pullRequestReview { id url }
  }
}"""


def review_payload(node_id: str, disposition: str, body: str, threads: list[dict[str, Any]]) -> str:
    """The `gh api graphql --input` document for a review with inline threads."""
    variables = {
        "pullRequestId": node_id,
        "event": disposition,
        "body": body,
        "threads": [
            {"path": t["path"], "line": t["line"], "side": t["side"], "body": t["body"]} for t in threads
        ],
    }
    return json.dumps({"query": REVIEW_MUTATION, "variables": variables}, indent=2, ensure_ascii=False)
