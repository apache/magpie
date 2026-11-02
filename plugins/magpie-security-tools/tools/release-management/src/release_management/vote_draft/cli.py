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
"""`release-management vote-draft …` — every command prints JSON and sends nothing.

`--preflight` is what `release-config preflight --skill vote-draft …` printed and
`--load` what `release-config load --skill vote-draft <version>-rcN` printed,
each saved to a file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release_management.cli import emit
from release_management.vote_draft import render

FAMILY = "vote-draft"


def _read(path: str | None) -> str | None:
    return Path(path).read_text(encoding="utf-8") if path else None


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="release-vote-draft: the Step 0 verdict, the [VOTE] draft and the planning-issue comment"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    verdict = commands.add_parser("verdict", help="Step 0: the preflight blockers plus the verify-rc gate")
    verdict.add_argument("--preflight", required=True, help="file holding `release-config preflight` output")
    verdict.add_argument("--planning-issue", help="the planning issue URL, when one was found")
    verdict.add_argument(
        "--verify-rc-verdict",
        required=True,
        choices=list(render.VERDICTS),
        help="the overall verdict of the latest release-verify-rc comment, or none",
    )
    verdict.add_argument("--verify-rc-for", help="the <version>-rcN that comment reports on")

    render_p = commands.add_parser("render", help="render one step's draft and JSON contract")
    render_p.add_argument("--step", required=True, choices=["2", "3"])
    render_p.add_argument(
        "--load", required=True, help="file holding `release-config load --skill vote-draft …`"
    )
    render_p.add_argument("--product-name", required=True, help="the project's display name (project.md)")
    render_p.add_argument("--expedited", help="the neutral --expedited reason")
    render_p.add_argument("--staging-url", help="Step 2: the staging URL from the planning issue")
    render_p.add_argument("--tag-url", help="Step 2: the RC tag URL from the planning issue")
    render_p.add_argument("--changelog-url", help="Step 2: the changelog URL from the planning issue")
    render_p.add_argument(
        "--svn-revision", help="Step 2: `svn info --show-item last-changed-revision` (svnpubsub)"
    )
    render_p.add_argument("--rc-comment", help="Step 2: file holding release-rc-cut's planning-issue comment")
    for name in ("repository", "commit", "swhid", "epoch", "sha512"):
        render_p.add_argument(
            f"--{name}", help=f"Step 2: reproducibility record {name} (overrides --rc-comment)"
        )
    render_p.add_argument("--canned-body", help="Step 2: file holding the canned [VOTE] template block")
    render_p.add_argument("--skip-verify-check", help="Step 2: the --skip-verify-check reason")
    render_p.add_argument("--atr-candidate-url", help="Step 2 (atr): the candidate's ATR page")
    render_p.add_argument("--atr-revision", help="Step 2 (atr): a specific uploaded revision")
    render_p.add_argument("--planning-issue", help="Step 2 (ci-automated): the planning issue URL")
    render_p.add_argument("--project", help="Step 2 (atr): the <project> slug")
    render_p.add_argument("--rm-name", default="<RM name>")
    render_p.add_argument("--sent-at", help="Step 3: when the RM sent the [VOTE], ISO-8601 UTC")
    render_p.add_argument("--subject", help="Step 3: the final subject, when the RM edited it")


def _record(args: argparse.Namespace) -> render.Record:
    text = _read(args.rc_comment)
    record = render.parse_rc_comment(text) if text else render.Record()
    for name in ("repository", "commit", "swhid", "epoch", "sha512"):
        if getattr(args, name):
            setattr(record, name, getattr(args, name))
    return record


def dispatch(args: argparse.Namespace) -> int:
    try:
        if args.command == "verdict":
            preflight = json.loads(Path(args.preflight).read_text(encoding="utf-8"))
            emit(
                render.verdict(
                    preflight,
                    planning_issue=args.planning_issue,
                    verify_rc_verdict=args.verify_rc_verdict,
                    verify_rc_for=args.verify_rc_for,
                )
            )
            return 0
        loaded = json.loads(Path(args.load).read_text(encoding="utf-8"))
        draft = render.VoteDraft.from_load(loaded, product_name=args.product_name)
        if args.step == "2":
            out = render.step2(
                draft,
                tag_url=args.tag_url,
                changelog_url=args.changelog_url,
                staging_url=args.staging_url,
                svn_revision=args.svn_revision,
                record=_record(args),
                canned_body=_read(args.canned_body),
                expedited=args.expedited,
                skip_verify=args.skip_verify_check,
                atr_candidate_url=args.atr_candidate_url,
                atr_revision=args.atr_revision,
                planning_issue=args.planning_issue,
                project=args.project,
                rm_name=args.rm_name,
            )
        else:
            if not args.sent_at:
                raise render.RenderError("Step 3 needs --sent-at: the time the RM sent the [VOTE]")
            out = render.step3(draft, sent_at=args.sent_at, subject=args.subject, expedited=args.expedited)
    except render.RenderError as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    emit({"ok": True, "step": args.step} | out)
    return 0
