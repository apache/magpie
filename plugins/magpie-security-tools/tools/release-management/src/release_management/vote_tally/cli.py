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
"""`release-management vote-tally …` — every command prints JSON and sends nothing.

`--preflight` is what `release-config preflight --skill vote-tally …` printed and
`--load` what `release-config load --skill vote-tally <version>-rcN` printed,
each saved to a file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release_management.cli import emit
from release_management.vote_tally import render, tally

FAMILY = "vote-tally"


def _json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY,
        help="release-vote-tally: Step 0 verdict, archive URL, pre-classification, tally, [RESULT] draft",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    verdict = commands.add_parser(
        "verdict", help="Step 0: the preflight blockers plus the planning-issue checks"
    )
    verdict.add_argument("--preflight", required=True, help="file holding `release-config preflight` output")
    verdict.add_argument("--planning-issue", help="the planning issue URL, when one was found")
    verdict.add_argument("--comments", help="file holding the planning issue's comments")
    verdict.add_argument(
        "--ambiguous-note-acknowledged",
        action="store_true",
        help="the RM answered the previous run's AMBIGUOUS note (re-run from scratch or resolve inline)",
    )

    archive = commands.add_parser("archive-url", help="Step 1: render mail_archive_url_template")
    archive.add_argument("--load", required=True)

    pre = commands.add_parser("preclassify", help="Step 1: the parsed value of every bare vote line")
    pre.add_argument("--replies", required=True, help="JSON list of {from, date, raw_vote_line}")

    count = commands.add_parser("tally", help="Step 2: binding resolution, one person one vote, pass rule")
    source = count.add_mutually_exclusive_group(required=True)
    source.add_argument("--votes", help="JSON file: list of classified votes")
    source.add_argument(
        "--pr-reviews",
        help="pr-approval: file holding `gh pr list --json number,reviews`; each reviewer's latest review is their vote",
    )
    count.add_argument(
        "--login-map", help="with --pr-reviews: JSON file mapping GitHub login to roster Primary email"
    )
    count.add_argument("--roster", required=True, help="approver roster markdown file")
    count.add_argument(
        "--overrides",
        default="{}",
        help="JSON object of pass-rule overrides (min_binding_plus1, max_binding_minus1)",
    )
    count.add_argument("--force-close", action="store_true")
    count.add_argument("--mechanism", default="dev-list-vote")
    count.add_argument("--min-approvals", type=int, help="pr-approval: approval_pr_min_approvals")

    result = commands.add_parser("render", help="Step 3: the [RESULT] [VOTE] subject and body")
    result.add_argument("--load", required=True)
    result.add_argument("--tally", required=True, help="file holding what `vote-tally tally` printed")
    result.add_argument("--product-name", help="the project's display name (project.md)")
    result.add_argument(
        "--result", choices=["PASSED", "FAILED"], help="non-list mechanisms: the rule's outcome"
    )
    result.add_argument("--rule", help="non-list mechanisms: the rule applied")
    result.add_argument("--rm-name", default="<RM name>")


def _tally(args: argparse.Namespace) -> int:
    try:
        reviewers = None
        if args.pr_reviews:
            login_map = _json(args.login_map) if args.login_map else {}
            if not isinstance(login_map, dict):
                raise tally.InputError("--login-map must hold a JSON object of login -> Primary email")
            votes, reviewers = tally.pr_review_votes(_json(args.pr_reviews), login_map)
        else:
            if args.login_map:
                raise tally.InputError("--login-map only applies with --pr-reviews")
            votes = _json(args.votes)
            if not isinstance(votes, list):
                raise tally.InputError("--votes must hold a JSON list")
        overrides = json.loads(args.overrides)
        if not isinstance(overrides, dict):
            raise tally.InputError("--overrides must be a JSON object")
        roster = tally.parse_roster(Path(args.roster).read_text(encoding="utf-8"))
        if not roster:
            raise tally.InputError("roster has no rows with an Apache ID / Primary email header")
        out = tally.tally(votes, roster, overrides, args.force_close, args.mechanism, args.min_approvals)
        if reviewers is not None:
            out["pr_reviewers"] = reviewers
    except (tally.InputError, OSError, json.JSONDecodeError) as exc:
        emit({"error": str(exc)})
        return 2
    emit(out)
    return 0


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "tally":
        return _tally(args)
    try:
        if args.command == "verdict":
            comments = Path(args.comments).read_text(encoding="utf-8") if args.comments else None
            out = render.verdict(
                _json(args.preflight),
                planning_issue=args.planning_issue,
                comments=comments,
                ambiguous_note_acknowledged=args.ambiguous_note_acknowledged,
            )
        elif args.command == "archive-url":
            out = render.archive_url(_json(args.load))
        elif args.command == "preclassify":
            replies = _json(args.replies)
            if not isinstance(replies, list):
                raise render.RenderError("--replies must hold a JSON list")
            out = render.preclassify(replies)
        else:
            out = render.result_draft(
                _json(args.load),
                _json(args.tally),
                product_name=args.product_name,
                result=args.result,
                rule=args.rule,
                rm_name=args.rm_name,
            )
    except render.RenderError as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    emit(out)
    return 0
