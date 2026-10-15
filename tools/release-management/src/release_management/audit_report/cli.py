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
"""`release-management audit-report …` — every command prints JSON and opens nothing.

`--preflight` is what `release-config preflight --skill audit-report <version>`
printed and `--load` what `release-config load --skill audit-report <version>`
printed, each saved to a file. `--step1` is the Step 1 JSON the RM confirmed,
saved to a file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release_management.audit_report import record, render
from release_management.cli import emit

FAMILY = "audit-report"


def _json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _object(path: str, what: str) -> dict[str, Any]:
    data = _json(path)
    if not isinstance(data, dict):
        raise render.RenderError(f"{what} must hold a JSON object")
    return data


def _schema(path: str | None) -> list[str]:
    source = Path(path) if path else record.DEFAULT_SCHEMA
    return record.required_fields(source.read_text(encoding="utf-8"))


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY,
        help="release-audit-report: Step 0 verdict, Step 1 gather and check, Step 2 record, Step 3 PR proposal",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    schema_help = "audit-record-schema.md (the skill's own; default: the framework copy)"

    verdict = commands.add_parser(
        "verdict", help="Step 0: the preflight blockers plus the planning-issue check"
    )
    verdict.add_argument("--preflight", required=True)
    verdict.add_argument(
        "--planning-issue", help="the planning issue found or passed: a URL or <org>/<repo>#<n>"
    )
    verdict.add_argument("--upstream", help="<upstream> owner/repo, from project.md")
    verdict.add_argument("--searched", help="the search term used when no planning issue was found")

    gather = commands.add_parser(
        "gather", help="Step 1: mail-archive searches, promote-revision recipe, fields"
    )
    gather.add_argument("--load", required=True)
    gather.add_argument(
        "--rc", help="the RC label from the planning issue (e.g. rc1), to render the subjects"
    )
    gather.add_argument("--schema", help=schema_help)

    voters = commands.add_parser("voters", help="Step 1: [RESULT] binding voters → roster handles")
    voters.add_argument("--voters", required=True, help="JSON list of From: addresses or Apache IDs")
    voters.add_argument("--roster", required=True, help="the approver roster markdown file")

    check = commands.add_parser("check", help="Step 1: fields_missing / fields_redacted and refused values")
    check.add_argument("--step1", required=True)
    check.add_argument("--schema", help=schema_help)
    check.add_argument(
        "--not-ponymail",
        action="store_true",
        help="the mail archive is not PonyMail: skip the permalink shape",
    )

    rec = commands.add_parser("record", help="Step 2: render and validate the audit record")
    rec.add_argument("--step1", required=True)
    rec.add_argument("--schema", help=schema_help)

    pr = commands.add_parser("pr", help="Step 3: the audit-log PR title, body and target file")
    pr.add_argument("--step1", required=True)
    pr.add_argument("--audit-log-path", required=True, help="Step 0's audit_log_path")
    pr.add_argument("--upstream", help="<upstream> owner/repo, from project.md")
    pr.add_argument(
        "--base",
        help="the PR's base branch: project.md's upstream_default_branch (default: <default-branch>)",
    )
    pr.add_argument("--body-file", default=render.DEFAULT_BODY_FILE)


def dispatch(args: argparse.Namespace) -> int:
    try:
        if args.command == "verdict":
            out = render.verdict(
                _json(args.preflight),
                planning_issue=args.planning_issue,
                upstream=args.upstream,
                searched=args.searched,
            )
        elif args.command == "gather":
            source = Path(args.schema) if args.schema else record.DEFAULT_SCHEMA
            out = render.gather(_json(args.load), rc=args.rc, schema_text=source.read_text(encoding="utf-8"))
        elif args.command == "voters":
            entries = _json(args.voters)
            if not isinstance(entries, list):
                raise render.RenderError("--voters must hold a JSON list")
            out = render.voters(entries, Path(args.roster).read_text(encoding="utf-8"))
        elif args.command == "check":
            out = render.check(
                _object(args.step1, "--step1"), _schema(args.schema), ponymail=not args.not_ponymail
            )
        elif args.command == "record":
            out = record.render(_object(args.step1, "--step1"), _schema(args.schema))
        else:
            out = render.pr(
                _object(args.step1, "--step1"),
                audit_log_path=args.audit_log_path,
                upstream=args.upstream,
                base=args.base,
                body_file=args.body_file,
            )
    except (record.InputError, OSError, json.JSONDecodeError) as exc:
        emit({"error": str(exc)})
        return 2
    except render.RenderError as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    emit(out)
    return 0
