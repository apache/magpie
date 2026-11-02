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
"""`release-management archive-sweep …` — every command prints JSON and runs nothing.

`--preflight` is what `release-config preflight --skill archive-sweep` printed and
`--load` what `release-config load --skill archive-sweep` printed, each saved to a file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from release_management.archive_sweep import render, retention
from release_management.cli import emit

FAMILY = "archive-sweep"


def _json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="release-archive-sweep: listing command, trains.json, retention rule, archive commands"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    ver = commands.add_parser("verdict", help="Step 0: the preflight blockers as the step's JSON")
    ver.add_argument("--preflight", required=True, help="file holding `release-config preflight` output")

    lst = commands.add_parser("listing", help="Step 1: the backend's read-only listing command")
    lst.add_argument("--load", required=True, help="file holding `release-config load --skill archive-sweep`")
    lst.add_argument("--upstream", help="<upstream> owner/repo, from project.md (github-releases)")

    tr = commands.add_parser("trains", help="Step 1: trains.json from release-trains.md's release lines")
    tr.add_argument("--load", required=True)
    tr.add_argument("--keep", type=int, help="versions each train keeps, when the rule keeps more than one")

    ret = commands.add_parser("retention", help="Step 1: apply the retention rule to the listing")
    ret.add_argument("--listing", required=True, help="file: one dist entry per line ('-' for stdin)")
    ret.add_argument(
        "--trains", required=True, help="JSON file: the trains list, or what `archive-sweep trains` printed"
    )

    ren = commands.add_parser("render", help="Step 2: the archive command set, oldest first")
    ren.add_argument("--load", required=True)
    ren.add_argument("--retention", required=True, help="file holding what `archive-sweep retention` printed")
    ren.add_argument("--upstream", help="<upstream> owner/repo, from project.md (github-releases)")
    ren.add_argument("--project", help="<project> slug, when project_dist_name is unset")
    ren.add_argument("--command-template", help="self-hosted: the adopter-supplied archival command")


def _retention(args: argparse.Namespace) -> int:
    try:
        text = sys.stdin.read() if args.listing == "-" else Path(args.listing).read_text(encoding="utf-8")
        trains = _json(args.trains)
        undecided = isinstance(trains, dict) and trains.get("keep_decided") is False
        prefix = suffix = ""
        if isinstance(trains, dict):
            prefix, suffix = str(trains.get("entry_prefix") or ""), str(trains.get("entry_suffix") or "")
            trains = trains.get("trains")
        if not isinstance(trains, list) or not trains:
            raise retention.InputError("--trains must hold a non-empty JSON list")
        if undecided and not all(isinstance(t, dict) and "keep" in t for t in trains):
            # A free-text archive_retention_rule: defaulting to keep 1 would archive what the rule keeps.
            raise retention.InputError(
                "--trains says keep_decided is false (archive_retention_rule is free text): re-run "
                "`archive-sweep trains` with --keep N, or give every train an explicit 'keep'"
            )
        versions, other = retention.parse_listing(text, prefix, suffix)
        out = retention.sweep(versions, trains)
        out["non_version_entries"] = other
        out["entry_prefix"], out["entry_suffix"] = prefix, suffix
    except (retention.InputError, OSError, json.JSONDecodeError) as exc:
        emit({"error": str(exc)})
        return 2
    emit(out)
    return 0


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "retention":
        return _retention(args)
    if args.command == "verdict":
        emit(render.verdict(_json(args.preflight)))
        return 0
    try:
        sweep = render.Sweep.from_load(
            _json(args.load), upstream=getattr(args, "upstream", None), project=getattr(args, "project", None)
        )
        if args.command == "listing":
            out = render.listing(sweep)
        elif args.command == "trains":
            out = render.trains(sweep, keep=args.keep)
        else:
            out = render.step2(sweep, _json(args.retention), command_template=args.command_template)
    except render.RenderError as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    emit(out)
    return 0
