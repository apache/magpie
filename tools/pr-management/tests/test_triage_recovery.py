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
"""Action receipts, per-PR history and guarded recovery, with no external writes."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from pr_management import cli
from pr_management.triage import fold, recovery, session

from .helpers import page, pr

REPO = "acme/product"
VIEWER = "maintainer"
HEAD = "a" * 40
BLOCK = "<!-- pr-triage-fold: action=draft -->\nPlease fix CI.\n<!-- /pr-triage-fold -->"
OLD = "<!-- pr-triage-fold: action=comment -->\nPrevious note.\n<!-- /pr-triage-fold -->"


def live(**fields: Any) -> dict[str, Any]:
    return {
        "number": 12,
        "url": f"https://github.com/{REPO}/pull/12",
        "headRefOid": HEAD,
        "state": "OPEN",
        "isDraft": False,
        "mergedAt": None,
        "body": "Author text.",
        "labels": [],
        "assignees": [],
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "workflow_runs": [{"id": 1, "status": "completed", "conclusion": "success"}],
        "comment_receipts": [],
        "updatedAt": "2026-11-13T10:00:00Z",
        **fields,
    }


def checkpoint(path: Path, **event: Any) -> dict[str, Any]:
    return recovery.checkpoint(path, REPO, VIEWER, event)


def begin(path: Path, action: str = "draft", number: int = 12) -> int:
    return checkpoint(path, phase="begin", pr=number, head=HEAD, action=action)["action_id"]


def apply(state: dict[str, Any], change: dict[str, Any], *, reverse: bool = False) -> dict[str, Any]:
    state = copy.deepcopy(state)
    value = change["before" if reverse else "after"]
    kind = change["kind"]
    if kind in {"label", "assignee"}:
        key, field = ("labels", "name") if kind == "label" else ("assignees", "login")
        state[key] = [x for x in state[key] if x[field] != change["target"]]
        if value:
            state[key].append({field: change["target"]})
    elif kind == "draft":
        state["isDraft"] = value
    elif kind == "state":
        state["state"] = value
    elif kind == "fold":
        state["body"] = fold.restore(
            state["body"], expected=change["after" if reverse else "before"], previous=value
        )
    elif kind == "comment":
        if reverse:
            state["missing_comment_ids"] = [100]
            state["comment_receipts"] = []
        else:
            state["comment_receipts"] = [
                {
                    "id": 100,
                    "body": value,
                    "user": {"login": VIEWER},
                    "issue_url": f"https://api.github.com/repos/{REPO}/issues/12",
                    "updated_at": "2026-11-13T10:01:00Z",
                }
            ]
    return state


def record_action(
    path: Path, changes: list[dict[str, Any]], state: dict[str, Any] | None = None, action: str = "draft"
) -> tuple[int, dict[str, Any]]:
    state = state or live()
    ident = begin(path, action)
    for change in changes:
        effect = checkpoint(path, phase="prepare", action_id=ident, change=change, live=state)["effect_id"]
        state = apply(state, change)
        checkpoint(
            path,
            phase="result",
            action_id=ident,
            effect_id=effect,
            outcome="applied",
            live=state,
            receipt=state["comment_receipts"][0] if change["kind"] == "comment" else None,
        )
    checkpoint(path, phase="finish", action_id=ident)
    return ident, state


def recover_all(path: Path, ident: int, state: dict[str, Any]) -> dict[str, Any]:
    while True:
        plan = recovery.plan(path, REPO, VIEWER, ident, state)
        assert plan["status"] in {"ready", "recovered", "partial", "irreversible"}, plan
        if not plan["operations"]:
            return state
        op = plan["operations"][0]
        effect = next(
            e
            for e in session.load(path)["action_log"]["actions"][ident - 1]["effects"]
            if e["id"] == op["effect_id"]
        )
        after = apply(state, effect, reverse=True)
        checkpoint(
            path,
            phase="recover",
            action_id=ident,
            effect_id=op["effect_id"],
            before=state,
            after=after,
            confirmed_plan=plan["digest"],
        )
        state = after


def test_compound_draft_recovers_label_draft_note_and_assignment(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    original = live(labels=[{"name": "ready for maintainer review"}])
    changes: list[dict[str, Any]] = [
        {"kind": "label", "target": "ready for maintainer review", "before": True, "after": False},
        {"kind": "draft", "before": False, "after": True},
        {"kind": "fold", "before": None, "after": BLOCK},
        {"kind": "assignee", "target": "contributor", "before": False, "after": True},
    ]
    ident, state = record_action(path, changes, original)
    before = path.read_bytes()
    plan = recovery.plan(path, REPO, VIEWER, ident, state)
    assert [o["kind"] for o in plan["operations"]] == ["assignee", "fold", "draft", "label"]
    assert path.read_bytes() == before  # previews have no side effects
    state["body"] = "New author introduction.\n" + state["body"] + "\nNew author footer."
    restored = recover_all(path, ident, state)
    assert restored["labels"] == original["labels"]
    assert restored["isDraft"] is False and restored["assignees"] == []
    assert "New author introduction." in restored["body"] and "New author footer." in restored["body"]
    assert BLOCK not in restored["body"]
    assert recovery.plan(path, REPO, VIEWER, ident, restored)["status"] == "recovered"
    assert "12" not in session.load(path)["prs"]
    assert session.summary(path)["action_history"] == {"recovered": 1}


def test_comment_channel_deletes_only_the_recorded_comment(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "comment", "before": None, "after": "Please fix CI."}])
    op = recovery.plan(path, REPO, VIEWER, ident, state)["operations"][0]
    assert op["argv"] == ["gh", "api", f"repos/{REPO}/issues/comments/100", "-X", "DELETE"]
    restored = recover_all(path, ident, state)
    assert restored["missing_comment_ids"] == [100]


@pytest.mark.parametrize(
    "field,value",
    [
        ("body", "edited"),
        ("user", {"login": "another-maintainer"}),
        ("updated_at", "2026-11-14T00:00:00Z"),
        ("issue_url", "https://api.github.com/repos/other/repo/issues/12"),
    ],
)
def test_changed_comment_is_never_deleted(tmp_path: Path, field: str, value: Any) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "comment", "before": None, "after": "note"}])
    state["comment_receipts"][0][field] = value
    plan = recovery.plan(path, REPO, VIEWER, ident, state)
    assert plan["status"] == "blocked" and not plan["operations"]


def test_missing_comment_requires_exact_id_absence_evidence(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "comment", "before": None, "after": "note"}])
    state["comment_receipts"] = []
    assert recovery.plan(path, REPO, VIEWER, ident, state)["status"] == "blocked"
    state["missing_comment_ids"] = [100]
    plan = recovery.plan(path, REPO, VIEWER, ident, state)
    assert plan["operations"][0]["argv"] == []
    assert plan["operations"][0]["already_restored"]
    recover_all(path, ident, state)


@pytest.mark.parametrize(
    "change,state,expected",
    [
        (
            {"kind": "state", "before": "OPEN", "after": "CLOSED"},
            live(),
            ["gh", "pr", "reopen", "12", "--repo", REPO],
        ),
        (
            {"kind": "draft", "before": True, "after": False},
            live(isDraft=True),
            ["gh", "pr", "ready", "12", "--repo", REPO, "--undo"],
        ),
        (
            {"kind": "assignee", "target": "contributor", "before": True, "after": False},
            live(assignees=[{"login": "contributor"}]),
            ["gh", "pr", "edit", "12", "--repo", REPO, "--add-assignee", "contributor"],
        ),
    ],
)
def test_native_inverse_commands(
    tmp_path: Path, change: dict[str, Any], state: dict[str, Any], expected: list[str]
) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [change], state)
    assert recovery.plan(path, REPO, VIEWER, ident, state)["operations"][0]["argv"] == expected
    recover_all(path, ident, state)


@pytest.mark.parametrize("fields", [{"headRefOid": "b" * 40}, {"state": "MERGED", "mergedAt": "today"}])
def test_head_move_or_merge_blocks_all_recovery(tmp_path: Path, fields: dict[str, Any]) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    state.update(fields)
    assert recovery.plan(path, REPO, VIEWER, ident, state)["status"] == "blocked"


@pytest.mark.parametrize(
    "fields",
    [
        {"mergeable": "UNKNOWN"},
        {"mergeable": "CONFLICTING"},
        {"workflow_runs": [{"conclusion": "action_required"}]},
        {"workflow_runs": None},
    ],
)
def test_ready_restoration_uses_existing_ci_guards(tmp_path: Path, fields: dict[str, Any]) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    state.update(fields)
    assert recovery.plan(path, REPO, VIEWER, ident, state)["status"] == "blocked"


def test_configured_ready_label_cannot_bypass_the_guard(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(
        path,
        [{"kind": "label", "target": "custom-ready", "before": True, "after": False}],
        live(labels=[{"name": "custom-ready"}]),
    )
    state["workflow_runs"] = [{"conclusion": "action_required"}]
    assert recovery.plan(path, REPO, VIEWER, ident, state, ready_label="custom-ready")["status"] == "blocked"


def test_only_latest_action_on_same_pr_can_be_recovered(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    first, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    second, state = record_action(path, [{"kind": "fold", "before": None, "after": BLOCK}], state)
    assert recovery.plan(path, REPO, VIEWER, first, state)["status"] == "blocked"
    state = recover_all(path, second, state)
    assert session.load(path)["prs"]["12"]["action_taken"] == "draft"
    recover_all(path, first, state)


def test_history_is_ordered_and_omits_private_bodies(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    record_action(path, [{"kind": "fold", "before": None, "after": BLOCK}])
    begin(path, action="skip", number=13)
    checkpoint(path, phase="finish", action_id=2)
    result = recovery.history(path, REPO, VIEWER)
    assert [a["pr"] for a in result["actions"]] == [12, 13]
    assert "Please fix CI" not in json.dumps(result)
    assert path.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("outcome", ["prepared", "unknown"])
def test_uncertain_operation_is_not_retried_or_guessed(tmp_path: Path, outcome: str) -> None:
    path = tmp_path / "s.json"
    ident = begin(path)
    effect = checkpoint(
        path,
        phase="prepare",
        action_id=ident,
        change={"kind": "draft", "before": False, "after": True},
        live=live(),
    )["effect_id"]
    if outcome == "unknown":
        checkpoint(path, phase="result", action_id=ident, effect_id=effect, outcome="unknown")
    checkpoint(path, phase="finish", action_id=ident)
    assert recovery.plan(path, REPO, VIEWER, ident, live(isDraft=True))["status"] == "blocked"
    assert session.load(path)["prs"]["12"]["terminal"]
    checkpoint(
        path, phase="result", action_id=ident, effect_id=effect, outcome="applied", live=live(isDraft=True)
    )
    recover_all(path, ident, live(isDraft=True))


def test_verified_failure_is_not_counted_as_a_success(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident = begin(path)
    effect = checkpoint(
        path,
        phase="prepare",
        action_id=ident,
        change={"kind": "draft", "before": False, "after": True},
        live=live(),
    )["effect_id"]
    checkpoint(path, phase="result", action_id=ident, effect_id=effect, outcome="not-applied")
    assert checkpoint(path, phase="finish", action_id=ident)["status"] == "failed"
    assert not session.load(path)["prs"]["12"]["terminal"]
    assert session.summary(path)["acted_total"] == 0


def test_irreversible_effects_are_visible_not_called_recovered(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(
        path, [{"kind": "irreversible", "before": None, "after": "run-rerun"}], action="rerun"
    )
    plan = recovery.plan(path, REPO, VIEWER, ident, state)
    assert plan["status"] == "irreversible" and plan["operations"] == []
    assert plan["irreversible"] == ["run-rerun"] and plan["notifications_recalled"] is False


def test_recovery_checkpoint_needs_the_exact_plan_and_observed_result(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    plan = recovery.plan(path, REPO, VIEWER, ident, state)
    event = {
        "phase": "recover",
        "action_id": ident,
        "effect_id": 1,
        "before": state,
        "after": live(),
        "confirmed_plan": "wrong",
    }
    with pytest.raises(ValueError, match="freshly confirmed"):
        checkpoint(path, **event)
    event["confirmed_plan"] = plan["digest"]
    event["after"] = state
    with pytest.raises(ValueError, match="does not confirm"):
        checkpoint(path, **event)
    event["after"] = live()
    checkpoint(path, **event)
    assert checkpoint(path, **event)["recovered"]  # replay only records a known result; no duplicate write


def test_interrupted_recovery_can_resume_from_the_saved_log(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    # GitHub changed but the process died before recording its success.
    state["isDraft"] = False
    plan = recovery.plan(path, REPO, VIEWER, ident, state)
    assert plan["operations"][0]["already_restored"]
    recover_all(path, ident, state)


def test_old_session_is_viewable_without_inventing_undo_evidence(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    session.record(path, pr=12, head="abc", action="draft")
    assert recovery.history(path, REPO, VIEWER)["actions"][0]["status"] == "legacy"
    assert "action_log" not in session.load(path)
    with pytest.raises(ValueError, match="not in this session"):
        recovery.plan(path, REPO, VIEWER, 1, live())


@pytest.mark.parametrize("repo,viewer", [("other/repo", VIEWER), (REPO, "other-viewer")])
def test_session_is_bound_to_repository_and_actor(tmp_path: Path, repo: str, viewer: str) -> None:
    path = tmp_path / "s.json"
    begin(path)
    with pytest.raises(ValueError, match="does not match"):
        recovery.history(path, repo, viewer)


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "unknown"},
        {"kind": "draft", "before": 0, "after": 1},
        {"kind": "label", "target": "x", "before": False, "after": False},
        {"kind": "fold", "before": None, "after": "arbitrary author text"},
        {"kind": "comment", "before": "existing comment", "after": "new"},
        {"kind": "irreversible", "before": None, "after": "arbitrary-command"},
    ],
)
def test_invalid_intent_is_rejected_before_writing(tmp_path: Path, change: dict[str, Any]) -> None:
    path = tmp_path / "s.json"
    ident = begin(path)
    original = path.read_bytes()
    with pytest.raises(ValueError):
        checkpoint(path, phase="prepare", action_id=ident, change=change, live=live())
    assert path.read_bytes() == original


def test_cli_checkpoint_history_and_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "s.json"
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"phase": "begin", "pr": 12, "head": HEAD, "action": "skip"}))
    common = ["--session", str(path), "--repo", REPO, "--viewer", VIEWER]
    assert cli.main(["triage", "session", "checkpoint", *common, "--event", str(event)]) == 0
    assert json.loads(capsys.readouterr().out) == {"action_id": 1}
    checkpoint(path, phase="finish", action_id=1)
    assert cli.main(["triage", "session", "history", *common]) == 0
    assert json.loads(capsys.readouterr().out)["actions"][0]["action"] == "skip"
    snapshot = tmp_path / "live.json"
    snapshot.write_text(json.dumps(live()))
    assert (
        cli.main(["triage", "session", "undo-plan", *common, "--action-id", "1", "--live", str(snapshot)])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "nothing-to-undo"


def test_revisit_bypasses_only_the_selected_session_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    (saved / "triage-pages.json").write_text(
        json.dumps(page(pr(12, head=HEAD, mergeable="CONFLICTING"), pr(13, head=HEAD)))
    )
    path = tmp_path / "s.json"
    session.record(path, pr=12, head=HEAD, action="draft")
    session.record(path, pr=13, head=HEAD, action="comment")
    before = path.read_bytes()
    args = [
        "--config-dir",
        str(tmp_path),
        "triage",
        "classify",
        "--saved-dir",
        str(saved),
        "--viewer",
        VIEWER,
        "--session",
        str(path),
    ]
    cli.main(args)
    assert json.loads(capsys.readouterr().out)["counts"]["suppressed"] == 2
    cli.main([*args, "--revisit", "12"])
    out = json.loads(capsys.readouterr().out)
    assert out["counts"]["suppressed"] == 0
    assert all(item["number"] == 12 for group in out["groups"] for item in group["prs"])
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "body", ["<!-- pr-triage-fold: x -->unclosed", BLOCK + BLOCK, "<!-- /pr-triage-fold -->"]
)
def test_ambiguous_folds_fail_closed(body: str) -> None:
    with pytest.raises(ValueError):
        fold.block(body)


def test_fold_recovery_preserves_previous_block_and_author_edits() -> None:
    body = "Updated introduction.\n\n" + BLOCK + "\nUpdated footer."
    assert fold.restore(body, expected=BLOCK, previous=OLD) == body.replace(BLOCK, OLD)
    with pytest.raises(ValueError, match="changed"):
        fold.restore(body, expected=OLD, previous=None)


def test_late_failure_receipt_resettles_action_and_cache(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident = begin(path)
    effect = checkpoint(
        path,
        phase="prepare",
        action_id=ident,
        change={"kind": "draft", "before": False, "after": True},
        live=live(),
    )["effect_id"]
    checkpoint(path, phase="result", action_id=ident, effect_id=effect, outcome="unknown")
    checkpoint(path, phase="finish", action_id=ident)
    checkpoint(path, phase="result", action_id=ident, effect_id=effect, outcome="not-applied")
    cache = session.load(path)
    assert cache["action_log"]["actions"][0]["status"] == "failed"
    assert not cache["prs"]["12"]["terminal"]
    assert cache["prs"]["12"]["journal_status"] == "failed"
    assert session.summary(path)["acted_total"] == 0


def test_recovery_restores_failed_cache_entry_without_promoting_it(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident = begin(path)
    effect = checkpoint(
        path,
        phase="prepare",
        action_id=ident,
        change={"kind": "draft", "before": False, "after": True},
        live=live(),
    )["effect_id"]
    checkpoint(path, phase="result", action_id=ident, effect_id=effect, outcome="not-applied")
    checkpoint(path, phase="finish", action_id=ident)
    second, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    recover_all(path, second, state)
    restored = session.load(path)["prs"]["12"]
    assert restored["journal_status"] == "failed" and not restored["terminal"]
    assert session.summary(path)["acted_total"] == 0


def test_recovered_pr_remains_available_for_revisit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    recover_all(path, ident, state)
    assert not session.load(path)["prs"]
    saved = tmp_path / "saved"
    saved.mkdir()
    (saved / "triage-pages.json").write_text(json.dumps(page(pr(12, head=HEAD))))
    (tmp_path / "project.md").write_text(f"| `upstream_repo` | `{REPO}` |\n")
    assert (
        cli.main(
            [
                "--config-dir",
                str(tmp_path),
                "triage",
                "classify",
                "--saved-dir",
                str(saved),
                "--viewer",
                VIEWER,
                "--session",
                str(path),
                "--revisit",
                "12",
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["counts"]["suppressed"] == 0


def test_original_legacy_cache_survives_new_action_and_recovery(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    session.record(path, pr=12, head=HEAD, action="comment")
    original = copy.deepcopy(session.load(path)["prs"]["12"])
    ident, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    assert any(row["status"] == "legacy" for row in recovery.history(path, REPO, VIEWER)["actions"])
    recover_all(path, ident, state)
    assert session.load(path)["prs"]["12"] == original


def test_later_skip_does_not_block_recovery_of_an_applied_action(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    skip = begin(path, action="skip")
    checkpoint(path, phase="finish", action_id=skip)
    recover_all(path, ident, state)
    assert session.load(path)["prs"]["12"]["action_taken"] == "skip"


def test_partial_recovery_keeps_irreversible_effects_explicit(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(
        path,
        [
            {"kind": "draft", "before": False, "after": True},
            {"kind": "irreversible", "before": None, "after": "workflow-approve"},
        ],
    )
    state = recover_all(path, ident, state)
    assert recovery.plan(path, REPO, VIEWER, ident, state)["status"] == "irreversible"
    assert session.load(path)["action_log"]["actions"][0]["status"] == "partially-recovered"


@pytest.mark.parametrize("field,value", [("state", None), ("isDraft", None)])
def test_recovery_rejects_incomplete_saved_pr_reads(tmp_path: Path, field: str, value: Any) -> None:
    path = tmp_path / "s.json"
    ident, state = record_action(path, [{"kind": "draft", "before": False, "after": True}])
    state[field] = value
    with pytest.raises(ValueError, match="complete PR read"):
        recovery.plan(path, REPO, VIEWER, ident, state)


def test_local_cli_recovery_executes_native_commands_against_a_fake_forge(tmp_path: Path) -> None:
    """Exercise serialized CLI plans, native argv and checkpoints without network access."""
    path = tmp_path / "session.json"
    original = live(labels=[{"name": "ready for maintainer review"}])
    changes: list[dict[str, Any]] = [
        {"kind": "label", "target": "ready for maintainer review", "before": True, "after": False},
        {"kind": "draft", "before": False, "after": True},
        {"kind": "fold", "before": None, "after": BLOCK},
        {"kind": "comment", "before": None, "after": "A triage note."},
        {"kind": "assignee", "target": "contributor", "before": False, "after": True},
        {"kind": "state", "before": "OPEN", "after": "CLOSED"},
    ]
    ident, state = record_action(path, changes, original, action="close")
    state_file = tmp_path / "forge.json"
    state_file.write_text(json.dumps(state))
    fake = tmp_path / "fake_gh.py"
    fake.write_text("""import json,sys
