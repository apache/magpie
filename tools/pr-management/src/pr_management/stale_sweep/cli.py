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
"""`pr-management stale-sweep plan | classify | render | record | recap`."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from .. import config, mentions, model, people
from . import classify as stale_classify
from . import plan as stale_plan
from . import recap as stale_recap
from . import render as stale_render

FAMILY = "stale-sweep"
#: Where `classify` keeps its output for `render` and `recap`.
CLASSIFIED = "stale-classify.json"


def add_parsers(sub: Any) -> None:
    family = sub.add_parser(FAMILY, help="pr-stale-sweep")
    cmds = family.add_subparsers(dest="command", required=True)

    pln = cmds.add_parser("plan", help="Step 0-1: thresholds, selector validation, the reads to save")
    pln.add_argument(
        "selector", nargs="*", help="the selector as typed: stale, label:<l>, warn:<N>, 42,88, …"
    )

    cls = cmds.add_parser("classify", help="Steps 1-3: the pool, the per-PR state, one class per PR")
    cls.add_argument("--saved-dir", type=Path, required=True)
    cls.add_argument("--now", default=None)
    cls.add_argument("selector", nargs="*")

    ren = cmds.add_parser("render", help="Step 4: the comment for one proposal")
    mentions.add_flag(ren)
    ren.add_argument("--saved-dir", type=Path, required=True)
    ren.add_argument("--pr", type=int, required=True)
    ren.add_argument("--out-dir", type=Path, required=True)

    rec = cmds.add_parser("record", help="Step 6: record what happened to one PR")
    rec.add_argument("--session", type=Path, required=True)
    rec.add_argument("--pr", type=int, required=True)
    rec.add_argument("--class", dest="cls", required=True)
    rec.add_argument("--outcome", choices=stale_recap.OUTCOMES, required=True)
    rec.add_argument("--comment-url", default=None)

    rcp = cmds.add_parser("recap", help="Step 7: the recap")
    rcp.add_argument("--session", type=Path, required=True)
    rcp.add_argument("--saved-dir", type=Path, required=True)


def _now(value: str | None) -> dt.datetime:
    parsed = model.parse_time(value) if value else None
    return parsed or dt.datetime.now(dt.UTC)


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    cfg = mentions.apply_flag(config.load(args.project_root, args.config_dir), args)
    if args.command == "plan":
        return stale_plan.build(
            args.selector, args.project_root, args.config_dir, cfg.committers_team
        ).as_dict()
    if args.command == "classify":
        plan = stale_plan.build(args.selector, args.project_root, args.config_dir, cfg.committers_team)
        if plan.error:
            return {"error": plan.error, "plan": plan.as_dict()}
        saved: Path = args.saved_dir
        paths = [saved / stale_plan.PAGES] if (saved / stale_plan.PAGES).is_file() else []
        paths += sorted(saved.glob("stale-one-*.json"))
        if not paths:
            return {
                "needs": plan.reads,
                "error": None,
                "warnings": ["no saved sweep yet — save the reads first"],
            }
        team = saved / stale_plan.TEAM
        maintainers = people.Maintainers(
            team=people.load_team(team if team.is_file() else None),
            permissions=people.load_permissions(sorted(saved.glob("permission-*"))),
        )
        result = stale_classify.sweep(stale_classify.load(paths), plan, cfg, maintainers, _now(args.now))
        (saved / CLASSIFIED).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        result["saved_as"] = str(saved / CLASSIFIED)
        return result
    if args.command == "render":
        classified = json.loads((args.saved_dir / CLASSIFIED).read_text(encoding="utf-8"))
        entry = next((p for p in classified.get("proposals", []) if p["number"] == args.pr), None)
        if entry is None:
            return {"error": f"#{args.pr} is not a proposal of the last classify run"}
        return stale_render.render(entry, cfg, args.out_dir)
    if args.command == "record":
        return stale_recap.record(args.session, args.pr, args.cls, args.outcome, args.comment_url)
    classified = json.loads((args.saved_dir / CLASSIFIED).read_text(encoding="utf-8"))
    session = json.loads(args.session.read_text(encoding="utf-8")) if args.session.is_file() else {"prs": {}}
    return stale_recap.recap(session, classified, cfg.upstream_repo or "<upstream>")
