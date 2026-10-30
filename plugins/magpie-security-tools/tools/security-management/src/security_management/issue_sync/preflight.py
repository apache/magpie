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
"""Bulk mode, orchestrator step 1b: the batched state read and the no-op classifier.

`query` writes one aliased GraphQL read per 50 trackers (state, dates,
labels, the last comment). `classify` applies the rule table of
`bulk-mode.md` in order, first match wins:

1. last comment by a human within 24h — `dispatch-urgent`;
2. updated within 7 days, last comment by a human — `dispatch`;
3. closed over 30 days ago with `announced` — `skip-noop` (post-announce);
4. closed over 90 days ago without `announced` — `skip-noop` (stale closed);
5. open, `cve allocated` + `pr merged` + `announced`, last comment skill-or-bot — `skip-noop`;
6. open, `cve allocated` + `pr merged`, last comment skill-or-bot — `skip-noop` (awaiting release);
7. open, `cve allocated` + `fix released`, last comment skill-or-bot — `skip-noop`;
8. anything else — `dispatch`.

*Skill-or-bot*: a `[bot]` login, a body starting with the
`<!-- apache-magpie: ` marker (the skill posts as the operator), or a
configured `bot_logins` entry. A tracker named explicitly is classified for
the recap's context but never skipped, and `--no-preflight` dispatches all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from security_management.issue_sync.select import _labels, _time
from security_management.shared import refs
from security_management.shell import w

CHUNK = 50
MARKER = "<!-- apache-magpie: "
REASONS = {
    "post_announce_cve_published": "post-announce; CVE published",
    "stale_closed": "stale closed (invalid/duplicate/abandoned)",
    "all_phases_done_awaiting_closure": "all phases done; awaiting closure heuristic",
    "awaiting_release": "awaiting release",
    "fix_released_awaiting_advisory": "fix released; awaiting advisory propagation",
}


def query(data: Mapping[str, Any]) -> dict[str, Any]:
    owner, _, name = str(data["tracker"]).partition("/")
    numbers = [int(n) for n in data.get("numbers") or []]
    scratch = str(data["scratch"]).rstrip("/")
    out = []
    for index in range(0, len(numbers), CHUNK):
        chunk = numbers[index : index + CHUNK]
        blocks = "\n".join(
            f"    i{n}: issue(number: {n}) {{\n"
            "      number state closedAt updatedAt\n"
            "      labels(first: 30) { nodes { name } }\n"
            "      comments(last: 1) { nodes { author { login } createdAt body } }\n"
            "    }"
            for n in chunk
        )
        path = f"{scratch}/sync-preflight-{index // CHUNK + 1}.graphql"
        out.append(
            {
                "numbers": chunk,
                "file": path,
                "query": f'query {{\n  repository(owner: "{owner}", name: "{name}") {{\n{blocks}\n  }}\n}}\n',
                "command": f"gh api graphql -F query=@{w(path)}",
            }
        )
    return {"ok": True, "batches": out}


def _nodes(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    nodes = list(data.get("issues") or [])
    for response in data.get("responses") or []:
        repo = ((response or {}).get("data") or {}).get("repository") or {}
        nodes.extend(node for node in repo.values() if node)
    return nodes


def skill_or_bot(comment: Mapping[str, Any] | None, bot_logins: Sequence[str]) -> bool:
    if not comment:
        return True  # no comment: nothing human to answer
    author = comment.get("author") or {}
    login = str(author.get("login") or "") if isinstance(author, Mapping) else str(author)
    if login.endswith("[bot]") or login in bot_logins:
        return True
    return str(comment.get("body") or "").startswith(MARKER)


def decide(node: Mapping[str, Any], now: datetime, bot_logins: Sequence[str]) -> tuple[str, str | None]:
    labels = set(_labels(node))
    comments = node.get("comments") or {}
    if isinstance(comments, Mapping):
        comments = comments.get("nodes") or []
    last = comments[-1] if comments else None
    human = not skill_or_bot(last, bot_logins)
    opened = str(node.get("state") or "").upper() == "OPEN"
    if human and last and last.get("createdAt") and _time(last["createdAt"]) > now - timedelta(hours=24):
        return "dispatch-urgent", None
    if human and node.get("updatedAt") and _time(node["updatedAt"]) > now - timedelta(days=7):
        return "dispatch", None
    if not opened and node.get("closedAt"):
        closed = _time(node["closedAt"])
        if "announced" in labels and closed < now - timedelta(days=30):
            return "skip-noop", "post_announce_cve_published"
        if "announced" not in labels and closed < now - timedelta(days=90):
            return "skip-noop", "stale_closed"
    if opened and not human:
        if {"cve allocated", "pr merged", "announced"} <= labels:
            return "skip-noop", "all_phases_done_awaiting_closure"
        if {"cve allocated", "pr merged"} <= labels:
            return "skip-noop", "awaiting_release"
        if {"cve allocated", "fix released"} <= labels:
            return "skip-noop", "fix_released_awaiting_advisory"
    return "dispatch", None


def classify(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    now = _time(data["now"])
    bots = [str(b) for b in data.get("bot_logins") or []]
    explicit = {int(n) for n in data.get("explicit") or []}
    no_preflight = bool(data.get("no_preflight"))
    rows = []
    for node in sorted(_nodes(data), key=lambda n: int(n["number"])):
        number = int(node["number"])
        decision, rule = decide(node, now, bots)
        would_skip = decision == "skip-noop"
        if would_skip and (number in explicit or no_preflight):
            decision = "dispatch"
        rows.append(
            {
                "issue": number,
                "decision": decision,
                "rule": rule,
                "named_but_idle": would_skip and decision == "dispatch",
            }
        )
    dispatched = [r["issue"] for r in rows if r["decision"] != "skip-noop"]
    urgent = [r["issue"] for r in rows if r["decision"] == "dispatch-urgent"]
    skipped = [{"issue": r["issue"], "rule": r["rule"]} for r in rows if r["decision"] == "skip-noop"]
    lines = [f"- {refs.tracker_link(tracker, s['issue'])} — {REASONS[str(s['rule'])]}" for s in skipped]
    return {
        "ok": True,
        "rows": rows,
        "dispatched": dispatched,
        "urgent": urgent,
        "skipped": skipped,
        "skipped_text": ("Pre-flight skipped\n" + "\n".join(lines) + "\n") if lines else "",
    }
