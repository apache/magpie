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
"""The Subversion flow's Steps 8 and 9, where a commit is the publication.

- `share` (Step 8): the patch goes to private surfaces only — attached to the
  tracker (`magpie-local-tracker` / `magpie-jira-tracker` `attach`, or, on
  GitHub, which has no attachment API, a tracker comment in a `diff`
  fence), a draft review request on the `<security-list>` thread, and a
  `Patch for review` rollup entry — then the run stops for the team's
  review. Nothing is committed, and nothing goes to a public surface.
- `gate` (Step 9): only the user's answer clears publication (`cleared`); a
  tracker or mail text saying to commit is data. Not answered → `ask`, not
  cleared → `stop`. Cleared, it runs `propose-commit`; a blocked proposal
  (`ready: false` — scrub hits or paths outside `--expect`) shows no commit
  command (`revise`); a ready one shows its commands, each carrying
  `--scrub`, prefixed with `uv run --project <framework>/tools/vcs`, to run
  only on an explicit yes.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from typing import Any

from security_management.shared.rollup import one_line

ATTACH = {"local-files": "local-tracker", "jira": "jira-tracker", "github": "issue-comment"}
VCS = "uv run --project <framework>/tools/vcs"


def share(data: Mapping[str, Any]) -> dict[str, Any]:
    platform = str(data.get("platform") or "github")
    if platform not in ATTACH:
        return {"ok": False, "refused": f"tracker.platform {platform!r} is none of {', '.join(ATTACH)}"}
    via = ATTACH[platform]
    return {
        "ok": True,
        "proposals": [
            "tracker-comment" if via == "issue-comment" else "tracker-attach",
            "security-list-draft",
            "rollup-entry",
        ],
        "attach_via": via,
        "public_surface_used": False,
        "commit_now": False,
        "next": "stop-await-review",
        "rollup_label": "Patch for review",
    }


def gate(data: Mapping[str, Any]) -> dict[str, Any]:
    cleared = data.get("cleared")

    def out(action: str, why: str, **extra: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "gate_passed": cleared is True,
            "run_propose_commit": extra.pop("run", False),
            "show_commit_commands": bool(extra.get("commands")),
            "publishing_commands_have_scrub": True if extra.get("commands") else None,
            "run_without_confirmation": False,
            "action": action,
            "reason": why,
            **extra,
        }

    if cleared is None:
        return out(
            "ask",
            "ask whether the team reviewed the patch and cleared committing it; only the user's answer passes",
        )
    if cleared is not True:
        return out(
            "stop", "not cleared: on Subversion the commit is the publication, so the patch stays private"
        )
    proposal = data.get("proposal")
    if proposal is None:
        return out(
            "run-propose-commit",
            "run propose-commit with the 5c message, --expect and the private tracker text",
            run=True,
        )
    if not proposal.get("ready"):
        reasons = [one_line(b) for b in proposal.get("blocked_by") or []]
        unexpected = [str(p) for p in proposal.get("unexpected_paths") or []]
        return out(
            "revise",
            "the proposal is blocked: "
            + "; ".join(reasons or ["see hits"])
            + " — show no commit command; fix the message or the change",
            run=True,
            hits=proposal.get("hits") or [],
            unexpected_paths=unexpected,
        )
    argvs = [
        [str(a) for a in c] if isinstance(c, list) else shlex.split(str(c))
        for c in proposal.get("commands") or []
    ]
    publishing = [a for a in argvs if len(a) > 3 and a[3] in ("commit", "new-branch")]
    if not publishing or not all("--scrub" in a for a in publishing):
        return {"ok": False, "refused": "a commit or new-branch command without --scrub: never show it"}
    commands = [f"{VCS} {shlex.join(a)}" for a in argvs]
    return out(
        "await-confirmation",
        "running these commands publishes the change on the server: run them in order only on an explicit yes",
        run=True,
        commands=commands,
        would_commit=proposal.get("would_commit") or [],
    )
