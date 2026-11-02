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
"""The session cache and the Step 6 session summary.

The cache is one JSON file for the session: `prs` maps a PR number to the head
SHA it was handled at and what was done. `triage classify --session` reads the
same file and silently suppresses a PR carrying a terminal action at an
unchanged head. Writes are atomic (temp file, fsync, rename): a half-written
cache would block the rest of the session.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

#: Action → the summary line's label, in the order the summary prints them.
ACTION_LABELS: dict[str, str] = {
    "draft": "drafted",
    "comment": "commented",
    "close": "closed",
    "rebase": "rebased",
    "rerun": "reruns triggered",
    "mark-ready": "marked ready",
    "request-author-confirmation": "author-confirm requests",
    "ping": "pings posted",
    "promote-bot-draft": "bot drafts promoted",
    "approve-workflow": "workflow approvals",
    "flag-suspicious": "suspicious flags",
    "strip-ready-label": "ready labels stripped",
}

#: Actions that change the PR, so an unchanged head has nothing new to read.
TERMINAL = frozenset(ACTION_LABELS)

#: Skip reasons, keyed by pre-filter or decision row, grouped for the summary.
SKIP_GROUPS: dict[str, str] = {
    "3": "already triaged / inside grace",
    "4": "already triaged / inside grace",
    "grace": "already triaged / inside grace",
    "14b": "awaiting author confirmation",
    "19": "already ready",
    "F4": "already ready",
    "F2": "bot",
    "F1": "collaborator",
    "F3": "recent draft",
    "F5a": "maintainer conversation",
    "F5b": "maintainer conversation",
    "F5c": "maintainer conversation",
    "F6": "maintainer conversation",
    "6": "own PR",
    "7a": "too fresh",
    "0": "abandoned first-time PR",
    "5": "stale draft (sweep)",
    "22": "state not settled",
    "pending": "CI running",
    "backport": "backport branch",
}


def _now(now: dt.datetime | None) -> dt.datetime:
    return now or dt.datetime.now(dt.UTC)


def _iso(at: dt.datetime) -> str:
    return at.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"prs": {}}
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    data.setdefault("prs", {})
    return data


def save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def record(
    path: Path,
    *,
    pr: int,
    head: str,
    action: str,
    classification: str | None = None,
    terminal: bool | None = None,
    reason: str | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    data = load(path)
    at = _now(now)
    data.setdefault("started_at", _iso(at))
    entry = {
        "head_sha": head,
        "classification": classification,
        "action_taken": action,
        "action_at": _iso(at),
        "terminal": action in TERMINAL if terminal is None else terminal,
    }
    if reason:
        entry["reason"] = reason
    data["prs"][str(pr)] = entry
    save(path, data)
    return entry


def _minutes(start: dt.datetime, end: dt.datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def summary(
    path: Path, *, classify: dict[str, Any] | None = None, now: dt.datetime | None = None
) -> dict[str, Any]:
    data = load(path)
    end = _now(now)
    started_raw = data.get("started_at")
    start = dt.datetime.fromisoformat(started_raw.replace("Z", "+00:00")) if started_raw else end
    prs: dict[str, dict[str, Any]] = data["prs"]

    acted: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    for entry in prs.values():
        action = entry.get("action_taken")
        if action in ACTION_LABELS:
            acted[action] += 1
        elif action in ("skip", "skipped"):
            skipped[entry.get("reason") or "skipped by maintainer"] += 1

    pending: list[int] = []
    presented = len(prs)
    if classify:
        for key, count in (classify.get("filtered") or {}).items():
            skipped[SKIP_GROUPS.get(str(key), str(key))] += int(count)
        for item in classify.get("skipped") or []:
            skipped[SKIP_GROUPS.get(str(item.get("row")), str(item.get("reason") or item.get("row")))] += 1
        for group in classify.get("groups") or []:
            for item in group.get("prs") or []:
                if str(item["number"]) not in prs:
                    pending.append(int(item["number"]))
        presented = len(prs) + len(pending)

    actions_total = sum(acted.values())
    minutes = _minutes(start, end)
    per_hour = round(actions_total * 60 / minutes) if minutes else actions_total
    lines = [
        f"Session summary — {start.strftime('%Y-%m-%d %H:%M')} UTC → {end.strftime('%H:%M')} UTC ({minutes}m)",
        "",
        f"PRs presented:  {presented}",
        f"PRs acted on:    {actions_total}",
    ]
    for action, label in ACTION_LABELS.items():
        if acted[action]:
            lines.append(f"  - {label + ':':<19} {acted[action]}")
    skipped_total = sum(skipped.values())
    breakdown = ", ".join(f"{count} {reason}" for reason, count in skipped.most_common())
    lines.append(f"PRs skipped:     {skipped_total}" + (f"   ({breakdown})" if breakdown else ""))
    lines.append(
        f"PRs left pending: {len(pending)}"
        + ("   (classified but the group was not decided)" if pending else "")
    )
    lines += ["", f"Throughput: {actions_total} actions / {minutes}m = {per_hour} PRs/h"]
    text = "\n".join(lines)
    result = {
        "started_at": _iso(start),
        "ended_at": _iso(end),
        "minutes": minutes,
        "presented": presented,
        "acted": {ACTION_LABELS[a]: c for a, c in acted.items()},
        "acted_total": actions_total,
        "skipped": dict(skipped),
        "skipped_total": skipped_total,
        "pending": sorted(pending),
        "per_hour": per_hour,
        "text": text,
    }
    data["last_summary"] = {k: v for k, v in result.items() if k != "text"}
    save(path, data)
    return result
