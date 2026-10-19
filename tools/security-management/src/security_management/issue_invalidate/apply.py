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
"""Steps 5a, 5c and 6: the label change, the board queries and the ordered apply commands.

Labels: add `invalid`; remove `needs triage`, the scope label and `pr created` /
`pr merged` when set; `security issue` always stays. The board read and the
`archiveProjectV2Item` mutation are written as query files and run with
`-F query=@<file>` (never `deleteProjectV2Item`). The apply plan is the 6a-6f
order for one tracker: rollup first (its URL feeds the closing comment),
then comment, labels, close as `not planned`, archive, and the draft-id amend.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shell import dq, w

INVALID = "invalid"
KEEP = "security issue"
PR_LABELS = ("pr created", "pr merged")
VETTED = "uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-invalidate"

BOARD_READ = """query($n: Int!) {
  repository(owner: "{owner}", name: "{name}") {
    issue(number: $n) {
      projectItems(first: 5) {
        nodes { id isArchived project { number } }
      }
    }
  }
}
"""
BOARD_ARCHIVE = """mutation($pid: ID!, $iid: ID!) {
  archiveProjectV2Item(input: { projectId: $pid, itemId: $iid }) {
    item { id isArchived }
  }
}
"""


def _names(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        value = value.get("nodes") or []
    return [str(v.get("name") if isinstance(v, Mapping) else v) for v in value or []]


def labels(data: Mapping[str, Any]) -> dict[str, Any]:
    current = _names(data.get("labels"))
    scopes = [str(s) for s in data.get("scope_labels") or []]
    needs_triage = str(data.get("needs_triage_label") or "needs triage")
    remove = [lbl for lbl in current if lbl == needs_triage]
    remove += [lbl for lbl in current if lbl in scopes]
    remove += [lbl for lbl in current if lbl in PR_LABELS]
    out: dict[str, Any] = {
        "labels_to_add": [INVALID],
        "labels_to_remove": remove,
        "security_issue_stays": True,
    }
    if data.get("number") and data.get("tracker"):
        parts = [
            f"gh issue edit {int(data['number'])} --repo {w(str(data['tracker']))} --add-label {dq(INVALID)}"
        ]
        parts += [f"--remove-label {dq(lbl)}" for lbl in remove]
        out["command"] = " ".join(parts)
    return out


def board(data: Mapping[str, Any]) -> dict[str, Any]:
    owner, _, name = str(data["tracker"]).partition("/")
    number = int(data["number"])
    scratch = str(data["scratch"]).rstrip("/")
    read_file = f"{scratch}/invalidate-{number}-board.graphql"
    out: dict[str, Any] = {
        "read": {
            "file": read_file,
            "query": BOARD_READ.replace("{owner}", owner).replace("{name}", name),
            "command": f"gh api graphql -F query=@{w(read_file)} -F n={number}",
            "select": f"the node whose project.number is {int(data['project_number'])}",
        }
    }
    items = data.get("items")
    if items is not None:
        match = [
            i for i in items if int((i.get("project") or {}).get("number", -1)) == int(data["project_number"])
        ]
        if not match:
            out["archive"] = None
            out["note"] = "not on the board: skip the archive and say so in the rollup"
        elif match[0].get("isArchived"):
            out["archive"] = None
            out["note"] = f"item {match[0]['id']} is already archived"
            out["item_id"] = match[0]["id"]
        else:
            item = str(match[0]["id"])
            archive_file = f"{scratch}/invalidate-{number}-archive.graphql"
            out["item_id"] = item
            out["archive"] = {
                "file": archive_file,
                "query": BOARD_ARCHIVE,
                "command": (
                    f"gh api graphql -F query=@{w(archive_file)} -F pid={w(str(data['project_node_id']))} -F iid={w(item)}"
                ),
            }
    return out


def plan(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    number = int(data["number"])
    scratch = str(data["scratch"]).rstrip("/")
    rollup_file = f"{scratch}/invalidate-{number}-rollup.md"
    close_file = f"{scratch}/invalidate-{number}-close.md"
    label_plan = labels({**data, "tracker": tracker, "number": number})
    steps: Sequence[dict[str, Any]] = [
        {
            "step": "6a",
            "write": rollup_file,
            "command": f'{VETTED} rollup-append {number} "Closed as invalid" {w(rollup_file)}',
        },
        {
            "step": "6b",
            "write": close_file,
            "command": f"gh issue comment {number} --repo {w(tracker)} --body-file {w(close_file)}",
        },
        {"step": "6c", "command": label_plan["command"]},
        {"step": "6d", "command": f"gh issue close {number} --repo {w(tracker)} --reason 'not planned'"},
        {"step": "6e", "command": "the board archive from `board` (skip when not on the board)"},
        {
            "step": "6f",
            "command": "create the draft (Step 5d plan) when one is owed",
            "draft": bool(data.get("draft_owed")),
        },
        {
            "step": "6f-amend",
            "command": f'{VETTED} rollup-amend-latest {number} "Closed as invalid" {w(rollup_file)}',
            "when": "6a ran with the `<pending>` draft id",
        },
        {"step": "6g", "command": f"delete {scratch}/invalidate-{number}-*"},
    ]
    return {"tracker": tracker, "number": number, "steps": list(steps), "labels": label_plan}
