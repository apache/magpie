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
"""Steps 1 and 2: the selector, the queue it resolves to, and the batched state read.

- `resolve` parses the invocation (`triage`, `triage #N…`, ranges,
  `triage scope:<label>`, `triage CVE-…`, `--retriage`, `--no-preflight`)
  into a query and the plain `gh` command that runs it. A malformed CVE
  token, a scope label the project does not declare and a bare
  `--retriage` are hard errors.
- `queue` checks what the query returned against the Step 1 stop cases
  (empty, the 1000 cap, a CVE matching several trackers, `--retriage` over
  50), prints the one-line echo, and the item 1 GraphQL batches: chunks of
  at most 20 aliased issues, each a query file holding only numbers and the
  tracker's owner/name.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import selectors
from security_management.shell import dq, w

LIMIT = 1000
RETRIAGE_CONFIRM = 50
CHUNK = 20
_SCOPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/-]{0,49}$")
_LIST_FIELDS = "number,title,labels,updatedAt"


def _result(action: str, **values: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "action": action,
        "issue_numbers": None,
        "scope_label": None,
        "cve_token": None,
        "retriage": False,
        "no_preflight": False,
        "explicit": False,
        "command": None,
        "error": None,
    }
    base.update(values)
    return base


def resolve(data: Mapping[str, Any]) -> dict[str, Any]:
    """The query for `data["invocation"]`; `action` is `list_query`, `verbatim`, `cve_search` or `error`."""
    tracker = str(data["tracker"])
    needs_triage = str(data.get("needs_triage_label") or "needs triage")
    scopes = [str(s) for s in data.get("scope_labels") or []]
    words = str(data.get("invocation") or "").split()
    if words and words[0].lstrip("/").removeprefix("security-issue-") == "triage":
        words = words[1:]
    flags = {"retriage": "--retriage" in words, "no_preflight": "--no-preflight" in words}
    rest = " ".join(w_ for w_ in words if w_ not in ("--retriage", "--no-preflight")).strip()
    unknown = [w_ for w_ in rest.split() if w_.startswith("--")]
    if unknown:
        return _result("error", error=f"unknown flag {unknown[0]}", **flags)
    if not rest:
        if flags["retriage"]:
            return _result("error", error="no selector provided — expected 'triage [<selector>]'", **flags)
        command = (
            f"gh issue list --repo {w(tracker)} --state open --label {dq(needs_triage)} "
            f"--limit {LIMIT} --json {_LIST_FIELDS}"
        )
        return _result("list_query", command=command, **flags)
    if rest.lower().startswith("scope:"):
        label = rest[len("scope:") :].strip()
        if not _SCOPE.match(label):
            return _result("error", error=f"scope label {label!r} is not a plain label name", **flags)
        if scopes and label not in scopes:
            return _result("error", error=f"scope label {label!r} is not one of {', '.join(scopes)}", **flags)
        triage_filter = "" if flags["retriage"] else f"--label {dq(needs_triage)} "
        command = (
            f"gh issue list --repo {w(tracker)} --state open {triage_filter}--label {dq(label)} "
            f"--limit {LIMIT} --json {_LIST_FIELDS}"
        )
        return _result("list_query", scope_label=label, command=command, **flags)
    if rest.upper().startswith("CVE"):
        token = rest.strip()
        if not selectors.CVE.match(token):
            return _result("error", error=f"{token} does not match expected format CVE-YYYY-NNNNN", **flags)
        command = (
            f"gh search issues {dq(token)} --repo {w(tracker)} --match body --json number,title "
            "--jq '.[] | .number'"
        )
        return _result("cve_search", cve_token=token, command=command, **flags)
    try:
        numbers = selectors.issue_numbers(rest, tracker)
    except ValueError as exc:
        return _result("error", error=str(exc), **flags)
    return _result("verbatim", issue_numbers=numbers, explicit=True, **flags)


def _graphql(owner: str, name: str, numbers: Sequence[int]) -> str:
    blocks = "\n".join(
        f"    i{n}: issue(number: {n}) {{\n"
        "      number title body updatedAt\n"
        "      labels(first: 30) { nodes { name } }\n"
        "      milestone { title }\n"
        "      assignees(first: 10) { nodes { login } }\n"
        "      comments(last: 10) { nodes { author { login } createdAt body } }\n"
        "      closedByPullRequestsReferences(first: 10, includeClosedPrs: true) {\n"
        "        nodes { number url state mergedAt repository { nameWithOwner } }\n"
        "      }\n"
        "    }"
        for n in numbers
    )
    return f'query {{\n  repository(owner: "{owner}", name: "{name}") {{\n{blocks}\n  }}\n}}\n'


def batches(
    tracker: str, numbers: Sequence[int], scratch: str, prefix: str = "triage"
) -> list[dict[str, Any]]:
    """The item 1 read: one aliased query per chunk of up to 20 issues, run as `-F query=@<file>`."""
    owner, _, name = tracker.partition("/")
    if not owner or not name:
        raise ValueError(f"tracker {tracker!r} is not owner/name")
    out = []
    for index in range(0, len(numbers), CHUNK):
        chunk = list(numbers[index : index + CHUNK])
        path = f"{scratch.rstrip('/')}/{prefix}-batch-{index // CHUNK + 1}.graphql"
        out.append(
            {
                "numbers": chunk,
                "file": path,
                "query": _graphql(owner, name, chunk),
                "command": f"gh api graphql -F query=@{w(path)}",
            }
        )
    return out


def _date(item: Mapping[str, Any]) -> str:
    return str(item.get("updatedAt") or "")[:10]


def queue(data: Mapping[str, Any]) -> dict[str, Any]:
    """Step 1's stop cases, the echo line, and the item 1 batches for what the query returned."""
    selection: Mapping[str, Any] = data["selection"]
    action = selection["action"]
    if action == "error":
        return {"stop": "error", "message": selection.get("error"), "numbers": [], "batches": []}
    issues: list[Mapping[str, Any]] = list(data.get("issues") or [])
    if action == "verbatim":
        numbers = [int(n) for n in selection["issue_numbers"]]
    elif action == "cve_search":
        numbers = [int(n) for n in data.get("cve_matches") or []]
    else:
        numbers = [int(i["number"]) for i in issues]
    stop = None
    message = None
    if not numbers:
        stop, message = "empty", "the selector returned no trackers; nothing to triage (no wider fallback)"
    elif action == "list_query" and len(issues) >= LIMIT:
        stop = "limit"
        message = (
            f"the list returned {len(issues)} trackers, the --limit {LIMIT} cap: "
            "a needs-triage backlog this size is a triage-cadence problem; surface it and stop"
        )
    elif action == "cve_search" and len(numbers) > 1:
        stop, message = (
            "ask",
            f"{selection['cve_token']} matches {len(numbers)} trackers; ask which one is intended",
        )
    elif selection.get("retriage") and len(numbers) > RETRIAGE_CONFIRM and not data.get("confirmed"):
        stop, message = "confirm", f"--retriage over {len(numbers)} trackers; confirm once before proceeding"
    scope = selection.get("scope_label") or ("explicit" if selection.get("explicit") else "needs triage")
    dates = sorted(_date(i) for i in issues if _date(i))
    echo = f"{len(numbers)} tracker(s), scope: {scope}"
    if dates:
        echo += f", oldest update {dates[0]}, newest {dates[-1]}"
    scratch = str(data.get("scratch") or "")
    return {
        "stop": stop,
        "message": message,
        "numbers": numbers,
        "echo": echo,
        "batches": batches(str(data["tracker"]), numbers, scratch)
        if numbers and not stop and scratch
        else [],
    }
