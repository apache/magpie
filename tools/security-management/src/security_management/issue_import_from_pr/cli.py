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
"""`security-management issue-import-from-pr …` — reads files, prints JSON, runs nothing.

The PR title, body, author and file paths are attacker-controlled: they reach
a command only in a file the agent wrote with its Write tool. The PR number
travels in argv only as an integer.
"""

from __future__ import annotations

import argparse
from typing import Any

from security_management.cli import emit, read_json, read_object, refuse
from security_management.issue_import_from_pr import render, scope

FAMILY = "issue-import-from-pr"


def _positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("PR number must be positive")
    return number


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="security-issue-import-from-pr: scope, body, labels, rollup, recap")
    commands = parser.add_subparsers(dest="command", required=True)

    ref = commands.add_parser("parse-ref", help="Step 0: the PR number from one of the four input forms")
    ref.add_argument("--ref", required=True, help="what the user typed: N, owner/repo#N or the PR URL")
    ref.add_argument("--upstream", required=True, help="<upstream>; any other repository is refused")

    sc = commands.add_parser("scope", help="Step 2: scope from the changed files, mixed-scope guard")
    sc.add_argument(
        "--files", required=True, help="`gh pr view --json files` output, or a JSON list of paths"
    )
    sc.add_argument("--scope-config", required=True, help="JSON: project.md scope_detection block")

    for name, help_text in (
        ("milestone-check", "Step 3: does the chosen milestone exist (exact match)"),
        ("title", "Step 5a: strip conventional-commit prefixes, skip-ci markers, trailing (#N)"),
        ("render-body", "Step 5b: the tracker body"),
        ("labels", "Step 5c: scope, PR-state and security-marker labels"),
        ("render-rollup", "Step 5e: the first rollup entry"),
        ("render-recap", "Step 8: the recap and hand-off"),
    ):
        p = commands.add_parser(name, help=help_text)
        p.add_argument("--input", required=True, help="JSON; see the README")

    dup = commands.add_parser("dup-query", help="Step 4: the duplicate-tracker search and its verdict")
    dup.add_argument("--pr", required=True, type=_positive, help="the integer pr.number from Step 1")
    dup.add_argument("--tracker", required=True, help="<tracker>")
    dup.add_argument("--hits", help="the search's JSON output; omit to print the command only")
    dup.add_argument("--platform", default="github", help="tracker.platform: github, jira or local-files")


def dispatch(args: argparse.Namespace) -> int:
    command = args.command
    if command == "parse-ref":
        result = scope.parse_ref(args.ref, args.upstream)
        if not result["ok"]:
            return refuse(result["refused"])
        emit(result)
        return 0
    if command == "scope":
        emit(scope.detect(read_json(args.files), read_object(args.scope_config)))
        return 0
    if command == "dup-query":
        emit(
            render.dup_query(
                args.pr, args.tracker, read_json(args.hits) if args.hits else None, args.platform
            )
        )
        return 0
    data = read_object(args.input)
    if command == "milestone-check":
        emit(render.milestone_check(str(data["proposed"]), data.get("titles") or []))
    elif command == "title":
        emit(render.title(str(data["title"])))
    elif command == "render-body":
        rendered = render.render_body(data)
        if not rendered["ok"]:
            return refuse(rendered["refused"], malformed_indicator=rendered["malformed_indicator"])
        emit(rendered)
    elif command == "labels":
        emit(render.labels(data.get("scope") or None, str(data["state"]), data.get("labels")))
    elif command == "render-rollup":
        result = render.rollup(data)
        if not result["ok"]:
            return refuse(result["refused"])
        emit(result)
    else:
        emit(render.recap(data))
    return 0
