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
"""`pr-management reviewer-routing …` — pre-flight, and the whole score-and-propose step."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
from pathlib import Path
from typing import Any

from .. import config as core_config
from . import codeowners, roster, score

FAMILY = "reviewer-routing"
_TARGET = re.compile(r"^(?:(pr|issue):)?(\d{1,10})$")
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
NO_ROSTER_BLOCKER = (
    "no roster file found — create reviewer-roster.md or release-trains.md in the project config directory"
)


def parse_target(value: str) -> tuple[str, int] | None:
    match = _TARGET.match(value.strip())
    if not match:
        return None
    return match.group(1) or "pr", int(match.group(2))


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="reviewer-routing")
    cmd = parser.add_subparsers(dest="command", required=True)
    pre = cmd.add_parser("preflight", help="Step 0: input, roster and privacy-gate verdict")
    pre.add_argument("--target", required=True, help="pr:<N>, issue:<N>, or <N>")
    pre.add_argument("--repo", default=None)
    pre.add_argument("--privacy-exit", type=int, required=True, help="privacy-llm-check's exit code")
    pre.add_argument("--privacy-message", default="", help="privacy-llm-check's error line, when it failed")

    pro = cmd.add_parser("propose", help="Steps 2-4: gather saved signals, score, render the proposal")
    pro.add_argument("--target", required=True)
    pro.add_argument("--repo", default=None)
    pro.add_argument("--saved-dir", type=Path, required=True)
    pro.add_argument("--area", action="append", default=[], help="an area the agent inferred from the title")
    pro.add_argument("--no-codeowners", action="store_true", help="the CODEOWNERS read failed (no such file)")
    pro.add_argument("--injection", default=None, help="one-line summary of a flagged injection attempt")


def _upstream(args: argparse.Namespace) -> str | None:
    repo = args.repo or core_config.load(args.project_root, args.config_dir).upstream_repo
    return repo if repo and _REPO.match(repo) else None


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    target = parse_target(args.target)
    upstream = _upstream(args)
    if target is None:
        blockers.append(f"input {args.target!r} is not pr:<N>, issue:<N> or <N>")
    if upstream is None:
        blockers.append("upstream_repo is not set in project.md (or --repo is not owner/name)")
    gate = args.privacy_exit == 0
    if not gate:
        detail = " ".join(args.privacy_message.split()) or "see its output"
        blockers.append(f"privacy-llm-check exited non-zero: {detail}")
    resolved = roster.load(args.project_root, args.config_dir)
    if resolved.source is None:
        blockers.append(NO_ROSTER_BLOCKER)
    return {
        "verdict": "blocked" if blockers else "proceed",
        "blockers": blockers,
        "privacy_gate_passed": gate,
        "roster_source": resolved.source,
        "item_type": target[0] if target else None,
        "item_number": target[1] if target else None,
        "upstream_repo": upstream,
    }


def _path_name(index: int) -> str:
    return f"routing-commits-{index}.txt"


def propose(args: argparse.Namespace) -> dict[str, Any]:
    target = parse_target(args.target)
    upstream = _upstream(args)
    if target is None or upstream is None:
        return {"error": "run preflight first: the target or the upstream repo is invalid"}
    kind, number = target
    saved: Path = args.saved_dir
    item_file = saved / f"routing-{kind}-{number}.json"
    if not item_file.is_file():
        op = "pr-view-with-body" if kind == "pr" else "repo-issue-view"
        return {"needs": [{"op": op, "params": [str(number)], "save": item_file.name}]}
    data = json.loads(item_file.read_text(encoding="utf-8"))
    paths = (
        sorted(str(f.get("path")) for f in data.get("files") or [] if f.get("path")) if kind == "pr" else []
    )
    item = score.Item(
        kind=kind,
        number=number,
        title=str(data.get("title") or ""),
        labels=[str(lbl.get("name")) for lbl in data.get("labels") or [] if lbl],
        paths=paths,
    )
    members = roster.load(args.project_root, args.config_dir)
    default_branch = core_config.load(args.project_root, args.config_dir).default_branch
    needs: list[dict[str, Any]] = []
    familiarity: dict[str, set[str]] = {}
    for index, path in enumerate(paths):
        commits = saved / _path_name(index)
        if not commits.is_file():
            needs.append({"op": "commits-by-path", "params": [path], "save": commits.name})
            continue
        for login in {
            line.strip().lower() for line in commits.read_text(encoding="utf-8").splitlines() if line.strip()
        }:
            familiarity.setdefault(login, set()).add(path)
    load: dict[str, int] = {}
    for member in members.members:
        found = saved / f"routing-load-{member.handle.lower()}.json"
        if not found.is_file():
            needs.append({"op": "pr-search-review-requested", "params": [member.handle], "save": found.name})
            continue
        load[member.handle.lower()] = len(json.loads(found.read_text(encoding="utf-8") or "[]"))
    owners: dict[str, set[str]] = {}
    owners_file = saved / "routing-codeowners.txt"
    if paths and not args.no_codeowners:
        if not owners_file.is_file():
            needs.append(
                {
                    "op": "repo-file",
                    "params": [".github/CODEOWNERS", default_branch],
                    "save": owners_file.name,
                    "on_failure": "no CODEOWNERS: re-run propose with --no-codeowners",
                }
            )
        else:
            raw = owners_file.read_text(encoding="utf-8").strip().strip('"').replace("\\n", "")
            try:
                text = base64.b64decode(raw).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                text = raw
            rules = codeowners.parse(text)
            for path in paths:
                for owner in codeowners.owners_of(path, rules):
                    owners.setdefault(owner.lower(), set()).add(path)
    if needs:
        return {"needs": needs}
    result = score.score(
        members, item, familiarity=familiarity, owners=owners, load=load, inferred_areas=list(args.area)
    )
    result["roster_source"] = members.source
    result["injection_flagged"] = bool(args.injection)
    result["proposal"] = score.render(result, item, upstream, args.injection)
    if not result.get("no_eligible_reviewer"):
        result["next_step"] = score.next_step(item, upstream, result["primary"]["handle"])
    result["classification"] = (
        "no-eligible-reviewer"
        if result.get("no_eligible_reviewer")
        else "primary-with-overloaded-backup"
        if (result.get("backup") or {}).get("overloaded")
        else "primary-and-backup"
        if result.get("backup")
        else "primary-only"
    )
    return result


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "preflight":
        return preflight(args)
    if args.command == "propose":
        return propose(args)
    raise SystemExit(f"pr-management reviewer-routing: unknown command {args.command!r}")
