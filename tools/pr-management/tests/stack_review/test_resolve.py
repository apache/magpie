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
"""Step 1 — resolve the stack and gate.

Each `test_case_*` mirrors a case of the retired model-graded
`tools/skill-evals/evals/pr-management-stack-review/step-1-gate` suite.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from pr_management.config import Config
from pr_management.stack_review import resolve

REPO = "acme/product"
GREEN = [
    {
        "__typename": "CheckRun",
        "name": "unit",
        "workflowName": "Tests",
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
    }
]
BOT = [
    {
        "__typename": "CheckRun",
        "name": "WIP",
        "workflowName": "WIP",
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
    }
]


def entry(
    position: int,
    number: int,
    *,
    state: str = "OPEN",
    draft: bool = False,
    author: str = "alice",
    cross: bool = False,
    base: str = "main",
) -> dict[str, Any]:
    return {
        "position": position,
        "pullRequest": {
            "number": number,
            "title": f"Layer {position}",
            "state": state,
            "isDraft": draft,
            "isCrossRepository": cross,
            "url": f"https://github.com/{REPO}/pull/{number}",
            "baseRefName": base,
            "headRefName": f"layer-{position}",
            "headRefOid": f"{position:040d}",
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "reviewDecision": "APPROVED",
            "additions": 10,
            "deletions": 5,
            "changedFiles": 2,
            "author": {"login": author},
            "body": "",
            "reviewThreads": {"nodes": [{"isResolved": False}]},
        },
    }


def save_stack(
    saved: Path, member: int, entries: list[dict[str, Any]] | None, *, base: str = "main", number: int = 900
) -> None:
    stack = (
        None
        if entries is None
        else {
            "number": number,
            "size": len(entries),
            "baseRefName": base,
            "entries": {"totalCount": len(entries), "nodes": entries},
        }
    )
    doc = {
        "data": {
            "repository": {
                "pullRequest": {"number": member, "stack": stack},
                "defaultBranchRef": {"name": "main"},
            }
        }
    }
    (saved / f"stack-{member}.json").write_text(json.dumps(doc))


def save_checks(saved: Path, number: int, rollup: list[dict[str, Any]]) -> None:
    (saved / f"checks-{number}.json").write_text(json.dumps({"statusCheckRollup": rollup}))


def run(saved: Path, viewer: str = "maintainer-bob", **kw: Any) -> dict[str, Any]:
    return resolve.resolve(saved=saved, cfg=Config(), viewer=viewer, repo=REPO, **kw).as_dict()


def test_case_1_healthy_stack(tmp_path: Path) -> None:
    save_stack(tmp_path, 901, [entry(1, 901), entry(2, 902), entry(3, 903)])
    save_checks(tmp_path, 901, GREEN)
    save_checks(tmp_path, 902, GREEN)
    save_checks(tmp_path, 903, BOT)
    out = run(tmp_path, pr=901)
    assert (out["action"], out["lowest_open_layer"], out["unverified_ci_layers"]) == ("review", 1, [3])
    assert out["merged_layers"] == [] and out["draft_layers"] == [] and not out["self_authored"]
    assert out["needs"] == []
    assert out["headline"].startswith("Stack #900 on acme/product — 3 layers onto main — lowest open: 1")


def test_case_2_bottom_merged(tmp_path: Path) -> None:
    save_stack(tmp_path, 902, [entry(1, 901, state="MERGED"), entry(2, 902), entry(3, 903)])
    for n in (902, 903):
        save_checks(tmp_path, n, GREEN)
    out = run(tmp_path, pr=902)
    assert (out["lowest_open_layer"], out["merged_layers"], out["lowest_open_pr"]) == (2, [1], 902)
    assert "refs/pull/901/head" not in out["fetch_command"]


def test_case_3_not_a_stack(tmp_path: Path) -> None:
    save_stack(tmp_path, 5190, None)
    out = run(tmp_path, pr=5190)
    assert (out["action"], out["stop_reason"], out["handoff"]) == (
        "stop",
        "not-a-stack",
        "pr-management-code-review pr:5190",
    )


def test_case_4_cross_fork(tmp_path: Path) -> None:
    save_stack(tmp_path, 901, [entry(1, 901), entry(2, 902, cross=True)])
    assert run(tmp_path, pr=901)["stop_reason"] == "cross-fork"


def test_case_5_all_merged(tmp_path: Path) -> None:
    save_stack(tmp_path, 901, [entry(1, 901, state="MERGED"), entry(2, 902, state="MERGED")])
    out = run(tmp_path, pr=901)
    assert (out["stop_reason"], out["merged_layers"]) == ("nothing-open", [1, 2])


def test_case_6_self_authored_with_draft(tmp_path: Path) -> None:
    save_stack(
        tmp_path,
        901,
        [entry(1, 901, author="me"), entry(2, 902, author="me"), entry(3, 903, author="me", draft=True)],
    )
    for n in (901, 902, 903):
        save_checks(tmp_path, n, GREEN)
    out = run(tmp_path, viewer="me", pr=901)
    assert out["self_authored"] and out["draft_layers"] == [3] and out["unverified_ci_layers"] == []


def test_case_7_api_unavailable(tmp_path: Path) -> None:
    out = run(tmp_path, pr=901, read_error="gh: Field 'stack' doesn't exist on type 'PullRequest'")
    assert (out["action"], out["stop_reason"]) == ("stop", "api-unavailable")


def test_case_8_trunk_is_another_open_pr(tmp_path: Path) -> None:
    save_stack(
        tmp_path,
        951,
        [entry(1, 951, draft=True, base="feature/api-v2-step-6"), entry(2, 952, draft=True)],
        base="feature/api-v2-step-6",
        number=920,
    )
    save_checks(tmp_path, 951, BOT)
    save_checks(tmp_path, 952, BOT)
    out = run(tmp_path, pr=951)
    assert out["needs"] == [
        {
            "op": "gql-pr-by-head",
            "params": ["feature/api-v2-step-6"],
            "save": resolve.head_key("feature/api-v2-step-6"),
        }
    ]
    gate = {
        "number": 940,
        "title": "step 6",
        "url": "u",
        "baseRefName": "main",
        "stackEntry": {"position": 6},
        "stack": {"number": 915, "size": 7},
    }
    (tmp_path / resolve.head_key("feature/api-v2-step-6")).write_text(
        json.dumps({"data": {"repository": {"pullRequests": {"nodes": [gate]}}}})
    )
    out = run(tmp_path, pr=951)
    assert out["trunk_gated_by_pr"] == 940
    assert out["draft_layers"] == [1, 2] and out["unverified_ci_layers"] == [1, 2]
    assert out["trunk_sentence"].startswith("Trunk is PR #940 (layer 6 of stack #915)")


def test_a_stack_number_needs_the_scan_then_finds_the_member(tmp_path: Path) -> None:
    assert run(tmp_path, stack_number=900)["needs"][0]["op"] == "gql-stack-scan"
    scan = [
        {
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": [{"number": 5, "stack": None}, {"number": 901, "stack": {"number": 900}}]
                    }
                }
            }
        }
    ]
    (tmp_path / "stack-scan.json").write_text(json.dumps(scan))
    assert run(tmp_path, stack_number=900)["needs"][0] == {
        "op": "gql-stack-of-pr",
        "params": ["901"],
        "save": "stack-901.json",
    }
    assert run(tmp_path, stack_number=7)["stop_reason"] == "no-member"


def test_missing_rollups_are_requested(tmp_path: Path) -> None:
    save_stack(tmp_path, 901, [entry(1, 901), entry(2, 902)])
    out = run(tmp_path, pr=901)
    assert [n["save"] for n in out["needs"]] == ["checks-901.json", "checks-902.json"]
    assert out["headline"] is None


def test_ci_cells_follow_the_rule_order() -> None:
    cfg = Config()

    def run_(c: str | None, s: str) -> dict[str, Any]:
        return {
            "__typename": "CheckRun",
            "workflowName": "Tests",
            "name": "t",
            "status": s,
            "conclusion": c,
        }

    assert (
        resolve.ci_cell([run_("FAILURE", "COMPLETED"), run_("CANCELLED", "COMPLETED")], cfg) == "red (Tests)"
    )
    assert (
        resolve.ci_cell([run_("CANCELLED", "COMPLETED"), run_("SUCCESS", "COMPLETED")], cfg)
        == "cancelled (Tests)"
    )
    assert resolve.ci_cell([run_(None, "IN_PROGRESS"), run_("SUCCESS", "COMPLETED")], cfg) == "running (1)"
    assert resolve.ci_cell([run_("SKIPPED", "COMPLETED")], cfg) == "green"
    dependency_review = {
        "__typename": "CheckRun",
        "workflowName": "Dependency Review",
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
    }
    assert resolve.ci_cell([dependency_review], cfg) == "unverified"


def test_printed_git_commands_are_quoted(tmp_path: Path) -> None:
    save_stack(tmp_path, 901, [entry(1, 901), entry(2, 902)], base="feat;x")
    for n in (901, 902):
        save_checks(tmp_path, n, GREEN)
    (tmp_path / resolve.head_key("feat;x")).write_text(
        json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}})
    )
    out = run(tmp_path, pr=901, clone="/my clone")
    assert shlex.split(out["fetch_command"])[4] == "+refs/heads/feat;x:refs/magpie-stack/900/trunk"
    assert shlex.split(out["diff_commands"][0].split(" > ")[0])[2] == "/my clone"
