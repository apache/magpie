#
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
"""
Tracker operations on a non-GitHub security tracker.

The policy's ``[tracker] platform`` selects where the tracker lives (see
``tools/security-tracker/contract.md``). On ``github`` nothing here runs. On
``local-files`` or ``jira`` every catalogue operation that addresses the
tracker is translated into a call of that backend's CLI —
``magpie-local-tracker`` or ``magpie-jira-tracker`` — instead of ``gh``.

The translation keeps every property the ``gh`` builders have:

* The executable and the backend's script name are fixed here; the policy
  supplies only the backend's project directory and its pinned settings (the
  tracker folder, or the Jira URL, project and security level), never a command.
  A caller cannot point an operation at another folder or another Jira project.
* Parameters arrive already validated by the dispatcher, are placed as single
  argv elements, and run without a shell. Free-text values (titles, search
  words) are attached as ``--opt=value``, so even a value that begins with a
  dash is read as the option's value, never as another option.
* Bodies still travel on stdin: every body parameter becomes ``-``, which both
  backends read from stdin.
* An operation with no counterpart on the backend (project boards, milestone
  administration, the collaborator roster, legacy-comment folding) is refused
  by name rather than approximated.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .ops import ParamError

PLATFORMS = ("github", "local-files", "jira")

#: platform -> (tool directory name, console script).
BACKEND_SCRIPTS = {
    "local-files": ("local-tracker", "magpie-local-tracker"),
    "jira": ("jira", "magpie-jira-tracker"),
}


@dataclass(frozen=True)
class TrackerBackend:
    """The resolved ``[tracker]`` policy for a non-GitHub backend."""

    platform: str
    #: Absolute path of the backend's tool directory (``tools/local-tracker``).
    project: str
    #: local-files: absolute path of the tracker folder.
    root: str = ""
    #: jira: pinned target.
    jira_url: str = ""
    jira_project: str = ""
    jira_security_level: str = ""
    jira_cloud: bool = False

    def prefix(self) -> list[str]:
        _, script = BACKEND_SCRIPTS[self.platform]
        argv = ["uv", "run", "--quiet", "--project", self.project, script]
        if self.platform == "local-files":
            return [*argv, "--root", self.root]
        argv += [
            "--url",
            self.jira_url,
            "--project",
            self.jira_project,
            "--security-level",
            self.jira_security_level,
        ]
        return [*argv, "--jira-cloud"] if self.jira_cloud else argv


@dataclass(frozen=True)
class BackendCall:
    """A translated operation: the argv to run, body (if any) on stdin."""

    argv: list[str]
    op: str


def _close_reason(reason: str) -> str:
    return (
        "not-planned"
        if reason.strip().lower().replace("_", " ") in {"not planned", "not-planned"}
        else "completed"
    )


Translate = Callable[[dict[str, str]], list[str]]

#: Catalogue operation -> contract subcommand argv (after the backend prefix).
#: Keyed by vetted-op name; this is the mapping the security skills' `gh`
#: commands reach through, documented in tools/security-tracker/contract.md.
TRANSLATIONS: dict[str, Translate] = {
    "issue-view": lambda p: ["view", p["number"]],
    "issue-list": lambda p: ["list", "--state", p["state"], "--limit", "1000"],
    "issue-list-label": lambda p: ["list", "--state", p["state"], "--label", p["label"], "--limit", "1000"],
    "issue-comments": lambda p: ["view", p["number"], "--comments"],
    "issue-search": lambda p: ["list", "--state", "all", f"--search={p['query']}", "--limit", "100"],
    "label-list": lambda p: ["labels"],
    "issue-create": lambda p: ["create", f"--title={p['title']}", "--body-file", "-"],
    "issue-add-label": lambda p: ["edit", p["number"], "--add-label", p["label"]],
    "issue-remove-label": lambda p: ["edit", p["number"], "--remove-label", p["label"]],
    "issue-set-milestone": lambda p: ["edit", p["number"], "--milestone", p["milestone"]],
    "issue-add-assignee": lambda p: ["edit", p["number"], "--add-assignee", p["login"]],
    "issue-remove-assignee": lambda p: ["edit", p["number"], "--remove-assignee", p["login"]],
    "issue-comment": lambda p: ["comment", p["number"], "--body-file", "-"],
    "issue-edit-body": lambda p: ["edit", p["number"], "--body-file", "-"],
    "issue-edit-title": lambda p: ["edit", p["number"], f"--title={p['title']}"],
    "issue-close": lambda p: ["close", p["number"], "--reason", _close_reason(p["reason"])],
    "issue-reopen": lambda p: ["reopen", p["number"]],
    "rollup-append": lambda p: [
        "rollup-append",
        p["number"],
        "--action",
        p["action"],
        "--entry-body-file",
        "-",
    ],
    "rollup-amend-latest": lambda p: [
        "rollup-amend-latest",
        p["number"],
        "--action",
        p["action"],
        "--entry-body-file",
        "-",
    ],
    "body-field-get": lambda p: ["field-get", p["number"], p["field"]],
    "body-field-set": lambda p: ["field-set", p["number"], p["field"], "--value-file", "-"],
    "tracker-pending": lambda p: ["pending"],
    "tracker-publish": lambda p: ["publish", "--message-file", "-", "--push"],
}

#: Tracker operations with no counterpart on a non-GitHub backend, and why.
NOT_ON_BACKEND: dict[str, str] = {
    "milestone-list": "milestones are free values here; the policy's `milestones` list is the set",
    "milestone-create": "milestones are free values here and need no creating",
    "milestone-close": "milestones are free values here and are never closed",
    "collaborators": "the security-team roster comes from release-trains.md, not the tracker",
    "comment-update": "the status rollup is kept by rollup-append / rollup-amend-latest",
    "rollup-fold": "there are no legacy bot comments to fold on this backend",
    "board-add-item": "this backend has no project board",
    "board-archive-item": "this backend has no project board",
    "board-set-status": "this backend has no project board",
}

#: Operations that only exist for a working-copy or non-GitHub backend.
GITHUB_NOT_APPLICABLE = {
    "tracker-pending": "GitHub tracker writes are visible as soon as they return; there is nothing pending",
    "tracker-publish": "GitHub tracker writes are visible as soon as they return; there is nothing to publish",
}


def is_tracker_op(name: str) -> bool:
    return name in TRANSLATIONS or name in NOT_ON_BACKEND


def translate(backend: TrackerBackend, op_name: str, params: dict[str, str]) -> BackendCall:
    if op_name in NOT_ON_BACKEND:
        raise ParamError(
            f"{op_name!r} is not available on the {backend.platform} tracker: {NOT_ON_BACKEND[op_name]}"
        )
    if op_name in {"tracker-pending", "tracker-publish"} and backend.platform != "local-files":
        raise ParamError(
            f"{op_name!r} is not applicable on the {backend.platform} tracker: its writes are immediate"
        )
    translate_fn = TRANSLATIONS.get(op_name)
    if translate_fn is None:  # pragma: no cover - guarded by is_tracker_op
        raise ParamError(f"{op_name!r} has no {backend.platform} translation")
    return BackendCall(argv=[*backend.prefix(), *translate_fn(params)], op=op_name)
