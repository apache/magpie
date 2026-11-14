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
"""Session-local action evidence and read-only recovery plans; never a GitHub client.

The skill checkpoints intent before each write and its observed outcome afterwards.
Recovery uses those receipts, not a guessed inverse of the action's name. The old
`prs` cache stays intact for classification and old caches remain viewable.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import fold, guards, session

KINDS = frozenset({"label", "assignee", "draft", "state", "fold", "comment", "irreversible"})
IRREVERSIBLE = frozenset({"update-branch", "workflow-approve", "run-rerun", "run-cancel"})
ACTIONS = session.TERMINAL | {"close-stale", "skip", "skipped"}


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError(f"{name} must be a non-empty string without NUL")
    return value


def _number(value: Any, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _identity(repo: str, viewer: str) -> None:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo, flags=re.ASCII) or any(
        part in {".", ".."} for part in repo.split("/")
    ):
        raise ValueError("repo must be owner/name")
    if not re.fullmatch(r"[\w-]+(?:\[bot\])?", viewer, flags=re.ASCII):
        raise ValueError("viewer must be a GitHub login")


def _load(path: Path, repo: str, viewer: str) -> tuple[dict[str, Any], dict[str, Any]]:
    _identity(repo, viewer)
    if path.is_symlink():
        raise ValueError("the session file must not be a symlink")
    data = session.load(path)
    if not isinstance(data, dict) or not isinstance(data.get("prs"), dict):
        raise ValueError("invalid session cache")
    history = data.setdefault("action_log", {"version": 1, "repo": repo, "viewer": viewer, "actions": []})
    if not isinstance(history, dict) or history.get("version") != 1:
        raise ValueError("unsupported action log version")
    if history.get("repo") != repo or history.get("viewer") != viewer:
        raise ValueError(
            "session repository or viewer does not match; use the original account and repository"
        )
    if not isinstance(history.get("actions"), list):
        raise ValueError("invalid action log")
    for index, action in enumerate(history["actions"], 1):
        _object(action, "logged action")
        if action.get("id") != index or not isinstance(action.get("effects"), list):
            raise ValueError("invalid action log IDs or effects")
        _number(action.get("pr"), "logged PR")
        _text(action.get("head"), "logged head")
        if action.get("status") not in (
            "running",
            "finished",
            "partial",
            "failed",
            "unchanged",
            "recovered",
            "partially-recovered",
        ):
            raise ValueError("invalid logged action status")
        for effect_id, effect in enumerate(action["effects"], 1):
            _object(effect, "logged effect")
            _change(effect)
            if effect.get("id") != effect_id or effect.get("outcome") not in (
                "prepared",
                "unknown",
                "applied",
                "not-applied",
            ):
                raise ValueError("invalid logged effect ID or outcome")
            if effect["kind"] == "comment" and effect["outcome"] == "applied":
                _number(effect.get("comment_id"), "logged comment id")
                _text(effect.get("comment_updated_at"), "logged comment updated_at")
    return data, history


def _action(history: dict[str, Any], action_id: Any) -> dict[str, Any]:
    ident = _number(action_id, "action_id")
    for action in history["actions"]:
        if action["id"] == ident:
            return action
    raise ValueError(f"action {ident} is not in this session")


def _effect(action: dict[str, Any], effect_id: Any) -> dict[str, Any]:
    ident = _number(effect_id, "effect_id")
    for effect in action["effects"]:
        if effect["id"] == ident:
            return effect
    raise ValueError(f"effect {ident} is not in this action")


def _change(change: Any) -> dict[str, Any]:
    if not isinstance(change, dict) or not isinstance(change.get("kind"), str) or change["kind"] not in KINDS:
        raise ValueError("unknown effect kind")
    result = {k: change.get(k) for k in ("kind", "target", "before", "after")}
    kind = result["kind"]
    before, after = result["before"], result["after"]
    if kind in {"label", "assignee"}:
        _text(result["target"], "target")
    elif result["target"] is not None:
        raise ValueError(f"{kind} has no target")
    if kind in {"label", "assignee", "draft"}:
        if type(before) is not bool or type(after) is not bool:
            raise ValueError(f"{kind} before/after must be booleans")
    elif kind == "state":
        if (
            not isinstance(before, str)
            or not isinstance(after, str)
            or before not in {"OPEN", "CLOSED"}
            or after not in {"OPEN", "CLOSED"}
        ):
            raise ValueError("state before/after must be OPEN or CLOSED")
    elif kind == "fold":
        for value in (before, after):
            if value is not None and (not isinstance(value, str) or fold.block(value) != value):
                raise ValueError("fold before/after must be a complete Magpie block or null")
    elif kind == "comment":
        if before is not None:
            raise ValueError("only comments created by this action can be recovered")
        _text(after, "comment body")
    elif kind == "irreversible" and (
        before is not None or not isinstance(after, str) or after not in IRREVERSIBLE
    ):
        raise ValueError("unknown irreversible operation")
    if before == after:
        raise ValueError("do not journal a no-op as a mutation")
    return result


def _pull(live: dict[str, Any], repo: str, pr: int) -> None:
    _object(live, "live read")
    if live.get("number") != pr or live.get("url") != f"https://github.com/{repo}/pull/{pr}":
        raise ValueError("live read belongs to a different repository or PR")
    head = live.get("headRefOid")
    if not isinstance(head, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", head):
        raise ValueError("live read needs the full headRefOid")


def _value(effect: dict[str, Any], live: dict[str, Any]) -> Any:
    kind = effect["kind"]
    if kind in {"label", "assignee"}:
        key, field = ("labels", "name") if kind == "label" else ("assignees", "login")
        values = live.get(key)
        if not isinstance(values, list) or any(not isinstance(x, dict) or field not in x for x in values):
            raise ValueError(f"live read needs the complete {key} list")
        return effect["target"] in [x[field] for x in values]
    if kind == "draft":
        value = live.get("isDraft")
        if type(value) is not bool:
            raise ValueError("live read needs isDraft")
        return value
    if kind == "state":
        if live.get("state") not in ("OPEN", "CLOSED", "MERGED"):
            raise ValueError("live read needs state")
        return live["state"]
    if kind == "fold":
        if not isinstance(live.get("body"), str):
            raise ValueError("live read needs body")
        return fold.block(live["body"])
    raise ValueError(f"cannot read {kind} from a PR snapshot")


def _settle(action: dict[str, Any]) -> None:
    effects = action["effects"]
    failed = bool(effects) and all(e["outcome"] == "not-applied" for e in effects)
    unchanged = not effects and action["action"] not in {"skip", "skipped"}
    partial = any(e["outcome"] != "applied" for e in effects)
    action["status"] = (
        "failed" if failed else "unchanged" if unchanged else "partial" if partial else "finished"
    )


def _refresh_cache(data: dict[str, Any], log: dict[str, Any], pr: int) -> None:
    active = [a for a in log["actions"] if a["pr"] == pr and a["status"] != "recovered"]
    if not active:
        legacy = log.get("legacy_prs", {}).get(str(pr))
        if legacy is None:
            data["prs"].pop(str(pr), None)
        else:
            data["prs"][str(pr)] = copy.deepcopy(legacy)
        return
    action = active[-1]
    data["prs"][str(pr)] = {
        "head_sha": action.get("result_head", action["head"]),
        "action_taken": action["action"],
        "classification": action.get("classification"),
        "action_at": action.get("finished_at", action["started_at"]),
        "terminal": action["action"] not in {"skip", "skipped"}
        and action["status"] not in {"failed", "unchanged"},
        "journal_status": action["status"],
    }


def checkpoint(
    path: Path,
    repo: str,
    viewer: str,
    event: dict[str, Any],
    *,
    now: dt.datetime | None = None,
    ready_label: str = "ready for maintainer review",
) -> dict[str, Any]:
    """Apply one local journal transition. Mutation receipts are supplied by the skill."""
    data, history = _load(path, repo, viewer)
    _object(event, "journal event")
    at = session._iso(session._now(now))
    phase = event.get("phase")
    if phase == "begin":
        pr = _number(event.get("pr"), "pr")
        head = _text(event.get("head"), "head")
        if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", head):
            raise ValueError("head must be the full commit SHA")
        if not isinstance(event.get("action"), str) or event["action"] not in ACTIONS:
            raise ValueError("unknown triage action")
        if any(a["pr"] == pr and a["status"] == "running" for a in history["actions"]):
            raise ValueError("finish or inspect this PR's running action first")
        action = {
            "id": len(history["actions"]) + 1,
            "pr": pr,
            "head": head.lower(),
            "action": event["action"],
            "started_at": at,
            "status": "running",
            "effects": [],
        }
        if str(pr) in data["prs"] and not any(a["pr"] == pr for a in history["actions"]):
            history.setdefault("legacy_prs", {})[str(pr)] = copy.deepcopy(data["prs"][str(pr)])
        history["actions"].append(action)
        data.setdefault("started_at", at)
        result = {"action_id": action["id"]}
    else:
        action = _action(history, event.get("action_id"))
        if phase == "prepare":
            if action["status"] != "running":
                raise ValueError("cannot add an effect to a finished action")
            if action["action"] in {"skip", "skipped"}:
                raise ValueError("a skipped PR cannot have GitHub mutations")
            if any(e["outcome"] in {"prepared", "unknown"} for e in action["effects"]):
                raise ValueError("resolve the preceding operation before preparing another")
            change = _change(event.get("change"))
            live = _object(event.get("live"), "live read")
            _pull(live, repo, action["pr"])
            if live["headRefOid"].lower() != action.get("result_head", action["head"]):
                raise ValueError("head moved; reclassify before writing")
            if change["kind"] not in {"comment", "irreversible"} and _value(change, live) != change["before"]:
                raise ValueError("before state does not match the live read")
            effect = {"id": len(action["effects"]) + 1, **change, "outcome": "prepared", "at": at}
            action["effects"].append(effect)
            result = {"action_id": action["id"], "effect_id": effect["id"]}
        elif phase == "result":
            effect = _effect(action, event.get("effect_id"))
            outcome = event.get("outcome")
            if outcome not in ("applied", "not-applied", "unknown"):
                raise ValueError("outcome must be applied, not-applied or unknown")
            if effect["outcome"] not in {"prepared", "unknown"}:
                raise ValueError("operation already has a verified outcome")
            if outcome == "applied":
                if effect["kind"] == "comment":
                    receipt = _object(event.get("receipt"), "comment receipt")
                    ident = _number(receipt.get("id"), "comment id")
                    if (
                        receipt.get("issue_url")
                        != f"https://api.github.com/repos/{repo}/issues/{action['pr']}"
                        or _object(receipt.get("user"), "comment user").get("login") != viewer
                        or receipt.get("body") != effect["after"]
                    ):
                        raise ValueError("comment receipt does not match this operation and actor")
                    effect["comment_id"] = ident
                    effect["comment_updated_at"] = _text(receipt.get("updated_at"), "comment updated_at")
                elif effect["kind"] != "irreversible":
                    observed = _object(event.get("live"), "observed read")
                    _pull(observed, repo, action["pr"])
                    if _value(effect, observed) != effect["after"]:
                        raise ValueError("observed state does not confirm the write")
                else:
                    observed = _object(event.get("live"), "observed read")
                    _pull(observed, repo, action["pr"])
                    action["result_head"] = observed["headRefOid"].lower()
            effect.update(outcome=outcome, result_at=at)
            if action["status"] != "running":
                _settle(action)
                _refresh_cache(data, history, action["pr"])
            result = {"effect_id": effect["id"], "outcome": outcome}
        elif phase == "finish":
            if action["status"] != "running":
                raise ValueError("action already finished")
            action.update(finished_at=at, classification=event.get("classification"))
            _settle(action)
            _refresh_cache(data, history, action["pr"])
            result = {"action_id": action["id"], "status": action["status"]}
        elif phase == "recover":
            effect = _effect(action, event.get("effect_id"))
            if effect.get("recovered_at"):
                return {"effect_id": effect["id"], "recovered": True, "action_status": action["status"]}
            result = plan(
                path, repo, viewer, action["id"], event.get("before") or {}, ready_label=ready_label
            )
            operations = result.get("operations") or []
            if (
                result["status"] not in {"ready", "partial"}
                or not operations
                or event.get("confirmed_plan") != result.get("digest")
                or event.get("effect_id") != operations[0]["effect_id"]
            ):
                raise ValueError("recovery must match the first operation of the freshly confirmed plan")
            observed = _object(event.get("after"), "observed recovery read")
            _pull(observed, repo, action["pr"])
            if observed["headRefOid"].lower() != action.get("result_head", action["head"]):
                raise ValueError("head moved during recovery; inspect it before recording success")
            if effect["kind"] == "comment":
                if effect["comment_id"] not in observed.get("missing_comment_ids", []):
                    raise ValueError("confirm the comment is absent before recording recovery")
            elif _value(effect, observed) != effect["before"]:
                raise ValueError("observed state does not confirm recovery")
            effect["recovered_at"] = at
            remaining = [
                e for e in action["effects"] if e["outcome"] == "applied" and not e.get("recovered_at")
            ]
            if not any(e["kind"] != "irreversible" for e in remaining):
                action["status"] = "partially-recovered" if remaining else "recovered"
            _refresh_cache(data, history, action["pr"])
            result = {"effect_id": effect["id"], "recovered": True, "action_status": action["status"]}
        else:
            raise ValueError("unknown journal phase")
    session.save(path, data)
    return result


def history(path: Path, repo: str, viewer: str) -> dict[str, Any]:
    """Read-only listing: never expose note bodies in the history menu or gist."""
    data, log = _load(path, repo, viewer)
    rows = [
        {k: a[k] for k in ("id", "pr", "action", "head", "started_at", "status")}
        | {"effects": len(a["effects"])}
        for a in log["actions"]
    ]
    recorded = {str(a["pr"]) for a in log["actions"]}
    legacy = {**data["prs"], **log.get("legacy_prs", {})}
    for pr, entry in legacy.items():
        if pr not in recorded or pr in log.get("legacy_prs", {}):
            rows.append({"id": None, "pr": int(pr), "action": entry.get("action_taken"), "status": "legacy"})
    return {"repo": repo, "actions": rows}


def _inverse(effect: dict[str, Any], live: dict[str, Any], repo: str, pr: int, viewer: str) -> dict[str, Any]:
    kind, target, before = effect["kind"], effect["target"], effect["before"]
    base = ["gh", "pr", "edit", str(pr), "--repo", repo]
    if kind == "comment":
        ident = effect["comment_id"]
        if ident in live.get("missing_comment_ids", []):
            return {"argv": [], "already_restored": True}
        comments = live.get("comment_receipts", [])
        if not isinstance(comments, list) or any(not isinstance(c, dict) for c in comments):
            raise ValueError("comment_receipts must be saved comment objects")
        comment = next((c for c in comments if c.get("id") == ident), None)
        if not comment:
            raise ValueError(
                f"read comment {ident} by its exact ID before recovery; do not infer absence from a list"
            )
        if (
            comment.get("issue_url") != f"https://api.github.com/repos/{repo}/issues/{pr}"
            or _object(comment.get("user"), "comment user").get("login") != viewer
            or comment.get("body") != effect["after"]
            or comment.get("updated_at") != effect["comment_updated_at"]
        ):
            raise ValueError(f"comment {ident} changed or belongs to another actor/PR")
        return {"argv": ["gh", "api", f"repos/{repo}/issues/comments/{ident}", "-X", "DELETE"]}
    current = _value(effect, live)
    if current == before:
        return {"argv": [], "already_restored": True}
    if current != effect["after"]:
        raise ValueError(f"{kind} {target or ''} differs from the recorded result")
    if kind in {"label", "assignee"}:
        return {"argv": [*base, f"--{'add' if before else 'remove'}-{kind}", target]}
    if kind == "draft":
        return {"argv": ["gh", "pr", "ready", str(pr), "--repo", repo] + (["--undo"] if before else [])}
    if kind == "state":
        return {"argv": ["gh", "pr", "reopen" if before == "OPEN" else "close", str(pr), "--repo", repo]}
    if kind == "fold":
        body = fold.restore(live["body"], expected=effect["after"], previous=before)
        return {"argv": [*base, "--body-file", "<recovery-body-file>"], "body": body}
    raise ValueError(f"no inverse for {kind}")


def plan(
    path: Path,
    repo: str,
    viewer: str,
    action_id: int,
    live: dict[str, Any],
    *,
    ready_label: str = "ready for maintainer review",
) -> dict[str, Any]:
    """Plan against a fresh, complete PR read. Does not write local or remote state."""
    _, log = _load(path, repo, viewer)
    action = _action(log, action_id)
    result: dict[str, Any] = {
        "action_id": action_id,
        "pr": action["pr"],
        "operations": [],
        "blockers": [],
        "irreversible": [],
    }

    def blocked(reason: str) -> dict[str, Any]:
        result.update(status="blocked", operations=[])
        result["blockers"].append(reason)
        return result

    if action["status"] == "recovered":
        return result | {"status": "recovered"}
    newer = [
        a
        for a in log["actions"]
        if a["pr"] == action["pr"]
        and a["id"] > action_id
        and a["status"] != "recovered"
        and (
            a["status"] == "running"
            or any(
                e["outcome"] in {"prepared", "unknown"}
                or (e["kind"] != "irreversible" and e["outcome"] == "applied" and not e.get("recovered_at"))
                for e in a["effects"]
            )
        )
    ]
    if newer:
        return blocked("revisit the newest action on this PR first")
    if action["status"] == "running":
        return blocked("finish or inspect the interrupted action first")
    if any(e["outcome"] in {"prepared", "unknown"} for e in action["effects"]):
        return blocked("an operation has an unverified outcome; verify its receipt before recovery")
    _pull(live, repo, action["pr"])
    if (
        live.get("state") not in ("OPEN", "CLOSED", "MERGED")
        or "mergedAt" not in live
        or type(live.get("isDraft")) is not bool
    ):
        raise ValueError("recovery needs state, mergedAt and isDraft from the complete PR read")
    for field in ("comment_receipts", "missing_comment_ids"):
        if field in live and not isinstance(live[field], list):
            raise ValueError(f"{field} must be an array")
    for ident in live.get("missing_comment_ids", []):
        _number(ident, "missing comment id")
    if live["headRefOid"].lower() != action.get("result_head", action["head"]):
        return blocked("the head moved; inspect and reclassify this PR")
    if live.get("state") == "MERGED" or live.get("mergedAt"):
        return blocked("the PR was merged; do not reverse triage state")
    # Work on a copy: later inverse steps must see the state earlier inverses produce.
    simulated = copy.deepcopy(live)
    for effect in reversed(action["effects"]):
        if effect["outcome"] != "applied" or effect.get("recovered_at"):
            continue
        if effect["kind"] == "irreversible":
            result["irreversible"].append(effect["after"])
            continue
        try:
            operation = _inverse(effect, simulated, repo, action["pr"], viewer)
        except ValueError as exc:
            return blocked(str(exc))
        restoring_ready = (effect["kind"] == "draft" and effect["before"] is False) or (
            effect["kind"] == "label" and effect["target"] == ready_label and effect["before"] is True
        )
        if restoring_ready and operation["argv"]:
            gate = guards.check(
                "mark-ready",
                expected_head=action.get("result_head", action["head"]),
                liveness={
                    "head_sha": live["headRefOid"],
                    "mergeable": live.get("mergeable", "UNKNOWN"),
                    "merge_state": live.get("mergeStateStatus"),
                },
                runs=live.get("workflow_runs"),
            )
            if not gate["proceed"]:
                return blocked(gate["reason"])
        result["operations"].append({"effect_id": effect["id"], "kind": effect["kind"], **operation})
        kind = effect["kind"]
        if kind in {"label", "assignee"}:
            key, field = ("labels", "name") if kind == "label" else ("assignees", "login")
            simulated[key] = [x for x in simulated[key] if x[field] != effect["target"]]
            if effect["before"]:
                simulated[key].append({field: effect["target"]})
        elif kind == "draft":
            simulated["isDraft"] = effect["before"]
        elif kind == "state":
            simulated["state"] = effect["before"]
        elif kind == "fold":
            if "body" in operation:
                simulated["body"] = operation["body"]
    result["status"] = "partial" if result["irreversible"] else "ready"
    if not result["operations"]:
        result["status"] = "irreversible" if result["irreversible"] else "nothing-to-undo"
    result["notifications_recalled"] = False
    result["requires_confirmation"] = bool(result["operations"])
    # Bind confirmation to the exact preview and input read, including author edits.
    result["digest"] = hashlib.sha256(json.dumps([result, live], sort_keys=True).encode()).hexdigest()
    return result
