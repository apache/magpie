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
"""`pr-management quick-merge …` — discovered by the main CLI."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

from .. import config
from . import approve, screen
from .config import load as load_quick_merge

FAMILY = "quick-merge"


def add_parsers(sub: Any) -> None:
    family = sub.add_parser(FAMILY, help="pr-management-quick-merge")
    commands = family.add_subparsers(dest="command", required=True)
    scr = commands.add_parser("screen", help="the three-stage screen over the saved ready queue")
    scr.add_argument("--saved-dir", type=Path, required=True)
    scr.add_argument("--tier", choices=("A", "B"), default=None, help="A: Tier A only; B: A and B")
    scr.add_argument("--max-churn", type=int, default=None)
    scr.add_argument("--pr", type=int, default=None, help="screen one PR (saved as express-one-<N>.json)")
    scr.add_argument("--session", type=Path, default=None)
    chk = commands.add_parser("approve-check", help="the approve safety protocol, on fresh reads")
    chk.add_argument("--saved-dir", type=Path, required=True)
    chk.add_argument("--pr", type=int, required=True)
    chk.add_argument("--head", required=True, help="the head SHA the PR was screened at")
    chk.add_argument("--session", type=Path, default=None)
    chk.add_argument("--out-dir", type=Path, default=None)
    chk.add_argument("--viewer", default=None, help="the maintainer's login, credited in an approve_body")
    ses = commands.add_parser("session", help="record a diff view or an approve")
    ses.add_argument("kind", choices=("view", "approve"))
    ses.add_argument("--session", type=Path, required=True)
    ses.add_argument("--pr", type=int, required=True)
    ses.add_argument("--head", required=True)


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    cfg = config.load(args.project_root, args.config_dir)
    if args.command == "session":
        return approve.record(args.session, args.kind, args.pr, args.head, dt.datetime.now(dt.UTC))
    qcfg = load_quick_merge(args.project_root, args.config_dir)
    session = approve.read_session(args.session)
    if args.command == "screen":
        tiers = ("A",) if args.tier == "A" else ("A", "B") if args.tier == "B" else None
        result = screen.run(
            args.saved_dir, cfg, qcfg, tiers=tiers, max_churn=args.max_churn, single=args.pr, session=session
        )
        result["approvals_this_session"] = sorted(int(n) for n in session.get("approved", {}))
        return result
    return approve.check(
        args.saved_dir,
        cfg,
        qcfg,
        number=args.pr,
        head=args.head,
        session=session,
        out_dir=args.out_dir,
        viewer=args.viewer,
    )
