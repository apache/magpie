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
"""Workflow runs held in `action_required` at a PR head, and how to release them.

The approve(+fixup)+auto-merge path relies on GitHub to hold the merge until the
required checks pass, which only works if those checks run. A push — the fixup,
or the contributor's own — can leave the head's runs held for approval, so the
flow reads the runs *at the head* (`runs-at-head <sha>`; the repository-wide
`runs-action-required` list is capped at 1000 and can miss them) and releases
each one before relying on auto-merge.

GitHub's approve endpoint only accepts runs from first-time contributors. Any
other held run answers HTTP 403 "This workflow run is not waiting for approval"
and needs a full re-run instead; a re-run that answers "already running" is done.
"""

from __future__ import annotations

from typing import Any

APPROVE_OP = "workflow-approve"
RERUN_OP = "run-rerun"
_NOT_WAITING = "not waiting for approval"
_ALREADY_RUNNING = "already running"


def held_runs(pages: list[dict[str, Any]] | dict[str, Any], head_sha: str) -> list[dict[str, Any]]:
    """Runs at `head_sha` whose conclusion is `action_required`, oldest first."""
    if isinstance(pages, dict):
        pages = [pages]
    seen: dict[int, dict[str, Any]] = {}
    for page in pages:
        for run in page.get("workflow_runs") or []:
            if run.get("head_sha") != head_sha or run.get("conclusion") != "action_required":
                continue
            seen[int(run["id"])] = {"id": int(run["id"]), "name": str(run.get("name") or "")}
    return [seen[i] for i in sorted(seen)]


def release_plan(held: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One step per held run: approve first, re-run when GitHub says it is not waiting for approval."""
    return [
        {"run_id": run["id"], "name": run["name"], "op": APPROVE_OP, "fallback_op": RERUN_OP} for run in held
    ]


def release_result(op: str, exit_code: int, output: str) -> dict[str, Any]:
    """What one release attempt means, and the next op to run for that run, if any."""
    text = output.lower()
    if exit_code == 0:
        return {"state": "released", "next_op": None}
    if op == APPROVE_OP and _NOT_WAITING in text:
        return {"state": "not-waiting-for-approval", "next_op": RERUN_OP}
    if op == RERUN_OP and _ALREADY_RUNNING in text:
        return {"state": "already-running", "next_op": None}
    return {"state": "failed", "next_op": None}
