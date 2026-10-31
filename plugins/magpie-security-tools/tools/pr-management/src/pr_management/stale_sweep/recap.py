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
"""pr-stale-sweep Steps 6-7: what happened to each PR, and the recap.

`record` appends one outcome per PR to the session file; `recap` reads it with
the classification the sweep saved and prints the counts and per-PR lines,
every PR reference a markdown link.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

OUTCOMES = ("posted", "closed", "skipped", "failed")
_URL = re.compile(r"^https://github\.com/[A-Za-z0-9._/-]+(#[A-Za-z0-9_-]+)?$")


def _read(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"prs": {}}
    return {"prs": {}}


def record(path: Path, number: int, cls: str, outcome: str, comment_url: str | None) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    if comment_url is not None and not _URL.match(comment_url):
        raise ValueError(f"{comment_url!r} is not a GitHub URL")
    data = _read(path)
    entry = data["prs"].setdefault(str(number), {"class": cls})
    entry["class"] = cls
    if outcome == "closed":
        entry["closed"] = True
    else:
        entry["outcome"] = outcome
    if comment_url:
        entry["comment_url"] = comment_url
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".stale-session.")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(temp, path)
    return {"recorded": True, "pr": number, **entry}


def recap(session: dict[str, Any], classified: dict[str, Any], upstream: str) -> dict[str, Any]:
    def link(number: int | str) -> str:
        return f"[#{number}](https://github.com/{upstream}/pull/{number})"

    prs = session.get("prs", {})
    counts = {
        "request_update_count": 0,
        "close_stale_count": 0,
        "closed_count": 0,
        "skipped_count": 0,
        "security_flagged_count": 0,
        "maintainer_court_count": 0,
    }
    lines: list[str] = []
    for proposal in classified.get("proposals", []):
        number = str(proposal["number"])
        entry = prs.get(number, {})
        cls = proposal["class"]
        outcome = entry.get("outcome", "skipped")
        if outcome == "posted":
            counts["request_update_count" if cls == "REQUEST-UPDATE" else "close_stale_count"] += 1
        else:
            counts["skipped_count"] += 1
        if entry.get("closed"):
            counts["closed_count"] += 1
        where = entry.get("comment_url")
        detail = f"comment posted: {where}" if outcome == "posted" and where else outcome
        if entry.get("closed"):
            detail += "; PR closed"
        lines.append(f"- {link(number)} — {cls} — {detail}")
    security = [s for s in classified.get("skipped", []) if s["class"] == "SKIP-SECURITY"]
    court = [s for s in classified.get("skipped", []) if s["class"] == "SKIP-MAINTAINER-COURT"]
    counts["security_flagged_count"] = len(security)
    counts["maintainer_court_count"] = len(court)
    for skipped in classified.get("skipped", []):
        lines.append(f"- {link(skipped['number'])} — {skipped['class']} — not touched ({skipped['reason']})")
    summary = (
        f"{counts['request_update_count']} REQUEST-UPDATE comments posted, "
        f"{counts['close_stale_count']} CLOSE-STALE comments posted, {counts['closed_count']} PRs closed, "
        f"{counts['skipped_count']} skipped, {counts['security_flagged_count']} security-flagged (not touched), "
        f"{counts['maintainer_court_count']} maintainer-court (not touched)."
    )
    notes: list[str] = []
    if security:
        notes.append(
            "Security-flagged PRs were skipped and still need a manual review — they may need confidential "
            "handling: " + ", ".join(link(s["number"]) for s in security) + "."
        )
    if court:
        notes.append(
            "Maintainer-court PRs were skipped: their authors are waiting on a maintainer response, which the "
            "maintainers still owe: " + ", ".join(link(s["number"]) for s in court) + "."
        )
    notes.append("Label changes and any state change beyond closing stay with you, not with this skill.")
    text = "\n".join([summary, "", *lines, "", *notes]) + "\n"
    return {**counts, "recap_text": text}
