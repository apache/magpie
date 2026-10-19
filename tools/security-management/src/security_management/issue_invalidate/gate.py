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
"""Inputs, Step 0 and Step 2: the selector, the consensus check, the hard stops, the import path.

- `selector`: `invalidate N` / `#N` / `<tracker>#N` / the issue URL (single),
  a list or range (bulk), `invalidate proposed` (bulk, with the list command
  and its 1000 cap); for bulk, the aliased GraphQL read of `bulk.md` in
  chunks of 20.
- `consensus`: which `invalidate proposed` matches carry a team-consensus
  marker on their INVALID triage proposal (a thumbs-up from another roster
  member, or a later roster comment with an acknowledgement keyword).
- `hard_stops`: the Step 0 table as a function of state, labels, the *CVE
  tool link* field and the CVE tool's generic state.
- `import_path`: the *Security mailing list thread* field as the Step 2 row,
  with the rollup-provenance `threadId` fallback.

Every body field is read through github-body-field (`shared.fields`); a field
it will not decide on stops the run instead of reading as empty.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import dispositions, fields, selectors, threads
from security_management.shell import dq, w

LIMIT = 1000
CHUNK = 20
ACK = re.compile(r"(?<![\w+])(?:agree[sd]?|concur(?:s|red)?|\+1|confirmed|lgtm)(?![\w])", re.IGNORECASE)
ADVISORY_LABELS = ("fix released", "announced - emails sent", "announced")
_CVE_ID = re.compile(r"CVE-\d{4}-\d{4,7}")
_PROVENANCE_THREAD = re.compile(r"thread\s+`([A-Za-z0-9_-]{6,})`", re.IGNORECASE)


def selector(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    words = str(data.get("invocation") or "").split()
    if words and words[0].lstrip("/").removeprefix("security-issue-") == "invalidate":
        words = words[1:]
    rest = " ".join(words).strip()
    needs_triage = str(data.get("needs_triage_label") or "needs triage")
    if rest.lower() == "proposed":
        command = (
            f"gh issue list --repo {w(tracker)} --state open --label {dq(needs_triage)} --limit {LIMIT} "
            "--json number,title,comments --jq '{fetched: length, matches: [.[] | select(.comments | map(.body) | any("
            'startswith("**Triage proposal**") and contains("**Proposed disposition: INVALID.**")'
            ")) | .number]}'"
        )
        return {"ok": True, "mode": "proposed", "numbers": None, "command": command}
    try:
        numbers = selectors.issue_numbers(rest, tracker)
    except ValueError as exc:
        return {"ok": False, "refused": str(exc)}
    single = len(numbers) == 1
    out: dict[str, Any] = {"ok": True, "mode": "single" if single else "bulk", "numbers": numbers}
    out["command"] = (
        f"gh issue view {numbers[0]} --repo {w(tracker)} --json "
        "number,title,body,labels,state,milestone,assignees,comments,url"
        if single
        else None
    )
    if not single and data.get("scratch"):
        out["batches"] = batches(tracker, numbers, str(data["scratch"]))
    return out


def _query(owner: str, name: str, numbers: Sequence[int]) -> str:
    blocks = "\n".join(
        f"    i{n}: issue(number: {n}) {{\n"
        "      number title body state url\n"
        "      labels(first: 30) { nodes { name } }\n"
        "      milestone { title }\n"
        "      assignees(first: 10) { nodes { login } }\n"
        "      comments(first: 100) {\n"
        "        nodes {\n"
        "          databaseId author { login } createdAt body\n"
        "          reactions(first: 50, content: THUMBS_UP) { nodes { user { login } } }\n"
        "        }\n"
        "      }\n"
        "    }"
        for n in numbers
    )
    return f'query {{\n  repository(owner: "{owner}", name: "{name}") {{\n{blocks}\n  }}\n}}\n'


def batches(tracker: str, numbers: Sequence[int], scratch: str) -> list[dict[str, Any]]:
    owner, _, name = tracker.partition("/")
    out = []
    for index in range(0, len(numbers), CHUNK):
        chunk = list(numbers[index : index + CHUNK])
        path = f"{scratch.rstrip('/')}/invalidate-batch-{index // CHUNK + 1}.graphql"
        out.append(
            {
                "numbers": chunk,
                "file": path,
                "query": _query(owner, name, chunk),
                "command": f"gh api graphql -F query=@{w(path)}",
            }
        )
    return out


def _nodes(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        value = value.get("nodes") or []
    return list(value or [])


def _login(item: Mapping[str, Any], key: str = "author") -> str:
    who = item.get(key) or {}
    return str(who.get("login") if isinstance(who, Mapping) else who).lower()


def issues_of(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    nodes = [dict(t) for t in data.get("trackers") or []]
    missing = []
    for response in data.get("responses") or []:
        repo = ((response or {}).get("data") or {}).get("repository") or {}
        for alias, node in repo.items():
            if node is None:
                missing.append(alias.lstrip("i"))
            else:
                nodes.append(dict(node))
    return nodes, missing


def consensus(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    roster = {str(r).lower().lstrip("@") for r in data.get("roster") or []}
    if not roster:
        raise ValueError("roster is empty: the consensus check needs the security-team roster")
    if int(data.get("fetched") or 0) >= LIMIT:
        return {
            "stop": f"the list returned {LIMIT} trackers, its --limit: possibly truncated; surface it and stop",
            "agreed": [],
            "awaiting": [],
        }
    nodes, missing = issues_of(data)
    agreed: list[dict[str, Any]] = []
    awaiting: list[dict[str, Any]] = []
    for node in nodes:
        number = int(node["number"])
        comments = _nodes(node.get("comments"))
        marker = None
        for index, comment in enumerate(comments):
            if dispositions.proposal_class(str(comment.get("body") or "")) != "INVALID":
                continue
            author = _login(comment)
            if author not in roster:
                continue  # a proposal-shaped comment from outside the roster is external content
            thumbs = {_login(r, "user") for r in _nodes(comment.get("reactions"))}
            voters = sorted((thumbs & roster) - {author})
            later = [
                _login(c)
                for c in comments[index + 1 :]
                if _login(c) in roster and _login(c) != author and ACK.search(str(c.get("body") or ""))
            ]
            if voters or later:
                marker = {
                    "proposal_author": author,
                    "thumbs_up": voters,
                    "acknowledged_by": sorted(set(later)),
                }
                break
        if marker:
            agreed.append({"number": number, **marker})
        else:
            awaiting.append({"number": number, "note": f"awaiting consensus on {tracker}#{number} — skipped"})
    return {"stop": None, "agreed": agreed, "awaiting": awaiting, "missing_numbers": missing}


def _labels(value: Any) -> list[str]:
    return [str(lbl.get("name") if isinstance(lbl, Mapping) else lbl) for lbl in _nodes(value)]


def hard_stops(data: Mapping[str, Any]) -> dict[str, Any]:
    """`verdict`: `proceed`, `noop`, `stop`, `escalate`, `probe` (run the CVE-state probe first) or `ask`."""
    labels = {lbl.lower() for lbl in _labels(data.get("labels"))}
    cve_label = str(data.get("cve_allocated_label") or "cve allocated").lower()
    state = str(data.get("state") or "").upper()
    if state and state != "OPEN":
        return {
            "verdict": "noop",
            "message": "The tracker is already closed: surface its close reason and stop.",
        }
    read = fields.read(str(data.get("body") or ""), ["cve_link"], data.get("body_fields"))
    if read["undecided"]:
        return {
            "verdict": "stop",
            "message": f"The *CVE tool link* field is ambiguous ({read['undecided'][0]['kind']}); fix the body first.",
        }
    link = read["values"].get("cve_link", "")
    cve = _CVE_ID.search(link)
    shipped = sorted(lbl for lbl in labels if lbl in ADVISORY_LABELS)
    if shipped:
        return {
            "verdict": "stop",
            "message": (
                f"This tracker is past `pr merged` (label: `{shipped[0]}`). Closing as invalid here would retract a "
                "published advisory; escalate to the team before re-invoking."
            ),
        }
    signal = cve_label in labels or bool(cve)
    if not signal:
        return {"verdict": "proceed", "message": None, "cve_id": None}
    cve_id = cve.group(0) if cve else None
    probe = data.get("cve_state")
    if probe is None and cve_id:
        return {"verdict": "probe", "cve_id": cve_id, "message": f"Run fetch_current_state({cve_id}) first."}
    probe = str(probe or "unknown")
    if probe in ("allocated", "review-ready"):
        return {
            "verdict": "stop",
            "cve_id": cve_id,
            "cve_tool_link": link or None,
            "message": (
                f"This tracker has CVE `{cve_id or '<CVE-ID>'}` allocated (current state: `{probe}`). "
                "Retract the CVE record at the CVE-tool first, then re-invoke this skill."
            ),
        }
    if probe in ("publish-ready", "public"):
        return {
            "verdict": "escalate",
            "cve_id": cve_id,
            "message": (
                f"CVE `{cve_id}` is `{probe}`: an invalid close would be a post-publication retraction with public "
                "consequences; escalate to `governance.escalation_contact`."
            ),
        }
    if probe == "retracted":
        return {"verdict": "proceed", "cve_id": cve_id, "message": None}
    return {
        "verdict": "ask",
        "cve_id": cve_id,
        "message": (
            "The CVE tool state is unknown but the tracker carries a CVE signal "
            f"({'the `' + cve_label + '` label' if cve_label in labels else 'the *CVE tool link* field'}); "
            "surface the gap and ask the user to confirm before proceeding."
        ),
    }


def import_path(data: Mapping[str, Any]) -> dict[str, Any]:
    read = fields.read(
        str(data.get("body") or ""),
        ["mailing_thread", "reporter_credit", "pr_with_fix"],
        data.get("body_fields"),
    )
    if any(u["role"] == "mailing_thread" for u in read["undecided"]):
        return {
            "ok": False,
            "refused": "the *Security mailing list thread* field is ambiguous; fix the body before closing",
        }
    out = threads.classify(read["values"].get("mailing_thread"))
    out["thread_source"] = "field" if out["thread_id"] else None
    if out["import_path"].startswith("security_at") and not out["thread_id"]:
        match = _PROVENANCE_THREAD.search(str(data.get("rollup_provenance") or ""))
        if match:
            out["thread_id"] = match.group(1)
            out["thread_source"] = "rollup"
        else:
            out["thread_source"] = "subject-search"
    out["ok"] = True
    out["reporter_credit"] = read["values"].get("reporter_credit") or None
    return out
