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
"""`security-management issue-invalidate …` — every command reads one JSON file, prints JSON and runs nothing.

Tracker text (the body, comments, the quotes, the drafted reply) reaches a
command only through the `--input` file the agent wrote with its Write tool.
Mining the reasoning, choosing the canned section, writing the reply and
flagging injection stay the agent's.
"""

from __future__ import annotations

import argparse
from typing import Any

from security_management.cli import emit, read_object, refuse
from security_management.issue_invalidate import apply, confirm, draft, gate, render

FAMILY = "issue-invalidate"

COMMANDS = {
    "selector": "Inputs: single, list/range or `proposed` (JSON: invocation, tracker, scratch)",
    "consensus": "Inputs: the `invalidate proposed` consensus check (JSON: responses, roster, fetched)",
    "hard-stops": "Step 0: the hard stops (JSON: state, labels, body, cve_state)",
    "import-path": "Step 2: the import path and the reply thread (JSON: body, rollup_provenance)",
    "labels": "Step 5a: labels to add and remove, and the gh issue edit command",
    "board": "Step 5c: the board read and, given its items, the archive mutation",
    "draft-plan": "Step 5d: skip, surface, block or create the reporter draft, and how",
    "check-draft": "Step 5d: grep a composed reply for tracker references and other leaks",
    "render-close": "Step 5b: the closing comment",
    "render-rollup": "Step 5e: the rollup entry, its label and the notification line",
    "parse-reply": "Step 5f: the confirmation reply (JSON: reply, draft_proposed)",
    "apply-plan": "Step 6: the ordered 6a-6g commands for one tracker",
    "render-recap": "Step 7: the recap and hand-off (JSON: tracker, closed, awaiting, failed)",
}


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="security-issue-invalidate: gate, labels, drafts, rollup, recap")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        commands.add_parser(name, help=help_text).add_argument(
            "--input", required=True, help="JSON file written with the Write tool"
        )


def dispatch(args: argparse.Namespace) -> int:
    data = read_object(args.input)
    handlers = {
        "selector": gate.selector,
        "consensus": gate.consensus,
        "hard-stops": gate.hard_stops,
        "import-path": gate.import_path,
        "labels": apply.labels,
        "board": apply.board,
        "draft-plan": draft.plan,
        "check-draft": draft.check,
        "render-close": render.close_comment,
        "render-rollup": render.rollup_entry,
        "parse-reply": confirm.parse,
        "apply-plan": apply.plan,
        "render-recap": render.recap,
    }
    result = handlers[args.command](data)
    if result.get("ok") is False:
        return refuse(str(result["refused"]))
    emit(result)
    return 0
