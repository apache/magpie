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
"""The fix flow, the backport labels and when the adversarial reviewers run.

- `flow` reads `magpie-vcs fix-flow`'s exit and JSON: `pull-request` runs
  every step as written; `patch-then-commit` (Subversion) takes the
  private-patch flow with no PR; exit `2` (the working copy contradicts the
  manifest, or an unknown value) stops.
- `backport` (5e): a milestone whose `X.Y` is the next `<default-branch>`
  release needs no label; any other `X.Y` is a patch release on its own
  branch and needs `backport-to-vX-Y-test` (the project's template), plus
  every further line the team confirmed.
- `review_plan` (Step 7): a security skill runs the configured reviewers
  whenever at least one is listed, whatever `mode` says; no file or no
  reviewer skips silently, a missing plugin skips with one line. The command
  is spelled with the literal `~` the sandbox exclusion matches.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.shared.rollup import one_line
from security_management.shell import dq, w

LABEL = "backport-to-v{major}-{minor}-test"
REVIEW = "uvx --from ~/.claude/magpie/adversarial-review adversarial-review run"
_VERSION = re.compile(r"\b(\d+)\.(\d+)(?:\.(\d+))?\b")


def flow(data: Mapping[str, Any]) -> dict[str, Any]:
    if int(data.get("exit") or 0) != 0:
        return {
            "ok": True,
            "flow": "stop",
            "follow_subversion_flow": False,
            "open_pr": False,
            "reason": one_line(data.get("error"))
            or "the working copy contradicts the manifest: stop and report it",
        }
    chosen = str((data.get("result") or {}).get("flow") or "")
    if chosen == "pull-request":
        return {
            "ok": True,
            "flow": chosen,
            "follow_subversion_flow": False,
            "open_pr": True,
            "reason": "every step runs as written",
        }
    if chosen == "patch-then-commit":
        return {
            "ok": True,
            "flow": chosen,
            "follow_subversion_flow": True,
            "open_pr": False,
            "reason": "Steps 0, 7, 8, 9, 10 and 11 follow subversion-flow.md: a private patch first, a commit once cleared",
        }
    return {"ok": False, "refused": f"fix-flow printed no known flow ({chosen!r})"}


def _xy(text: object) -> tuple[int, int] | None:
    match = _VERSION.search(str(text or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def backport(data: Mapping[str, Any]) -> dict[str, Any]:
    milestone = one_line(data.get("milestone"))
    target = _xy(milestone)
    main = _xy(data.get("main_version"))
    if target is None or main is None:
        return {
            "ok": False,
            "refused": "need a milestone with a version and the next main-branch release (main_version)",
        }
    template = str(data.get("label_template") or LABEL)
    lines = [] if target == main else [target]
    for extra in data.get("extra_lines") or []:
        line = _xy(extra)
        if line is None:
            return {"ok": False, "refused": f"{extra!r} names no release line"}
        if line != main and line not in lines:
            lines.append(line)
    labels = [template.format(major=a, minor=b) for a, b in lines]
    return {
        "ok": True,
        "milestone": milestone,
        "backport_needed": bool(labels),
        "backport_labels": labels,
        "rationale": "the next main-branch release: the fix lands on main directly"
        if not labels
        else f"patch release line(s) {', '.join(f'{a}.{b}' for a, b in lines)} need their backport label(s)",
    }


def review_plan(data: Mapping[str, Any]) -> dict[str, Any]:
    reviewers = [one_line(r) for r in data.get("reviewers") or [] if one_line(r)]
    if not data.get("config_found") or not reviewers:
        return {"ok": True, "run": False, "skip_notice": "silent", "command": None}
    if not data.get("plugin_installed"):
        return {
            "ok": True,
            "run": False,
            "skip_notice": "one-line",
            "message": "adversarial review skipped: the magpie-adversarial-review plugin is not installed",
            "command": None,
        }
    title = one_line(data.get("title"))
    body_file = one_line(data.get("body_file"))
    if not title or not body_file:
        return {"ok": False, "refused": "the review runs on the final PR title and body file: pass both"}
    command = (
        f"{REVIEW} --project-root {w(data['project_root'])} --repo-dir {w(data['repo_dir'])} "
        f"--base {w(data.get('base') or 'origin/main')} --title {dq(title)} --body-file {w(body_file)}"
    )
    return {
        "ok": True,
        "run": True,
        "skip_notice": None,
        "title_passed": title,
        "body_file_passed": body_file,
        "command": command,
    }
