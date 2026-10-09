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
"""The JSON the skill reads: groups in presentation order, follow-up reads, documents to load."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..config import Config
from ..model import PR
from .classify import ACTION_DOCS, DESTRUCTIVE, GROUP_ORDER, ROW_DOCS, Decision

#: Actions that deliver a contributor-facing note, and the recipe they share.
NOTE_ACTIONS = frozenset(
    {"draft", "comment", "close", "ping", "request-author-confirmation", "close-stale", "strip-ready-label"}
)
DELIVER_NOTE = "actions/deliver-note.md"

#: More stale-sweep candidates than this and the maintainer is asked before the run continues.
SWEEP_ALARM = 50

#: The longest untrusted excerpt (an author reply) carried into the output.
EXCERPT = 400


def _pr(pr: PR, cfg: Config) -> dict[str, Any]:
    prefix = cfg.area_label_prefix or ""
    return {
        "number": pr.number,
        "title": pr.title,
        "url": pr.url,
        "author": pr.author,
        "association": pr.association,
        "draft": pr.is_draft,
        "head_sha": pr.head_sha,
        "base": pr.base,
        "areas": [lbl for lbl in pr.labels if prefix and lbl.startswith(prefix)],
        "size": f"+{pr.additions}/-{pr.deletions}",
    }


def _entry(d: Decision, cfg: Config) -> dict[str, Any]:
    entry = {**_pr(d.pr, cfg), "row": d.row, "reason": d.reason}
    details = {k: v for k, v in d.details.items() if v not in (None, [], {}, False)}
    reply = details.pop("author_reply", None)
    if reply:
        entry["author_reply_untrusted"] = reply[:EXCERPT]
    if details:
        entry["details"] = details
    return entry


def build(decisions: list[Decision], cfg: Config, *, viewer: str, pages: int) -> dict[str, Any]:
    acting = [d for d in decisions if d.outcome == "act"]
    grouped: dict[tuple[str, str], list[Decision]] = {}
    for d in acting:
        grouped.setdefault((d.classification or "", d.action or ""), []).append(d)
    order = {key: i for i, key in enumerate(GROUP_ORDER)}
    groups = []
    load: list[str] = []
    for key in sorted(grouped, key=lambda k: (order.get(k, len(order)), k)):
        members = grouped[key]
        docs: list[str] = []
        for d in members:
            doc = ROW_DOCS.get(d.row or "")
            if doc and doc not in docs:
                docs.append(doc)
        action_doc = ACTION_DOCS.get(key[1])
        if action_doc:
            docs.append(action_doc)
        if key[1] in NOTE_ACTIONS:
            docs.append(DELIVER_NOTE)
        load += [doc for doc in docs if doc not in load]
        groups.append(
            {
                "classification": key[0],
                "action": key[1],
                "batchable": key[1] not in DESTRUCTIVE and key[0] != "pending_workflow_approval",
                "docs": docs,
                "prs": [_entry(d, cfg) for d in sorted(members, key=lambda d: d.pr.number)],
            }
        )

    needs: list[dict[str, Any]] = []
    for d in decisions:
        if d.outcome == "needs":
            for need in d.needs:
                needs.append({**need, "pr": d.pr.number, "why": d.reason})
    skipped = [
        {"number": d.pr.number, "row": d.row, "classification": d.classification, "reason": d.reason}
        for d in decisions
        if d.outcome == "skip"
    ]
    filtered = Counter(d.filter for d in decisions if d.outcome == "filtered")
    sweep_count = sum(1 for d in acting if (d.row or "").startswith("sweep-"))
    warnings = list(cfg.warnings)
    if sweep_count > SWEEP_ALARM:
        warnings.append(
            f"the stale sweeps surfaced {sweep_count} candidates — more than {SWEEP_ALARM} usually means a "
            "previous sweep never ran or a freeze piled up activity; ask the maintainer before continuing"
        )
    return {
        "viewer": viewer,
        "pages": pages,
        "fetched": len(decisions),
        "counts": {
            "act": len(acting),
            "skip": len(skipped),
            "filtered": sum(filtered.values()),
            "suppressed": sum(1 for d in decisions if d.outcome == "suppressed"),
            "needs": len({n["pr"] for n in needs}),
            "sweep_candidates": sweep_count,
        },
        "filtered": dict(sorted(filtered.items())),
        "needs": needs,
        "groups": groups,
        "skipped": skipped,
        "load": load,
        "config": {
            "feedback_channel": cfg.feedback_channel,
            "handback_mode": cfg.handback_mode,
            "ready_label": cfg.ready_label,
            "warnings": warnings,
        },
    }
