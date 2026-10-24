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
"""Bulk mode, orchestrator step 1: the selector, its `gh` reads, and the resolved set.

- `selector`: each comma-separated token as one query — `all` (open, plus
  the recently-closed `announced` bucket), `all open` / `open`, `closed
  announced`, `closed`, issue numbers and ranges, `CVE-…` IDs, a known
  label, or a title substring. A token that starts like a CVE ID but fails
  `^CVE-\\d{4}-\\d{4,7}$` makes the whole selector an error: nothing is
  searched, so no unvalidated text reaches a search argument.
- `resolve`: the queries' results as one ascending set — the
  `rejections-ledger` issue dropped from every set selector, the closed
  bucket cut to the last 90 days of `announced`, a CVE search kept only
  where the *CVE tool link* field names that CVE (read through
  github-body-field), a list that hit its `--limit` flagged as possibly
  incomplete, a title match always confirmed. `named` is what was named
  explicitly (numbers, CVE IDs): the pre-flight never skips those.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from github_body_field import parser as gbf

from security_management.shared import refs, selectors
from security_management.shared.rollup import one_line
from security_management.shell import dq, w

OPEN_LIMIT = 100
CLOSED_LIMIT = 50
CLOSED_WINDOW_DAYS = 90
LEDGER = "rejections-ledger"
ANNOUNCED = "announced"
CVE_FIELD = "CVE tool link"
_CVE_LIKE = re.compile(r"^CVE-", re.IGNORECASE)
_NUMBERISH = re.compile(r"^(?:#?\d+(?:-#?\d+)?|https://\S+|[\w.-]+/[\w.-]+#\d+)$")
_SET = {
    "all": ("open", "closed_announced"),
    "all open": ("open",),
    "open": ("open",),
    "closed announced": ("closed_announced",),
    "closed": ("open", "closed_all"),
}


def _list(tracker: str, kind: str, value: str = "") -> tuple[str, int]:
    base = f"gh issue list --repo {w(tracker)}"
    if kind == "open":
        return f"{base} --state open --limit {OPEN_LIMIT} --json number,title,labels", OPEN_LIMIT
    if kind == "closed_announced":
        return (
            f"{base} --state closed --label {dq(ANNOUNCED)} --limit {CLOSED_LIMIT} --json number,title,labels,closedAt",
            CLOSED_LIMIT,
        )
    if kind == "closed_all":
        return f"{base} --state closed --limit {OPEN_LIMIT} --json number,title,labels,closedAt", OPEN_LIMIT
    if kind == "label":
        return (
            f"{base} --state open --label {dq(value)} --limit {OPEN_LIMIT} --json number,title,labels",
            OPEN_LIMIT,
        )
    if kind == "title":
        return (
            f"{base} --state open --search {dq(value + ' in:title')} --limit {OPEN_LIMIT} --json number,title,labels",
            OPEN_LIMIT,
        )
    if kind == "cve":
        return f"gh search issues {dq(value)} --repo {w(tracker)} --json number,title,body", OPEN_LIMIT
    raise ValueError(kind)


def selector(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    text = str(data.get("invocation") or "").strip()
    text = re.sub(
        r"^/?(?:magpie-security:)?(?:security-)?(?:issue-)?sync\b", "", text, flags=re.IGNORECASE
    ).strip()
    no_preflight = bool(re.search(r"(?:^|\s)--no-preflight\b", text))
    text = re.sub(r"(?:^|\s)--no-preflight\b", " ", text).strip()
    known = {str(label).lower(): str(label) for label in data.get("known_labels") or []}
    tokens = [one_line(t) for t in text.split(",") if one_line(t)]
    if not tokens:
        return {"ok": False, "refused": "no selector given: ask which issues to sync"}
    invalid = [t for t in tokens if _CVE_LIKE.match(t) and not selectors.CVE.match(t.upper())]
    if invalid:
        return {
            "ok": True,
            "error": "invalid_cve_token",
            "invalid_tokens": invalid,
            "queries": [],
            "numbers": [],
            "message": "a CVE token failed validation (CVE-YYYY-NNNNN): nothing is searched; ask for the correct ID",
        }
    queries: list[dict[str, Any]] = []
    numbers: list[int] = []
    cves: list[str] = []

    def add(kind: str, value: str = "") -> None:
        command, limit = _list(tracker, kind, value)
        queries.append(
            {"id": f"q{len(queries) + 1}", "kind": kind, "value": value, "command": command, "limit": limit}
        )

    for token in tokens:
        lowered = token.lower()
        if lowered in _SET:
            for kind in _SET[lowered]:
                if not any(q["kind"] == kind for q in queries):
                    add(kind)
        elif _CVE_LIKE.match(token):
            cve_id = token.upper()
            if cve_id not in cves:
                cves.append(cve_id)
                add("cve", cve_id)
        elif all(_NUMBERISH.match(part) for part in token.split()):
            try:
                found = selectors.issue_numbers(token, tracker)
            except ValueError as exc:
                return {"ok": False, "refused": str(exc)}
            numbers.extend(n for n in found if n not in numbers)
        elif lowered in known:
            add("label", known[lowered])
        else:
            add("title", token)
    return {
        "ok": True,
        "error": None,
        "invalid_tokens": [],
        "queries": queries,
        "numbers": numbers,
        "searched_cve_ids": cves,
        "no_preflight": no_preflight,
    }


def _labels(item: Mapping[str, Any]) -> list[str]:
    value = item.get("labels") or []
    if isinstance(value, Mapping):
        value = value.get("nodes") or []
    return [str(v.get("name") if isinstance(v, Mapping) else v) for v in value]


def _time(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _cve_in_field(body: str, cve_id: str) -> bool:
    try:
        value = gbf.extract_field(body, CVE_FIELD)
    except gbf.FieldNotFoundError:
        return False
    return re.search(rf"(?<![\w-]){re.escape(cve_id)}(?![\w-]|\d)", value) is not None


def resolve(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    now = _time(data["now"])
    results: Mapping[str, Sequence[Mapping[str, Any]]] = data.get("results") or {}
    named = [int(n) for n in data.get("numbers") or []]
    from_sets: list[int] = []
    from_cves: list[int] = []
    confirm: list[int] = []
    warnings: list[str] = []
    groups = {"open": 0, "recently_closed": 0}
    for query in data.get("queries") or []:
        rows = results.get(query["id"])
        if rows is None:
            return {"ok": False, "refused": f"no result for {query['id']} ({query['command']})"}
        if len(rows) >= int(query["limit"]) and query["kind"] != "cve":
            warnings.append(
                f"`{query['command']}` hit its {query['limit']}-issue cap — the set may be incomplete"
            )
        for row in rows:
            number = int(row["number"])
            labels = _labels(row)
            kind = query["kind"]
            if kind == "cve":
                if _cve_in_field(str(row.get("body") or ""), str(query["value"])) and number not in from_cves:
                    from_cves.append(number)
                continue
            if LEDGER in labels:
                continue
            if kind == "closed_announced":
                if ANNOUNCED not in labels or not row.get("closedAt"):
                    continue
                if _time(row["closedAt"]) <= now - timedelta(days=CLOSED_WINDOW_DAYS):
                    continue
                groups["recently_closed"] += number not in from_sets
            elif kind == "open":
                groups["open"] += number not in from_sets
            if kind == "title" and number not in confirm:
                confirm.append(number)
            if number not in from_sets:
                from_sets.append(number)
    explicit = sorted({*named, *from_cves})
    resolved = sorted({*explicit, *from_sets})
    if not resolved:
        return {
            "ok": True,
            "resolved": [],
            "explicit": [],
            "message": "the selector resolved to no issue: say so and stop; never fall back to `sync all`",
            "warnings": warnings,
        }
    parts = [f"{groups['open']} open"] if groups["open"] else []
    if groups["recently_closed"]:
        parts.append(f"{groups['recently_closed']} recently-closed awaiting cve.org")
    links = ", ".join(refs.tracker_link(tracker, n) for n in resolved)
    echo = f"Sync {len(resolved)} tracker(s){' (' + ', '.join(parts) + ')' if parts else ''}: {links}."
    if confirm:
        echo += (
            " Title matches to confirm: "
            + ", ".join(refs.tracker_link(tracker, n) for n in sorted(confirm))
            + "."
        )
    for warning in warnings:
        echo += f"\n{warning}; offer a larger `--limit` before dispatching."
    return {
        "ok": True,
        "resolved": resolved,
        "explicit": explicit,
        "title_matches": sorted(confirm),
        "groups": groups,
        "warnings": warnings,
        "echo": echo,
        "bare_refs": refs.bare_refs(echo),
    }
