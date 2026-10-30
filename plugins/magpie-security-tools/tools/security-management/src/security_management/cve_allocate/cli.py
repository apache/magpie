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
"""`security-management cve-allocate …` — every command reads one JSON file, prints JSON and runs nothing.

Tracker text (the title, field values, the user's reply, a composed draft)
reaches a command only through the `--input` file the agent wrote with its
Write tool. Allocating the CVE, writing the reporter draft and flagging
injection stay the agent's; the allocation itself is the user's.
"""

from __future__ import annotations

import argparse
from typing import Any

from security_management.cli import emit, read_object, refuse
from security_management.cve_allocate import apply, confirm, draft, gate, recipe, render, title

FAMILY = "cve-allocate"

COMMANDS = {
    "selector": "Inputs: the tracker and an optional CVE-ID override (JSON: invocation, tracker, platform)",
    "blockers": "Step 1: the blocker checks (JSON: state, labels, cve_tool_link, scope_labels)",
    "preflight": "Step 0 item 5: the API pre-flight exits as the Step 3 path",
    "title": "Step 2: the CVE-ready title and the over-strip warning (JSON: title, project_names)",
    "recipe": "Step 3: the API proposal, the self-service recipe or the relay message",
    "allocate-result": "Step 3: what a vulnogram-api-allocate exit means next",
    "cve": "Step 3: the one CVE ID in the user's paste-back (JSON: text)",
    "draft-plan": "Step 4 item 5: whether the reporter gets a draft, to whom and how",
    "check-draft": "Step 4 item 5: grep a composed draft for the CVE-tool URL and other leaks",
    "proposal": "Step 4: the numbered items 1-5",
    "render-rollup": "Step 4 item 3: the rollup entry and its label",
    "parse-reply": "Step 5: the confirmation reply (JSON: reply, items)",
    "apply-plan": "Step 5: the confirmed items as ordered commands",
    "render-recap": "Step 7: the recap",
}


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="security-cve-allocate: blockers, title, recipe, proposal, rollup, recap"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        commands.add_parser(name, help=help_text).add_argument(
            "--input", required=True, help="JSON file written with the Write tool"
        )


def dispatch(args: argparse.Namespace) -> int:
    data = read_object(args.input)
    handlers = {
        "selector": gate.selector,
        "blockers": gate.blockers,
        "preflight": gate.preflight,
        "title": title.normalize,
        "recipe": recipe.render,
        "allocate-result": gate.allocate_result,
        "cve": gate.cve,
        "draft-plan": draft.plan,
        "check-draft": draft.check,
        "proposal": render.proposal,
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
