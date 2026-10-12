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
"""`release-management rc-cut …` — every command prints JSON and runs nothing.

`--load` is the JSON `release-config load --skill rc-cut <version> <rcN>`
printed, saved to a file; the renderers read every value from it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release_management.cli import emit
from release_management.rc_cut import render

FAMILY = "rc-cut"


def _cut(args: argparse.Namespace) -> render.RcCut:
    loaded = json.loads(Path(args.load).read_text(encoding="utf-8"))
    return render.RcCut.from_load(loaded, upstream=args.upstream, project=args.project)


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="release-rc-cut: render the RC command blocks and the planning-issue comment"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    tags = commands.add_parser("tag-exists", help="does refs/tags/<version>-<rcN> exist (exact match)")
    tags.add_argument(
        "--refs", required=True, help="file holding what `vetted-op-read … tags <version>-<rcN>` printed"
    )
    tags.add_argument("tag", help="<version>-<rcN>")

    render_p = commands.add_parser("render", help="render one step's blocks and JSON contract")
    render_p.add_argument("--step", required=True, choices=["2", "2b", "2c", "3", "4"])
    render_p.add_argument(
        "--load", required=True, help="file holding `release-config load --skill rc-cut …` output"
    )
    render_p.add_argument("--upstream", help="<upstream> owner/repo, from project.md")
    render_p.add_argument("--project", help="<project> slug, from project.md")
    render_p.add_argument("--asf-id", default="<asf-id>", help="the RM's ASF id (svnpubsub staging)")
    render_p.add_argument(
        "--skip-repro-check", action="store_true", help="Step 2b: the RM passed --skip-repro-check"
    )
    render_p.add_argument(
        "--epoch", default="<SOURCE_DATE_EPOCH>", help="Step 2b: the epoch repro-archive build printed"
    )
    render_p.add_argument("--record", help="Step 4: file holding what `repro-archive build` printed")
    render_p.add_argument(
        "--self-check", default="skipped", help="Step 4: the Step 2b outcome the RM reported"
    )
    render_p.add_argument("--run-url", help="Step 4 (ci-automated): the workflow run URL")
    render_p.add_argument(
        "--allow-unreviewed-archive",
        nargs="?",
        const="",
        default=None,
        help="Step 4: the override was used (optional reason)",
    )


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "tag-exists":
        exists = render.tag_exists(Path(args.refs).read_text(encoding="utf-8"), args.tag)
        emit({"tag": args.tag, "rc_tag_exists": exists})
        return 0
    try:
        cut = _cut(args)
        if args.step == "2":
            out = render.step2(cut)
        elif args.step == "2b":
            out = render.step2b(cut, skip=args.skip_repro_check, epoch=args.epoch)
        elif args.step == "2c":
            out = render.step2c(cut)
        elif args.step == "3":
            out = render.step3(cut, asf_id=args.asf_id)
        else:
            record = (
                render.parse_record(Path(args.record).read_text(encoding="utf-8")) if args.record else None
            )
            out = render.step4(
                cut,
                record=record,
                self_check=args.self_check,
                run_url=args.run_url,
                allow_unreviewed_archive=args.allow_unreviewed_archive,
            )
    except render.RenderError as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    emit({"ok": True, "step": args.step} | out)
    return 0
