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
"""`release-management announce-draft …` — every command prints JSON and runs nothing.

`--preflight` is the JSON `release-config preflight --skill announce-draft …`
printed; `--load` is what `release-config load --skill announce-draft …`
printed. The planning-issue facts arrive as flags. Nothing is sent or opened.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release_management.announce_draft import render
from release_management.cli import emit

FAMILY = "announce-draft"


def _json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _pair(value: str) -> tuple[str, str]:
    kind, sep, location = value.partition("=")
    if not sep or not kind.strip() or not location.strip():
        raise argparse.ArgumentTypeError(f"expected KIND=LOCATION, got {value!r}")
    return kind.strip(), location.strip()


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="release-announce-draft: the Step 0 verdict, the [ANNOUNCE] draft and the site-bump PR"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    v = commands.add_parser(
        "verdict", help="Step 0: fold the preflight output and the `promoted` label check"
    )
    v.add_argument(
        "--preflight", required=True, help="file holding `release-config preflight --skill announce-draft …`"
    )
    v.add_argument("--promoted", action="store_true", help="the planning issue carries `promoted`")
    v.add_argument("--no-planning-issue", action="store_true", help="no planning issue was found")

    r = commands.add_parser(
        "render", help="render Step 2 (the [ANNOUNCE] draft) or Step 3 (the site-bump PR)"
    )
    r.add_argument("--step", required=True, choices=["2", "3"])
    r.add_argument(
        "--load", required=True, help="file holding `release-config load --skill announce-draft …`"
    )
    r.add_argument("--product-name", help="the display name, e.g. 'Apache Airflow'")
    r.add_argument(
        "--project-name", help="the name after 'The Apache …' (default: --product-name without 'Apache ')"
    )
    r.add_argument("--download-page", help="Step 0 values.download_page_url")
    r.add_argument("--changelog-url", help="the changelog URL from the planning issue")
    r.add_argument("--skip-promote-wait", metavar="REASON", help="the override reason, logged in the body")
    r.add_argument("--canned-body", help="file holding the [ANNOUNCE] template from canned-responses.md")
    r.add_argument(
        "--description", help="one sentence describing the product, from the planning issue or config"
    )
    r.add_argument("--dev-list", help="the project's dev list, from project.md")
    r.add_argument("--users-list", help="the project's users list, from project.md")
    r.add_argument(
        "--convenience",
        action="append",
        type=_pair,
        default=[],
        metavar="KIND=LOCATION",
        help="a convenience artefact release-promote published, and where",
    )
    r.add_argument(
        "--files", nargs="*", help="Step 3: the files the site bump would modify (default site_pr_files)"
    )
    r.add_argument(
        "--confirm-extra",
        nargs="*",
        default=[],
        help="Step 3: out-of-scope files the RM confirmed to include",
    )
    r.add_argument(
        "--body-file", default="<scratch>/announce-pr-body.md", help="Step 3: where the body is saved"
    )


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "verdict":
        emit(
            render.verdict(
                _json(args.preflight), promoted=args.promoted, planning_issue_found=not args.no_planning_issue
            )
        )
        return 0
    try:
        a = render.Announce.from_load(
            _json(args.load), product_name=args.product_name, project_name=args.project_name
        )
        if args.step == "2":
            out = render.step2(
                a,
                download_page=args.download_page,
                changelog_url=args.changelog_url,
                skip_reason=args.skip_promote_wait,
                canned_body=Path(args.canned_body).read_text(encoding="utf-8") if args.canned_body else None,
                description=args.description,
                dev_list=args.dev_list,
                users_list=args.users_list,
                convenience=args.convenience,
            )
        else:
            out = render.step3(
                a, files=args.files, confirmed_extra=args.confirm_extra, body_file=args.body_file
            )
    except render.RenderError as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    emit({"ok": True, "step": args.step} | out)
    return 0
