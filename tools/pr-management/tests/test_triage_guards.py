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
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pr_management.triage import guards

HEAD = "abc1234def5678"


def live(mergeable: str = "MERGEABLE", head: str = HEAD, state: str = "CLEAN") -> dict[str, Any]:
    return {"head_sha": head, "mergeable": mergeable, "merge_state": state}


def run(conclusion: str | None, status: str = "completed", rid: int = 1) -> dict[str, Any]:
    return {"id": rid, "status": status, "conclusion": conclusion}


def test_mark_ready_passes_on_a_clean_head() -> None:
    assert guards.check("mark-ready", expected_head=HEAD, liveness=live(), runs=[run("success")])["proceed"]


def test_mark_ready_refuses_while_approval_is_pending() -> None:
    r = guards.check("mark-ready", expected_head=HEAD, liveness=live(), runs=[run("action_required")])
    assert not r["proceed"] and r["reroute"] == "pending_workflow_approval"


@pytest.mark.parametrize(
    ("mergeable", "state", "reroute"), [("CONFLICTING", "DIRTY", "draft"), ("UNKNOWN", "UNKNOWN", "retry")]
)
def test_mark_ready_refuses_an_unmergeable_or_unsettled_pr(mergeable: str, state: str, reroute: str) -> None:
    r = guards.check("mark-ready", expected_head=HEAD, liveness=live(mergeable, state=state), runs=[])
    assert not r["proceed"] and r["reroute"] == reroute


def test_any_guard_refuses_a_moved_head() -> None:
    r = guards.check("rebase", expected_head=HEAD, liveness=live(head="ffffffff"), runs=None)
    assert not r["proceed"] and r["reroute"] == "reclassify"


def test_mark_ready_without_the_reads_refuses() -> None:
    assert not guards.check("mark-ready", expected_head=HEAD, liveness=None, runs=[])["proceed"]
    assert not guards.check("mark-ready", expected_head=HEAD, liveness=live(), runs=None)["proceed"]


def test_rebase_refuses_conflicts_and_unknown() -> None:
    assert (
        guards.check("rebase", expected_head=HEAD, liveness=live("CONFLICTING"), runs=None)["reroute"]
        == "draft"
    )
    assert (
        guards.check("rebase", expected_head=HEAD, liveness=live("UNKNOWN"), runs=None)["reroute"] == "retry"
    )
    assert guards.check("rebase", expected_head=HEAD, liveness=live(), runs=None)["proceed"]


def test_approve_workflow_lists_the_pending_runs() -> None:
    r = guards.check(
        "approve-workflow",
        expected_head=HEAD,
        liveness=None,
        runs=[run("action_required", rid=7), run("success", rid=8), run("action_required", rid=9)],
    )
    assert r["proceed"] and r["run_ids"] == [7, 9]


def test_approve_workflow_is_a_no_op_once_approved() -> None:
    r = guards.check("approve-workflow", expected_head=HEAD, liveness=None, runs=[run("success")])
    assert not r["proceed"] and "already approved" in r["reason"]


def test_rerun_prefers_failed_runs_then_in_progress() -> None:
    assert guards.check(
        "rerun",
        expected_head=HEAD,
        liveness=None,
        runs=[run("failure", rid=3), run(None, "in_progress", rid=4)],
    )["rerun_failed"] == [3]
    assert guards.check("rerun", expected_head=HEAD, liveness=None, runs=[run(None, "in_progress", rid=4)])[
        "cancel_and_rerun"
    ] == [4]
    assert guards.check("rerun", expected_head=HEAD, liveness=None, runs=[])["reroute"] == "rebase"


def test_loaders_read_the_saved_shapes(tmp_path: Path) -> None:
    liveness = tmp_path / "liveness-1.json"
    liveness.write_text(
        json.dumps(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "headRefOid": HEAD,
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                        }
                    }
                }
            }
        )
    )
    runs = tmp_path / "runs-head-1.json"
    runs.write_text(
        json.dumps([{"workflow_runs": [run("success")]}, {"workflow_runs": [run("action_required", rid=2)]}])
    )
    assert guards.load_liveness(liveness)["mergeable"] == "MERGEABLE"
    assert [r["id"] for r in guards.load_runs(runs)] == [1, 2]
