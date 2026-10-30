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
"""`security-management issue-import-from-md …` — reads files, prints JSON, runs nothing.

The findings file and every value parsed from it are attacker-controlled: the
file is read by path, and parsed values travel back to the tool only inside
`--input` files the agent wrote with its Write tool.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from security_management.cli import emit, read_object, refuse
from security_management.issue_import_from_md import parse, render
from security_management.shared import keyword
from security_management.shell import w

FAMILY = "issue-import-from-md"


def _positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="security-issue-import-from-md: parse, body, rollup, proposal, recap"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("parse", help="Steps 0-1: shape check and the findings parser")
    p.add_argument("file", help="the findings markdown file")
    p.add_argument("--upstream", required=True, help="<upstream>: the fallback repository")

    k = commands.add_parser("keyword", help="Step 2: allowlist-clean the duplicate-search keyword")
    k.add_argument("--file", required=True, help="file the Write tool put the raw keyword in")
    k.add_argument("--tracker", help="<tracker>: also print the search command")

    r = commands.add_parser("render-rollup", help="Step 3e: the first rollup entry")
    r.add_argument("--input", required=True, help="JSON: basename, date, finding")
    r.add_argument("--k", required=True, type=_positive, help="this finding's index")
    r.add_argument("--n", required=True, type=_positive, help="findings in the file")

    for name, help_text in (
        ("render-body", "Step 3b: the tracker body"),
        ("render-proposal", "Step 4: the proposal table"),
        ("render-recap", "Step 6: the recap and hand-off"),
    ):
        c = commands.add_parser(name, help=help_text)
        c.add_argument("--input", required=True, help="JSON; see the README")


def dispatch(args: argparse.Namespace) -> int:
    command = args.command
    if command == "parse":
        result = parse.parse(Path(args.file).read_text(encoding="utf-8"), args.upstream)
        if not result["ok"]:
            return refuse(result["refused"], warnings=result.get("warnings") or [])
        emit(result)
        return 0
    if command == "keyword":
        cleaned = keyword.clean_file(args.file)
        out: dict[str, Any] = {"cleaned": cleaned, "empty": not cleaned}
        if args.tracker and cleaned:
            out["search_command"] = (
                f"gh search issues '{cleaned}' --repo {w(args.tracker)} --json number,title,state,url"
            )
        emit(out)
        return 0
    data = read_object(args.input)
    if command == "render-rollup":
        result = render.rollup(data, args.k, args.n)
    elif command == "render-body":
        result = render.render_body(data)
    elif command == "render-proposal":
        result = {"ok": True, **render.proposal(data)}
    else:
        result = {"ok": True, **render.recap(data)}
    if not result["ok"]:
        return refuse(str(result["refused"]))
    emit(result)
    return 0