from pathlib import Path
p=Path(sys.argv[1]); args=sys.argv[2:]; state=json.loads(p.read_text())
if args[:2]==['pr','edit']:
    flags=args[5:]
    if flags[0]=='--body-file': state['body']=Path(flags[1]).read_text()
    else:
        flag,target=flags
        action,kind=flag[2:].split('-',1)
        key,field=('labels','name') if kind=='label' else ('assignees','login')
        state[key]=[x for x in state[key] if x[field]!=target]
        if action=='add': state[key].append({field:target})
elif args[:2]==['pr','ready']: state['isDraft']='--undo' in args
elif args[:2]==['pr','reopen']: state['state']='OPEN'
elif args[:2]==['pr','close']: state['state']='CLOSED'
elif args[0]=='api' and args[-2:]==['-X','DELETE']:
    assert args[1]=='repos/acme/product/issues/comments/100'
    state['comment_receipts']=[]; state['missing_comment_ids']=[100]
else: raise AssertionError(args)
p.write_text(json.dumps(state))
""")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "project.md").write_text(f"| `upstream_repo` | `{REPO}` |\n")
    snapshot = tmp_path / "live.json"
    for _ in changes:
        before = json.loads(state_file.read_text())
        snapshot.write_text(json.dumps(before))
        command = [
            sys.executable,
            "-m",
            "pr_management.cli",
            "--config-dir",
            str(config_dir),
            "triage",
            "session",
            "undo-plan",
            "--session",
            str(path),
            "--repo",
            REPO,
            "--viewer",
            VIEWER,
            "--action-id",
            str(ident),
            "--live",
            str(snapshot),
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        plan = json.loads(result.stdout)
        assert plan["status"] == "ready", plan
        op = plan["operations"][0]
        argv = op["argv"]
        if "body" in op:
            body_file = tmp_path / "body.md"
            body_file.write_text(op["body"])
            argv = [str(body_file) if x == "<recovery-body-file>" else x for x in argv]
        subprocess.run([sys.executable, str(fake), str(state_file), *argv[1:]], check=True)
        after = json.loads(state_file.read_text())
        event_file = tmp_path / "event.json"
        event_file.write_text(
            json.dumps(
                {
                    "phase": "recover",
                    "action_id": ident,
                    "effect_id": op["effect_id"],
                    "confirmed_plan": plan["digest"],
                    "before": before,
                    "after": after,
                }
            )
        )
        checkpoint_cmd = [
            *command[: command.index("undo-plan")],
            "checkpoint",
            "--session",
            str(path),
            "--repo",
            REPO,
            "--viewer",
            VIEWER,
            "--event",
            str(event_file),
        ]
        subprocess.run(checkpoint_cmd, check=True, capture_output=True, text=True)
    restored = json.loads(state_file.read_text())
    assert restored["state"] == "OPEN" and restored["isDraft"] is False
    assert restored["labels"] == original["labels"] and restored["assignees"] == []
    assert BLOCK not in restored["body"] and "Author text." in restored["body"]
    assert recovery.plan(path, REPO, VIEWER, ident, restored)["status"] == "recovered"


def test_skipped_pr_cannot_prepare_a_mutation(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    ident = begin(path, action="skip")
    with pytest.raises(ValueError, match="skipped PR"):
        checkpoint(
            path,
            phase="prepare",
            action_id=ident,
            change={"kind": "draft", "before": False, "after": True},
            live=live(),
        )


def test_close_stale_is_counted_by_the_existing_summary(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    record_action(path, [{"kind": "state", "before": "OPEN", "after": "CLOSED"}], action="close-stale")
    assert session.summary(path)["acted"] == {"stale PRs closed": 1}
