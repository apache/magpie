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
"""`security-management issue-deduplicate …` — every command reads one JSON file, prints JSON and runs nothing.

Tracker text (both bodies, credits, threads, the user's reply) reaches a
command only through the `--input` file the agent wrote with its Write tool.
Judging that two reports share a root cause, writing the headline and the
analysis, and picking the kept side stay the agent's and the user's.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Any

from security_management.cli import emit, read_object, refuse
from security_management.issue_deduplicate import apply, gate, merge, render
from security_management.shared import numbered

FAMILY = "issue-deduplicate"

COMMANDS = {
    "selector": "Inputs: the kept and the dropped tracker (JSON: invocation, tracker, platform)",
    "classify": "Step 1: open, one shared scope label, not duplicate, the CVE rules",
    "fields": "Step 2: both trackers' template fields and the CWE / severity conflicts",
    "merge-body": "Step 3: the kept body with the dropped report merged in",
    "render-rollup-kept": "Step 4: the kept tracker's rollup entry",
    "render-rollup-dropped": "Step 4: the dropped tracker's rollup entry",
    "proposal": "Step 5: the numbered items 1-7",
    "parse-reply": "Step 5: the confirmation reply (JSON: reply, items)",
    "apply-plan": "Step 5: the confirmed items as ordered commands",
    "render-recap": "Step 6: the recap",
}


def _parse(data: Mapping[str, Any]) -> dict[str, Any]:
    return numbered.parse(data.get("reply"), data.get("items") or [], render.CANONICAL)


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="security-issue-deduplicate: checks, merged body, rollups, recap")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        commands.add_parser(name, help=help_text).add_argument(
            "--input", required=True, help="JSON file written with the Write tool"
        )


def dispatch(args: argparse.Namespace) -> int:
    data = read_object(args.input)
    handlers = {
        "selector": gate.selector,
        "classify": gate.classify,
        "fields": gate.fields,
        "merge-body": merge.merge_body,
        "render-rollup-kept": render.rollup_kept,
        "render-rollup-dropped": render.rollup_dropped,
        "proposal": render.proposal,
        "parse-reply": _parse,
        "apply-plan": apply.plan,
        "render-recap": render.recap,
    }
    result = handlers[args.command](data)
    if result.get("ok") is False:
        return refuse(str(result["refused"]))
    emit(result)
    return 0
