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
"""The optional APPROVE action's safety protocol, and the quick-merge session file.

`approve-check` decides — from fresh reads saved just before the approve —
whether the maintainer may submit it: approvals enabled, the diff viewed this
session (when required), the head unchanged since the screen, every Stage-1
gate still green, the branch still not conflicting. It prints the exact
`gh pr review` command; the maintainer confirms and the agent runs it.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .. import ci
from ..config import Config
from . import screen
from .config import QuickMergeConfig

#: Appended to an adopter-configured `approve_body`, which is agent-posted prose.
ATTRIBUTION = "\n\n<sub>_Approved by `@{viewer}` after the quick-merge screen — automated triage may be imperfect; a maintainer takes the next look._</sub>\n"


def read_session(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"viewed": {}, "approved": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"viewed": {}, "approved": {}}
    data.setdefault("viewed", {})
    data.setdefault("approved", {})
    return data


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".quick-merge-session.")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def record(path: Path, kind: str, number: int, head: str, now: dt.datetime) -> dict[str, Any]:
    data = read_session(path)
    bucket = "viewed" if kind == "view" else "approved"
    data[bucket][str(number)] = {"head": head, "at": now.isoformat()}
    _write(path, data)
    return {"recorded": kind, "pr": number, "head": head, "session": str(path)}


def check(
    saved: Path,
    cfg: Config,
    qcfg: QuickMergeConfig,
    *,
    number: int,
    head: str,
    session: dict[str, Any],
    out_dir: Path | None,
    viewer: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"pr": number, "proceed": False}

    def refuse(reason: str, **extra: Any) -> dict[str, Any]:
        result.update(reason=reason, **extra)
        return result

    if not qcfg.enable_approve:
        return refuse("enable_approve is false: this project runs quick-merge read-only")
    viewed = session.get("viewed", {}).get(str(number))
    if qcfg.approve_requires_diff_view and not viewed:
        return refuse("view the diff first ([V]), then approve — approve_requires_diff_view is on")
    fresh = [(pr, files) for pr, files in screen.load(saved, number) if pr.number == number]
    missing = [
        need
        for need, path in (
            (
                {"op": "gql-pr-express-one", "params": [str(number)], "save": screen.one_file(number)},
                screen.one_file(number),
            ),
            (
                {"op": "pr-live-state", "params": [str(number)], "save": screen.live_file(number)},
                screen.live_file(number),
            ),
            (
                {"op": "runs-action-required", "params": [], "save": screen.ACTION_REQUIRED},
                screen.ACTION_REQUIRED,
            ),
        )
        if not (saved / path).is_file()
    ]
    # Every read the approval stands on is fresh and present: none is optional.
    if missing or not fresh:
        return refuse(
            "re-read the PR first",
            needs=missing
            or [{"op": "gql-pr-express-one", "params": [str(number)], "save": screen.one_file(number)}],
        )
    pr, files = fresh[0]
    if not pr.head_sha.startswith(head[:7]) and not head.startswith(pr.head_sha[:7]):
        return refuse(f"the head moved ({head[:7]} → {pr.head_sha[:7]}) since the screen — re-screen this PR")
    if viewed and not pr.head_sha.startswith(str(viewed.get("head", ""))[:7]):
        return refuse("the diff you viewed is not the current head — view it again")
    action_required = ci.load_action_required(saved / screen.ACTION_REQUIRED)
    gate, why = screen.stage1(pr, cfg, action_required)
    if gate:
        return refuse(f"a gate regressed since the screen: {why}")
    # The change must still be trivial: files can move into a deny path, or past
    # the size budget, between the screen and the approval.
    drop, _tier, why = screen.stage2(pr, files, qcfg, qcfg.default_tiers, qcfg.max_churn)
    if drop:
        return refuse(f"the change is no longer an express-lane candidate: {why}")
    live = json.loads((saved / screen.live_file(number)).read_text(encoding="utf-8"))
    if live.get("mergeable") is False or str(live.get("mergeable_state")).lower() == "dirty":
        return refuse("the branch now conflicts — nothing to approve into")
    repo = cfg.upstream_repo or ""
    body_file = None
    if qcfg.approve_body:
        if out_dir is None:
            return refuse("approve_body is set: pass --out-dir for the review body file")
        if not viewer or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", viewer):
            return refuse("approve_body is set: pass --viewer <login> for the body's credit line")
        out_dir.mkdir(parents=True, exist_ok=True)
        body = out_dir / f"pr-{number}-approve.md"
        body.write_text(qcfg.approve_body.strip() + ATTRIBUTION.format(viewer=viewer), encoding="utf-8")
        body_file = str(body)
    item = screen.Screened(pr, [])
    screen._load_review(item, saved, required=False)
    required = item.review.get("required_approvals")
    approvals = item.review.get("approvals")
    note = None
    if isinstance(required, int) and isinstance(approvals, int) and approvals + 1 < required:
        note = f"the repo requires {required} approvals; this adds 1 ({approvals + 1} of {required})"
    result.update(
        proceed=True,
        command=screen.approve_command(number, repo, body_file),
        confirm=f"Submit an APPROVE review on #{number}? This is your maintainer review of this change. [y/N]",
        note=note,
        merge_command=screen.merge_command(qcfg.merge_template, number, repo),
    )
    return result
