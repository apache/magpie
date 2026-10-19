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
"""`security-management issue-fix …` — every command reads one JSON file, prints JSON and runs nothing.

Public-bound text (branch, title, body, commit message, newsfragment) and
tracker text reach a command only through the `--input` file the agent
wrote with its Write tool. Judging fixability, finding existing PRs,
planning files and tests, writing the code and the PR body stay the agent's.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Any

from security_management.cli import emit, read_object, refuse
from security_management.issue_fix import gate, render, scrub, svn
from security_management.shared import numbered

FAMILY = "issue-fix"
PLAN_ITEMS = (1, 2, 3, 4, 5, 6, 7)

COMMANDS = {
    "flow": "Source control: the fix flow from magpie-vcs fix-flow's exit and JSON",
    "scrub": "5a / 5c / 5f / 7 / 9: the forbidden-term check on every public surface",
    "backport": "5e: the backport labels for the milestone (JSON: milestone, main_version, extra_lines)",
    "parse-reply": "Step 6: the plan confirmation (JSON: reply, items)",
    "review-plan": "Step 7: whether the adversarial reviewers run, and the command",
    "svn-share": "Step 8 (Subversion): the private surfaces the patch goes to",
    "svn-gate": "Step 9 (Subversion): the publication gate and the commit proposal",
    "render-recap": "Step 11: the recap",
}


def _parse(data: Mapping[str, Any]) -> dict[str, Any]:
    return numbered.parse(data.get("reply"), data.get("items") or PLAN_ITEMS, PLAN_ITEMS)


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="security-issue-fix: flow, scrub, backport, review, Subversion gate, recap"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        commands.add_parser(name, help=help_text).add_argument(
            "--input", required=True, help="JSON file written with the Write tool"
        )


def dispatch(args: argparse.Namespace) -> int:
    data = read_object(args.input)
    handlers = {
        "flow": gate.flow,
        "scrub": scrub.check,
        "backport": gate.backport,
        "parse-reply": _parse,
        "review-plan": gate.review_plan,
        "svn-share": svn.share,
        "svn-gate": svn.gate,
        "render-recap": render.recap,
    }
    result = handlers[args.command](data)
    if result.get("ok") is False:
        return refuse(str(result["refused"]))
    emit(result)
    return 0
