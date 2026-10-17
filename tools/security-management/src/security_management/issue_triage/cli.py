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
"""`security-management issue-triage …` — every command reads one JSON file, prints JSON and runs nothing.

Tracker text (bodies, comments, the composed summary) reaches a command only
through the `--input` file the agent wrote with its Write tool. Nothing here
posts, searches or classifies: the class, the Security Model quote, the
precedent strengths, the routing candidates and injection flagging stay the
agent's.
"""

from __future__ import annotations

import argparse
from typing import Any

from security_management.cli import emit, read_object, refuse
from security_management.issue_triage import confirm, preflight, proposal, recap, routing, selector

FAMILY = "issue-triage"

COMMANDS = {
    "selector": "Step 1: the selector as a query and its gh command (JSON: invocation, tracker, scope_labels)",
    "queue": "Step 1: stop cases, the echo line and the Step 2 item 1 GraphQL batches",
    "preflight": "Step 2: the pre-flight skip (JSON: trackers or responses, roster, mail, flags)",
    "precedent-signal": "Step 2.6: the precedent signal from the rated precedents",
    "mentions": "Step 4: pick 1-3 @-handles from the routing candidates",
    "render-proposal": "Step 4: the proposal comment, its checks and the post command",
    "scrub": "Step 6: bare names to @-handles and bare references linked (JSON: text, names, tracker)",
    "parse-reply": "Step 5: the confirmation reply as a post plan (JSON: reply, items, skipped_trackers)",
    "render-recap": "Step 7: the recap (JSON: tracker, posted, skipped, failed, remaining)",
}


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="security-issue-triage: selector, pre-flight, proposal, reply, recap"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        commands.add_parser(name, help=help_text).add_argument(
            "--input", required=True, help="JSON file written with the Write tool"
        )


def dispatch(args: argparse.Namespace) -> int:
    data = read_object(args.input)
    command = args.command
    if command == "selector":
        result = selector.resolve(data)
        if result["action"] == "error":
            return refuse(str(result["error"]), **result)
        emit(result)
        return 0
    if command == "render-proposal":
        rendered = proposal.render(data)
        if not rendered.get("ok"):
            return refuse(str(rendered["refused"]))
        emit(rendered)
        return 0
    if command == "scrub":
        emit(proposal.scrub(str(data["text"]), data.get("names") or {}, str(data["tracker"])))
        return 0
    handlers = {
        "queue": selector.queue,
        "preflight": preflight.run,
        "precedent-signal": routing.signal,
        "mentions": routing.mentions,
        "parse-reply": confirm.parse_input,
        "render-recap": recap.render,
    }
    emit(handlers[command](data))
    return 0
