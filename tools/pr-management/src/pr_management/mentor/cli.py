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
"""`pr-management mentor …` — the deterministic half of pr-management-mentor."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from .. import config as core_config
from .. import mentions
from ..layers import personal_dir
from ..people import Maintainers, load_permissions, load_team
from . import config, render, thread, tone

FAMILY = "mentor"
OUTCOMES = ("drafted-and-posted", "drafted-and-discarded", "declined-pre-draft", "handed-off")


def saved_names(kind: str, number: int) -> dict[str, str]:
    """The `--save` names the skill uses for one thread's reads."""
    if kind == "issue":
        return {"view": f"mentor-issue-{number}.json"}
    return {"view": f"mentor-pr-{number}.json", "comments": f"mentor-pr-comments-{number}.json"}


HANDOFF_DOCS = {
    1: "classifications/handoff-max-turns.md",
    2: "classifications/handoff-pushback.md",
    3: "classifications/handoff-out-of-scope.md",
    4: "classifications/handoff-wants-human.md",
}


def _docs(result: dict[str, Any]) -> list[str]:
    """The classification documents the agent reads for this outcome."""
    outcome = result.get("outcome")
    if outcome == "handoff":
        return [HANDOFF_DOCS[result["handoff"]["trigger"]], "classifications/hand-off-comment.md"]
    if outcome == "draft":
        return ["classifications/pick-intervention.md"]
    return [f"classifications/{str(outcome).replace('_', '-')}.md"]


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="pr-management-mentor")
    cmd = parser.add_subparsers(dest="command", required=True)
    cmd.add_parser("config", help="the resolved mentoring configuration and what is missing")

    assess = cmd.add_parser("assess", help="hand-off, maintainer-engaged and scope decision for one thread")
    assess.add_argument("--saved-dir", type=Path, required=True)
    assess.add_argument("--kind", choices=("pr", "issue"), required=True)
    assess.add_argument("--number", type=int, required=True)
    assess.add_argument("--viewer", required=True)

    ren = cmd.add_parser("render", help="render an intervention or the hand-off, then tone-check it")
    ren.add_argument("--kind", choices=(*render.INTERVENTIONS, "hand-off"), required=True)
    ren.add_argument("--author", default=None)
    ren.add_argument("--pointer", default=None, help="the convention_pointers trigger the comment links")
    ren.add_argument("--open-question-file", type=Path, default=None, help="hand-off: one-line open question")
    ren.add_argument("--out", type=Path, required=True)
    mentions.add_flag(ren)

    chk = cmd.add_parser("tone-check", help="run the deterministic tone rules on a draft")
    chk.add_argument("--draft", type=Path, required=True)
    chk.add_argument("--author", default=None)

    log = cmd.add_parser("log", help="record the invocation outcome in the personal layer's audit log")
    log.add_argument("--number", type=int, required=True)
    log.add_argument("--kind", choices=("pr", "issue"), required=True)
    log.add_argument("--outcome", choices=OUTCOMES, required=True)
    log.add_argument("--trigger", type=int, choices=(1, 2, 3, 4), default=None)


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    cfg = config.load(args.project_root, args.config_dir)
    if args.command == "config":
        return {
            "source": cfg.source,
            "missing": cfg.missing,
            "max_agent_turns": cfg.max_agent_turns,
            "maintainer_team_handle": cfg.maintainer_team_handle,
            "pointers": [vars(p) for p in cfg.pointers],
            "out_of_scope": cfg.keywords(),
            "committers_team": cfg.committers_team,
        }
    if args.command == "assess":
        names = saved_names(args.kind, args.number)
        saved: Path = args.saved_dir
        missing = [n for n in names.values() if not (saved / n).is_file()]
        needs: list[dict[str, Any]] = []
        for key, name in names.items():
            if name in missing:
                op = {
                    "view": "repo-issue-view" if args.kind == "issue" else "pr-view-with-body",
                    "comments": "pr-comments",
                }[key]
                needs.append({"op": op, "params": [str(args.number)], "save": name})
        team_file = saved / "team-members.txt"
        slug = cfg.committers_team.split("/", 1)[-1] if cfg.committers_team else None
        if slug and not team_file.is_file():
            needs.append({"op": "team-members", "params": [slug], "save": "team-members.txt"})
        if needs:
            return {"outcome": "needs", "needs": needs}
        people = Maintainers(
            team=load_team(team_file if team_file.is_file() else None),
            permissions=load_permissions(sorted(saved.glob("permission-*"))),
        )
        view = saved / names["view"]
        comments = saved / names["comments"] if "comments" in names else None
        result = thread.assess(thread.load(args.kind, args.number, view, comments), cfg, args.viewer, people)
        result["docs"] = _docs(result)
        result["needs"] = [
            {"op": "upstream-permission", "params": [login], "save": f"permission-{login}"}
            for login in sorted(people.unresolved, key=str.lower)
        ]
        return result
    if args.command == "render":
        question = args.open_question_file.read_text(encoding="utf-8") if args.open_question_file else None
        core = mentions.apply_flag(core_config.load(args.project_root, args.config_dir), args)
        upstream = core.upstream_repo
        return render.render(
            cfg,
            kind=args.kind,
            author=args.author,
            pointer=args.pointer,
            open_question=question,
            upstream=upstream,
            out=args.out,
            allowed=mentions.allowed(core),
        )
    if args.command == "tone-check":
        return tone.check(args.draft.read_text(encoding="utf-8"), author=args.author, footer=cfg.footer)
    if args.command == "log":
        home = personal_dir(args.project_root)
        if home is None:
            return {"logged": False, "reason": "no personal config layer"}
        path = home / "logs" / "pr-management-mentor.jsonl"
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        entry = {
            "at": dt.datetime.now(dt.UTC).isoformat(),
            "kind": args.kind,
            "number": args.number,
            "outcome": args.outcome,
            "trigger": args.trigger,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        return {"logged": True, "log": str(path), **entry}
    raise SystemExit(f"pr-management mentor: unknown command {args.command!r}")
