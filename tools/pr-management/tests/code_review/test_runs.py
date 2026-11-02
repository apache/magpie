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
"""Releasing workflow runs held in action_required at a PR head."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pr_management import cli
from pr_management.code_review import data, runs

from .builders import node, review

HEAD = "0123456789abcdef0123456789abcdef01234567"
OTHER = "f" * 40


def _run_entry(
    run_id: int, *, head: str = HEAD, conclusion: str | None = "action_required"
) -> dict[str, Any]:
    return {"id": run_id, "name": f"wf-{run_id}", "head_sha": head, "conclusion": conclusion}


def test_held_runs_are_the_action_required_ones_at_the_head() -> None:
    pages = [
        {
            "workflow_runs": [
                _run_entry(30),
                _run_entry(10),
                _run_entry(20, conclusion="success"),
                _run_entry(40, head=OTHER),
                _run_entry(10),
            ]
        }
    ]
    assert runs.held_runs(pages, HEAD) == [{"id": 10, "name": "wf-10"}, {"id": 30, "name": "wf-30"}]


def test_a_single_page_object_is_accepted() -> None:
    assert runs.held_runs({"workflow_runs": [_run_entry(5)]}, HEAD) == [{"id": 5, "name": "wf-5"}]


def test_the_plan_approves_first_and_falls_back_to_a_rerun() -> None:
    assert runs.release_plan([{"id": 5, "name": "CI"}]) == [
        {"run_id": 5, "name": "CI", "op": "workflow-approve", "fallback_op": "run-rerun"}
    ]


@pytest.mark.parametrize(
    ("op", "code", "output", "expected"),
    [
        ("workflow-approve", 0, "{}", {"state": "released", "next_op": None}),
        (
            "workflow-approve",
            1,
            "gh: This workflow run is not waiting for approval (HTTP 403)",
            {"state": "not-waiting-for-approval", "next_op": "run-rerun"},
        ),
        ("run-rerun", 0, "", {"state": "released", "next_op": None}),
        (
            "run-rerun",
            1,
            "run 41291511481 cannot be rerun; This workflow is already running",
            {"state": "already-running", "next_op": None},
        ),
        ("run-rerun", 1, "HTTP 500", {"state": "failed", "next_op": None}),
        ("workflow-approve", 1, "HTTP 404", {"state": "failed", "next_op": None}),
    ],
)
def test_release_result(op: str, code: int, output: str, expected: dict[str, Any]) -> None:
    assert runs.release_result(op, code, output) == expected


def _cli(capsys: pytest.CaptureFixture[str], *argv: str) -> dict[str, Any]:
    assert cli.main(["code-review", *argv]) == 0
    return json.loads(capsys.readouterr().out)


FIXUP = "a" * 40


def _head_commit(
    oid: str,
    *,
    parents: list[str],
    signer: str | None = "alice",
    valid: bool = True,
    authors: tuple[str, ...] = ("alice",),
) -> dict[str, Any]:
    return {
        "commit": {
            "oid": oid,
            "parents": {"nodes": [{"oid": p} for p in parents]},
            "signature": {"isValid": valid, "signer": {"login": signer}} if signer else None,
            "authors": {"nodes": [{"user": {"login": a} if a else None} for a in authors]},
        }
    }


def _saved_pr(
    saved: Path,
    *,
    head: str,
    approved_at: str | None = HEAD,
    head_commits: list[dict[str, Any]] | None = None,
    viewer: str | None = "alice",
) -> None:
    reviews = [review("alice", "APPROVED", commit_oid=approved_at)] if approved_at else []
    full = node(7, head=head, reviews=reviews)
    full["headCommits"] = {"nodes": head_commits or []}
    payload: dict[str, Any] = {"repository": {"pullRequest": full}}
    if viewer:
        payload["viewer"] = {"login": viewer}
    (saved / "cr-pr-7.json").write_text(json.dumps({"data": payload}))


def _release(
    capsys: pytest.CaptureFixture[str], saved: Path, *extra: str, viewer: str = "alice"
) -> dict[str, Any]:
    return _cli(capsys, "release-runs", "--saved-dir", str(saved), "--pr", "7", "--viewer", viewer, *extra)


def test_release_runs_asks_for_the_head_read_then_plans(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _saved_pr(tmp_path, head=HEAD)
    first = _release(capsys, tmp_path, "--head", HEAD)
    (need,) = first["needs"]
    assert need["op"] == "runs-at-head" and need["params"] == [HEAD]
    (tmp_path / need["save"]).write_text(json.dumps([{"workflow_runs": [_run_entry(9)]}]))
    second = _release(capsys, tmp_path, "--head", HEAD)
    assert second["needs"] == [] and [step["run_id"] for step in second["plan"]] == [9]


def test_release_runs_wants_the_full_head_sha(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="full 40-character"):
        _release(capsys, tmp_path, "--head", "abc123")


@pytest.mark.parametrize(
    ("setup", "args", "message"),
    [
        pytest.param({"head": HEAD}, ["--head", OTHER], "refresh gql-cr-pr", id="stale-read"),
        pytest.param(
            {"head": HEAD, "approved_at": None}, ["--head", HEAD], "no APPROVED review", id="not-approved"
        ),
        pytest.param(
            {"head": HEAD, "viewer": None}, ["--head", HEAD], "has no viewer", id="no-viewer-in-read"
        ),
    ],
)
def test_release_runs_refuses_an_unapproved_or_stale_head(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, setup: dict[str, Any], args: list[str], message: str
) -> None:
    _saved_pr(tmp_path, **setup)
    with pytest.raises(SystemExit, match=message):
        _release(capsys, tmp_path, *args)


def test_release_runs_refuses_a_mismatched_viewer(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    _saved_pr(tmp_path, head=HEAD)
    with pytest.raises(SystemExit, match="not the saved read's viewer"):
        _release(capsys, tmp_path, "--head", HEAD, viewer="mallory")


def test_release_runs_accepts_a_verified_fixup_on_the_approved_head(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _saved_pr(tmp_path, head=FIXUP, head_commits=[_head_commit(FIXUP, parents=[HEAD])])
    out = _release(capsys, tmp_path, "--head", FIXUP, "--reviewed-head", HEAD)
    assert out["needs"][0]["params"] == [FIXUP]


@pytest.mark.parametrize(
    ("head_commit", "approved_at", "message"),
    [
        pytest.param(
            _head_commit(FIXUP, parents=[HEAD], signer=None), HEAD, "verified signature", id="unsigned"
        ),
        pytest.param(
            _head_commit(FIXUP, parents=[HEAD], valid=False),
            HEAD,
            "verified signature",
            id="invalid-signature",
        ),
        pytest.param(
            _head_commit(FIXUP, parents=[HEAD], signer="nina", authors=("alice",)),
            HEAD,
            "verified signature",
            id="forged-author-signed-by-someone-else",
        ),
        pytest.param(
            _head_commit(FIXUP, parents=[HEAD], authors=("",)),
            HEAD,
            "verified signature",
            id="unlinked-author",
        ),
        pytest.param(
            _head_commit(FIXUP, parents=[HEAD], authors=("alice", "nina")),
            HEAD,
            "verified signature",
            id="co-author",
        ),
        pytest.param(_head_commit(FIXUP, parents=[OTHER]), HEAD, "verified signature", id="wrong-parent"),
        pytest.param(
            _head_commit(FIXUP, parents=[HEAD, OTHER]), HEAD, "verified signature", id="merge-commit"
        ),
        pytest.param(
            _head_commit(FIXUP, parents=[HEAD]), OTHER, "no APPROVED review", id="reviewed-head-not-approved"
        ),
    ],
)
def test_release_runs_refuses_an_unverified_fixup(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    head_commit: dict[str, Any],
    approved_at: str,
    message: str,
) -> None:
    _saved_pr(tmp_path, head=FIXUP, approved_at=approved_at, head_commits=[head_commit])
    with pytest.raises(SystemExit, match=message):
        _release(capsys, tmp_path, "--head", FIXUP, "--reviewed-head", HEAD)


def test_release_result_command(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    out.write_text("This workflow run is not waiting for approval")
    result = _cli(
        capsys, "release-result", "--op", "workflow-approve", "--exit-code", "1", "--output-file", str(out)
    )
    assert result == {"state": "not-waiting-for-approval", "next_op": "run-rerun"}


@pytest.mark.parametrize(
    "conn",
    [
        pytest.param({"totalCount": 101, "pageInfo": {"hasNextPage": True}}, id="has-next-page"),
        pytest.param({"totalCount": 101}, id="total-above-read"),
    ],
)
def test_a_truncated_check_list_counts_as_unknown_pending(conn: dict[str, Any]) -> None:
    full = node(
        7,
        rollup="PENDING",
        checks=[{"__typename": "CheckRun", "name": "T", "status": "IN_PROGRESS", "isRequired": True}],
    )
    full["latest"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"].update(conn)
    assert data.from_node(full).pending_not_required == (data.UNREAD_CHECKS,)
