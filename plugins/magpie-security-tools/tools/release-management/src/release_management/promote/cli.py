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
"""`release-management promote …` — every command prints JSON and runs nothing.

`--preflight` is the JSON `release-config preflight --skill promote …` printed;
`--load` is what `release-config load --skill promote …` printed. Both are
saved to files by the agent; the planning-issue facts arrive as flags.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release_management.cli import emit
from release_management.promote import render

FAMILY = "promote"


def _json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="release-promote: the Step 0 verdict and the promotion command set")
    commands = parser.add_subparsers(dest="command", required=True)

    v = commands.add_parser("verdict", help="Step 0: fold the preflight output and the planning-issue facts")
    v.add_argument(
        "--preflight", required=True, help="file holding `release-config preflight --skill promote …`"
    )
    v.add_argument("--vote-passed", action="store_true", help="the planning issue carries `vote-passed`")
    v.add_argument("--no-planning-issue", action="store_true", help="no planning issue was found")
    v.add_argument(
        "--target",
        required=True,
        choices=render.TARGET_STATES,
        help="what the target listing / `gh release view` found; a check that did not run has no value to pass",
    )
    v.add_argument(
        "--attestation",
        action="store_true",
        help="the planning issue records the trusted-hardware attestation for this RC",
    )
    v.add_argument(
        "--planning-issue", default="<planning-issue>", help="planning-issue URL, for the blocker text"
    )
    v.add_argument(
        "--upstream", required=True, help="<upstream> owner/repo, from project.md; render must match it"
    )
    v.add_argument("--project", required=True, help="<project> slug, from project.md; render must match it")

    r = commands.add_parser("render", help="Step 2: the backend-shaped promotion command set")
    r.add_argument("--load", required=True, help="file holding `release-config load --skill promote …`")
    r.add_argument(
        "--upstream", required=True, help="<upstream> owner/repo, from project.md (as passed to verdict)"
    )
    r.add_argument("--project", required=True, help="<project> slug, from project.md (as passed to verdict)")
    r.add_argument("--product-name", help="the display name, e.g. 'Apache Airflow'")
    r.add_argument(
        "--verdict",
        required=True,
        help="file holding `promote verdict`'s output; only proceed / handoff-non-pmc render",
    )
    r.add_argument(
        "--handoff",
        action="store_true",
        default=None,
        help="compatibility: must agree with --verdict, which decides the hand-off",
    )
    r.add_argument("--rm", help="the RM's GitHub handle or apache_id, for the hand-off note")
    r.add_argument("--roster-path", help="preflight values.roster_path, for the hand-off note")
    r.add_argument("--apache-id", help="the RM's apache_id (svn --username)")
    r.add_argument("--result-vote-url", help="the [RESULT] [VOTE] archive URL")
    r.add_argument("--rc-commit-sha", help="`git rev-list -n1 <version>-rc<N>`")
    r.add_argument("--draft-tag", help="github-releases: the tag the draft release carries")
    r.add_argument(
        "--draft-tag-confirmed", action="store_true", help="the RM confirmed a --draft-tag that differs"
    )


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "verdict":
        emit(
            render.verdict(
                _json(args.preflight),
                vote_passed=args.vote_passed,
                target=args.target,
                attestation=args.attestation,
                planning_issue_found=not args.no_planning_issue,
                planning_issue=args.planning_issue,
                upstream=args.upstream,
                project=args.project,
            )
        )
        return 0
    try:
        p = render.Promote.from_load(
            _json(args.load), upstream=args.upstream, project=args.project, product_name=args.product_name
        )
        out = render.step2(
            p,
            handoff=render.handoff_from_verdict(p, _json(args.verdict), handoff=args.handoff),
            rm=args.rm,
            roster_path=args.roster_path,
            apache_id=args.apache_id,
            result_vote_url=args.result_vote_url,
            rc_commit_sha=args.rc_commit_sha,
            draft_tag=args.draft_tag,
            draft_tag_confirmed=args.draft_tag_confirmed,
        )
    except render.RenderError as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    emit({"ok": True} | out)
    return 0
