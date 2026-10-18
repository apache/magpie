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
"""The review session: what happened to each PR, the GitHub calls spent, and the Step 3 summary.

The file is scratch state for one session — the skill never writes a session
log anywhere else.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

#: GitHub calls a normal pass spends per reviewed PR (the read, the diff, the post).
CALLS_PER_PR = 3
#: A pass that crosses this many calls is mis-batching: stop and fix the call pattern.
BUDGET_ALARM = 100

OUTCOMES = ("APPROVE", "REQUEST_CHANGES", "COMMENT", "skipped", "slop-comment", "slop-close", "dry-run")


def _load(path: Path) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"started_at": None, "prs": {}, "calls": 0}


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".cr-session-")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(temp, path)


def record(
    path: Path,
    *,
    pr: int,
    outcome: str,
    reason: str | None = None,
    adversarial: bool | None = None,
    calls: int = 0,
    now: dt.datetime,
) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome {outcome!r} is not one of {', '.join(OUTCOMES)}")
    data = _load(path)
    data["started_at"] = data.get("started_at") or now.isoformat()
    data["prs"][str(pr)] = {
        "outcome": outcome,
        "reason": reason,
        "adversarial": adversarial,
        "at": now.isoformat(),
    }
    data["calls"] = int(data.get("calls") or 0) + calls
    _write(path, data)
    return {"recorded": pr, "calls": data["calls"], "over_budget": data["calls"] > BUDGET_ALARM}


def summary(path: Path, *, untouched: int = 0, now: dt.datetime) -> dict[str, Any]:
    data = _load(path)
    prs = data.get("prs") or {}
    counts = Counter(v["outcome"] for v in prs.values())
    started = dt.datetime.fromisoformat(data["started_at"]) if data.get("started_at") else now
    minutes = max(1, int((now - started).total_seconds() // 60))
    reviewed = sum(counts[k] for k in ("APPROVE", "REQUEST_CHANGES", "COMMENT"))
    skipped = [{"pr": int(k), "reason": v.get("reason")} for k, v in prs.items() if v["outcome"] == "skipped"]
    covered = sorted(int(k) for k, v in prs.items() if v.get("adversarial"))
    uncovered = sorted(int(k) for k, v in prs.items() if v.get("adversarial") is False)
    lines = [
        f"Reviewed: {reviewed}  (APPROVE {counts['APPROVE']}, REQUEST_CHANGES {counts['REQUEST_CHANGES']}, "
        f"COMMENT {counts['COMMENT']})",
        f"Skipped: {len(skipped)}"
        + (
            ""
            if not skipped
            else "  — " + "; ".join(f"#{s['pr']}: {s['reason'] or 'no reason given'}" for s in skipped)
        ),
        f"Untouched: {untouched}",
        f"Slop exits: {counts['slop-comment'] + counts['slop-close']}  •  Dry-run drafts: {counts['dry-run']}",
        f"Adversarial coverage: {', '.join(f'#{n}' for n in covered) or 'none'}"
        + (f"; without: {', '.join(f'#{n}' for n in uncovered)}" if uncovered else ""),
        f"Time: {minutes} min  •  {round(reviewed * 60 / minutes, 1)} PRs/hour  •  GitHub calls: {data.get('calls', 0)}",
    ]
    return {
        "counts": dict(counts),
        "skipped": skipped,
        "untouched": untouched,
        "minutes": minutes,
        "calls": data.get("calls", 0),
        "text": "\n".join(lines),
    }
