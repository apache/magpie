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
"""The pre-mutation guards, decided from two fresh reads taken just before the mutation.

* `liveness-<N>.json` — `gql-pr-liveness <N>`: the head SHA and the live
  mergeability, for the optimistic lock and the conflict guards.
* `runs-head-<N>.json` — `runs-at-head <head_sha>`: every workflow run on the
  head, for Golden rule 1b (never mark ready while approval is pending), the
  approve-workflow re-list and the rerun run list.

GraphQL computes `mergeable` lazily, so `UNKNOWN` is "not yet known", never
"no conflict": every guard that reads it refuses on it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LABEL_ACTIONS = frozenset({"mark-ready", "promote-bot-draft"})


def load_liveness(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pull = ((data.get("data") or {}).get("repository") or {}).get("pullRequest") or {}
    return {
        "head_sha": pull.get("headRefOid"),
        "mergeable": pull.get("mergeable") or "UNKNOWN",
        "merge_state": pull.get("mergeStateStatus"),
    }


def load_runs(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    pages = document if isinstance(document, list) else [document]
    return [run for page in pages for run in (page or {}).get("workflow_runs") or []]


def check(
    action: str,
    *,
    expected_head: str,
    liveness: dict[str, Any] | None,
    runs: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """`proceed` and, when refused, the `reason` and where the PR goes instead (`reroute`)."""
    result: dict[str, Any] = {"action": action, "proceed": True}

    def refuse(reason: str, reroute: str | None) -> dict[str, Any]:
        result.update(proceed=False, reason=reason, reroute=reroute)
        return result

    needs_liveness = action in LABEL_ACTIONS | {"rebase"} or liveness is not None
    if needs_liveness:
        if liveness is None:
            return refuse("the live PR state was not read; save gql-pr-liveness first", None)
        head = liveness.get("head_sha") or ""
        if (
            expected_head
            and head
            and not head.startswith(expected_head)
            and not expected_head.startswith(head)
        ):
            return refuse(
                f"the head moved ({expected_head[:7]} → {head[:7]}) — re-classify this PR", "reclassify"
            )
    if action in LABEL_ACTIONS | {"approve-workflow", "rerun"} and runs is None:
        return refuse("the head's workflow runs were not read; save runs-at-head first", None)

    pending = [r for r in runs or [] if r.get("conclusion") == "action_required"]
    if action in LABEL_ACTIONS:
        if pending:
            return refuse(
                f"{len(pending)} workflow run(s) awaiting approval at the head — not ready for review",
                "pending_workflow_approval",
            )
        assert liveness is not None
        if liveness["mergeable"] == "CONFLICTING" or liveness.get("merge_state") == "DIRTY":
            return refuse("the PR is conflicting — route to draft (row 9)", "draft")
        if liveness["mergeable"] == "UNKNOWN":
            return refuse("mergeability not yet computed — retry next sweep", "retry")
    elif action == "rebase":
        assert liveness is not None
        if liveness["mergeable"] == "CONFLICTING":
            return refuse("CONFLICTING — route to draft instead", "draft")
        if liveness["mergeable"] == "UNKNOWN":
            return refuse("mergeability not yet computed — retry next sweep", "retry")
    elif action == "approve-workflow":
        ids = [r.get("id") for r in pending]
        if not ids:
            result.update(
                proceed=False, reason="no pending runs at the head — already approved", reroute=None
            )
            return result
        result["run_ids"] = ids
    elif action == "rerun":
        completed_failed = [
            r.get("id")
            for r in runs or []
            if r.get("status") == "completed" and r.get("conclusion") in ("failure", "timed_out")
        ]
        in_progress = [r.get("id") for r in runs or [] if r.get("status") in ("in_progress", "queued")]
        if completed_failed:
            result["rerun_failed"] = completed_failed
        elif in_progress:
            result["cancel_and_rerun"] = in_progress
        else:
            return refuse("no workflow runs found at the head — the PR may need a push or a rebase", "rebase")
    return result
