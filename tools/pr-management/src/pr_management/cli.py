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
"""`pr-management` — the deterministic core of the pr-management skills.

Every subcommand reads files (the adopter's `<project-config>` and the reads
`vetted-op-read --save` wrote) and prints one JSON document. None of them
calls GitHub: under the secure setup `gh` only works outside the sandbox, so
the skill runs the reads and this tool does everything that follows.
Exit 0 once JSON is printed; 2 for a usage error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Sequence
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from . import ci, config, mdconfig, model, people
from .triage import classify as triage_classify
from .triage import fold as triage_fold
from .triage import guards as triage_guards
from .triage import output as triage_output
from .triage import preflight as triage_preflight
from .triage import render as triage_render
from .triage import run as triage_run
from .triage import session as triage_session
from .triage import sweeps as triage_sweeps

#: The file names the triage skill saves its reads under (`vetted-op-read --save`).
SAVED = {
    "pages": "triage-pages.json",
    "action_required": "action-required.json",
    "main_failures": "main-failures.json",
    "team": "team-members.txt",
}


def _now(value: str | None) -> dt.datetime:
    if value:
        parsed = model.parse_time(value)
        if parsed is None:
            raise SystemExit(f"pr-management: --now {value!r} is not an ISO-8601 time")
        return parsed
    return dt.datetime.now(dt.UTC)


def _optional(directory: Path | None, name: str) -> Path | None:
    if directory is None:
        return None
    path = directory / name
    return path if path.is_file() else None


def _triage_classify(args: argparse.Namespace) -> dict[str, Any]:
    cfg = config.load(args.project_root, args.config_dir)
    saved: Path | None = args.saved_dir
    pages = [Path(p) for p in args.pages] or [p for p in [_optional(saved, SAVED["pages"])] if p]
    if not pages:
        raise SystemExit("pr-management: no pages — pass --pages, or --saved-dir holding triage-pages.json")
    prs, page_count = model.load_pages(pages)
    if args.label:
        prs = [pr for pr in prs if any(fnmatchcase(label, args.label) for label in pr.labels)]

    for pr in prs:
        rest = _optional(saved, f"check-runs-{pr.number}.json")
        if rest is not None:
            pr.rest_failed_checks = ci.load_rest_failures(rest)
        compare = _optional(saved, f"compare-{pr.number}.json")
        if compare is not None:
            data = json.loads(compare.read_text(encoding="utf-8"))
            pr.commits_behind = int(data.get("behind_by") or 0)
        liveness = _optional(saved, f"liveness-{pr.number}.json")
        if liveness is not None:
            pr.extra["liveness"] = triage_sweeps.liveness_from(
                json.loads(liveness.read_text(encoding="utf-8"))
            )

    team_path = _optional(saved, SAVED["team"])
    maintainers = people.Maintainers(
        team=people.load_team(team_path),
        permissions=people.load_permissions(sorted(saved.glob("permission-*")) if saved else []),
    )
    session: dict[str, dict[str, Any]] = {}
    if args.session and Path(args.session).is_file():
        session = json.loads(Path(args.session).read_text(encoding="utf-8")).get("prs", {})
    opts = triage_classify.Options(
        viewer=args.viewer, now=_now(args.now), authors=args.authors, session=session
    )
    decisions = triage_run.classify(
        prs,
        cfg,
        opts,
        maintainers,
        ci.load_action_required(_optional(saved, SAVED["action_required"])),
        ci.load_systemic(_optional(saved, SAVED["main_failures"])),
    )
    result = triage_output.build(decisions, cfg, viewer=args.viewer, pages=page_count)
    prefetch: list[dict[str, Any]] = []
    if cfg.committers_team_slug and team_path is None:
        prefetch.append({"op": "team-members", "params": [cfg.committers_team_slug], "save": SAVED["team"]})
    if _optional(saved, SAVED["action_required"]) is None:
        prefetch.append({"op": "runs-action-required", "params": [], "save": SAVED["action_required"]})
    if _optional(saved, SAVED["main_failures"]) is None:
        prefetch.append({"op": "gql-main-recent-failures", "params": [], "save": SAVED["main_failures"]})
    for login in sorted(maintainers.unresolved, key=str.lower):
        result["needs"].append(
            {
                "op": "upstream-permission",
                "params": [login],
                "save": f"permission-{login}",
                "why": "maintainer status decided conservatively; resolve and classify again",
            }
        )
    result["counts"]["needs_reads"] = len(result["needs"])
    result["prefetch"] = prefetch
    if args.max is not None:
        _cap(result, args.max)
    result["config"]["sources"] = cfg.sources
    return result


def _triage_render(args: argparse.Namespace) -> dict[str, Any]:
    cfg = config.load(args.project_root, args.config_dir)
    resolver = mdconfig.Resolver(args.project_root, args.config_dir)
    saved: Path = args.saved_dir
    pages = [Path(p) for p in args.pages] or [saved / SAVED["pages"]]
    prs, _ = model.load_pages([p for p in pages if p.is_file()])
    by_number = {pr.number: pr for pr in prs}
    if args.pr not in by_number:
        raise SystemExit(f"pr-management: PR {args.pr} is not in the saved pages")
    pr = by_number[args.pr]
    rest = saved / f"check-runs-{pr.number}.json"
    if rest.is_file():
        pr.rest_failed_checks = ci.load_rest_failures(rest)
    compare = saved / f"compare-{pr.number}.json"
    if compare.is_file():
        pr.commits_behind = int(json.loads(compare.read_text(encoding="utf-8")).get("behind_by") or 0)
    details = triage_render.load_details(args.details_json)
    classification = args.classification or details.pop("classification", None)
    rendered = triage_render.render(
        pr,
        cfg,
        action=args.action,
        classification=classification,
        viewer=args.viewer,
        now=_now(args.now),
        details=details,
        prs=prs,
        overrides=triage_render.template_overrides(resolver),
        sec_list=triage_render.security_list(resolver),
        template=args.template,
    )
    body_file: str | None = None
    if rendered.body is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        target = args.out_dir / f"pr-{pr.number}-{args.action}.md"
        target.write_text(rendered.body, encoding="utf-8")
        body_file = str(target)
    return {
        "pr": pr.number,
        "action": args.action,
        "row": args.row,
        "channel": rendered.channel,
        "template": rendered.template,
        "body_file": body_file,
        "mentions": rendered.mentions,
        "assign_author": rendered.assign_author,
        "unassign_author": rendered.unassign_author,
        "preview": "\n".join((rendered.body or "").splitlines()[:30]),
        "ok": not rendered.warnings,
        "warnings": rendered.warnings,
    }


def _triage_guard(args: argparse.Namespace) -> dict[str, Any]:
    liveness = _optional(args.saved_dir, f"liveness-{args.pr}.json")
    runs = _optional(args.saved_dir, f"runs-head-{args.pr}.json")
    result = triage_guards.check(
        args.action,
        expected_head=args.head,
        liveness=triage_guards.load_liveness(liveness) if liveness else None,
        runs=triage_guards.load_runs(runs) if runs else None,
    )
    result["pr"] = args.pr
    return result


def _cap(result: dict[str, Any], limit: int) -> None:
    """Keep the first `limit` PRs across the groups, in presentation order."""
    left = limit
    kept = []
    for group in result["groups"]:
        if left <= 0:
            break
        group["prs"] = group["prs"][:left]
        left -= len(group["prs"])
        kept.append(group)
    result["groups"] = kept
    result["capped_at"] = limit


def _triage_fold(args: argparse.Namespace) -> dict[str, Any]:
    body = triage_fold.read_body(args.current_body)
    block = args.block.read_text(encoding="utf-8")
    new, replaced = triage_fold.splice(body, block)
    args.out.write_text(new, encoding="utf-8")
    return {"out": str(args.out), "replaced": replaced, "bytes": len(new.encode("utf-8"))}


def _triage_session(args: argparse.Namespace) -> dict[str, Any]:
    now = _now(args.now) if args.now else None
    if args.session_command == "record":
        entry = triage_session.record(
            args.session,
            pr=args.pr,
            head=args.head,
            action=args.action,
            classification=args.classification,
            terminal=True if args.terminal else None,
            reason=args.reason,
            now=now,
        )
        return {"pr": args.pr, **entry}
    classify_out = json.loads(args.classify.read_text(encoding="utf-8")) if args.classify else None
    return triage_session.summary(args.session, classify=classify_out, now=now)


def _config(args: argparse.Namespace) -> dict[str, Any]:
    cfg = config.load(args.project_root, args.config_dir)
    data = dict(vars(cfg))
    data["check_map"] = [vars(row) for row in cfg.check_map]
    return data


# --- pr-management-stats --------------------------------------------------------


def _add_stats_parsers(sub: Any) -> None:
    stats = sub.add_parser("stats", help="pr-management-stats")
    stats_sub = stats.add_subparsers(dest="command", required=True)
    bld = stats_sub.add_parser("build", help="fetch-free build of the whole dashboard from the saved reads")
    bld.add_argument(
        "--saved-dir", type=Path, default=None, help="the vetted-ops workspace's saved/ directory"
    )
    bld.add_argument("--viewer", required=True, help="the authenticated maintainer's login")
    bld.add_argument(
        "--out", type=Path, required=True, help="the dashboard file to write (keep it dashboard.html)"
    )
    bld.add_argument("--since", default=None, help="cutoff YYYY-MM-DD (default: six weeks ago)")
    bld.add_argument(
        "--fast-closed", action="store_true", help="closed PRs from the search index (capped, lags)"
    )
    bld.add_argument("--format", choices=("html", "markdown"), default="html")
    bld.add_argument(
        "--fetch-with-gh", action="store_true", help="fetch through gh directly (CI, outside the sandbox)"
    )
    bld.add_argument("--repo", default=None, help="owner/name for --fetch-with-gh (default: upstream_repo)")
    bld.add_argument("--now", default=None, help="evaluate as of this ISO-8601 time (tests, replays)")
    rec = stats_sub.add_parser("record-gist", help="store the dashboard gist's id for in-place updates")
    rec.add_argument("gist_id")


def _stats(args: argparse.Namespace) -> dict[str, Any]:
    from .stats import build as stats_build

    if args.command == "record-gist":
        if not args.gist_id.isalnum():
            raise SystemExit(f"pr-management: {args.gist_id!r} is not a gist id")
        return stats_build.record_gist(args.project_root, args.gist_id)
    if args.since is not None:
        try:
            dt.datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            raise SystemExit(f"pr-management: --since {args.since!r} is not YYYY-MM-DD") from None
    return stats_build.build(
        project_root=args.project_root,
        config_dir=args.config_dir,
        saved=args.saved_dir,
        viewer=args.viewer,
        out=args.out,
        since=args.since,
        fast_closed=args.fast_closed,
        fetch_with_gh=args.fetch_with_gh,
        repo=args.repo,
        fmt=args.format,
        now=_now(args.now) if args.now else None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pr-management", description=__doc__.splitlines()[0])
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="the adopter repository root")
    parser.add_argument(
        "--config-dir", type=Path, default=None, help="read every config file from this directory"
    )
    sub = parser.add_subparsers(dest="family", required=True)

    sub.add_parser("config", help="print the resolved configuration")

    triage = sub.add_parser("triage", help="pr-management-triage")
    triage_sub = triage.add_subparsers(dest="command", required=True)
    cls = triage_sub.add_parser("classify", help="Step 2: pre-filters and the decision table")
    cls.add_argument(
        "--saved-dir", type=Path, default=None, help="the vetted-ops workspace's saved/ directory"
    )
    cls.add_argument(
        "--pages", nargs="*", default=[], help="saved sweep pages (default: <saved-dir>/triage-pages.json)"
    )
    cls.add_argument("--viewer", required=True, help="the authenticated maintainer's login")
    cls.add_argument("--authors", choices=("default", "all", "collaborators"), default="default")
    cls.add_argument("--session", default=None, help="the session cache JSON")
    cls.add_argument("--now", default=None, help="evaluate as of this ISO-8601 time (tests, replays)")
    cls.add_argument(
        "--label", default=None, help="keep only PRs with a label matching this glob (e.g. 'area:*')"
    )
    cls.add_argument("--max", type=int, default=None, help="present at most this many PRs, in group order")

    pre = triage_sub.add_parser(
        "preflight", help="Step 0 checks 2-3: viewer permission and the triage labels"
    )
    pre.add_argument("--saved-dir", type=Path, required=True)

    grd = triage_sub.add_parser("guard", help="the pre-mutation guard for one action, on fresh reads")
    grd.add_argument("action")
    grd.add_argument("--pr", type=int, required=True)
    grd.add_argument("--head", required=True, help="the head SHA the PR was classified at")
    grd.add_argument("--saved-dir", type=Path, required=True)

    ren = triage_sub.add_parser("render", help="render the contributor-facing body of one action")
    ren.add_argument(
        "--saved-dir", type=Path, required=True, help="the vetted-ops workspace's saved/ directory"
    )
    ren.add_argument(
        "--pages", nargs="*", default=[], help="saved sweep pages (default: <saved-dir>/triage-pages.json)"
    )
    ren.add_argument("--pr", type=int, required=True)
    ren.add_argument("--action", required=True)
    ren.add_argument("--classification", default=None)
    ren.add_argument("--row", default=None)
    ren.add_argument("--template", default=None, help="force a template stem")
    ren.add_argument("--viewer", required=True, help="the authenticated maintainer's login")
    ren.add_argument("--out-dir", type=Path, required=True)
    ren.add_argument("--details-json", type=Path, default=None, help="the classify group entry for this PR")
    ren.add_argument("--now", default=None)

    fld = triage_sub.add_parser("fold", help="splice a fold block into a PR body, replacing any previous one")
    fld.add_argument(
        "--current-body", type=Path, required=True, help="raw body, or the saved pr-view-with-body JSON"
    )
    fld.add_argument("--block", type=Path, required=True)
    fld.add_argument("--out", type=Path, required=True)

    ses = triage_sub.add_parser("session", help="the session cache and the Step 6 summary")
    ses_sub = ses.add_subparsers(dest="session_command", required=True)
    rec = ses_sub.add_parser("record", help="record what was done to one PR")
    rec.add_argument("--session", type=Path, required=True)
    rec.add_argument("--pr", type=int, required=True)
    rec.add_argument("--head", required=True)
    rec.add_argument("--action", required=True)
    rec.add_argument("--classification", default=None)
    rec.add_argument("--reason", default=None)
    rec.add_argument("--terminal", action="store_true", help="suppress the PR for the rest of the session")
    rec.add_argument("--now", default=None)
    summ = ses_sub.add_parser("summary", help="print the Step 6 session summary")
    summ.add_argument("--session", type=Path, required=True)
    summ.add_argument("--classify", type=Path, default=None, help="this session's classify output")
    summ.add_argument("--now", default=None)

    _add_stats_parsers(sub)

    args = parser.parse_args(argv)
    result: dict[str, Any] = {}
    if args.family == "config":
        result = _config(args)
    elif args.family == "triage" and args.command == "classify":
        result = _triage_classify(args)
    elif args.family == "triage" and args.command == "render":
        result = _triage_render(args)
    elif args.family == "triage" and args.command == "fold":
        result = _triage_fold(args)
    elif args.family == "triage" and args.command == "session":
        result = _triage_session(args)
    elif args.family == "triage" and args.command == "preflight":
        result = triage_preflight.check(
            args.saved_dir / "preflight.json", config.load(args.project_root, args.config_dir)
        )
    elif args.family == "triage" and args.command == "guard":
        result = _triage_guard(args)
    elif args.family == "stats":
        result = _stats(args)
    else:  # pragma: no cover - argparse enforces the choices
        parser.error("unknown command")
    json.dump(result, sys.stdout, indent=2, default=str, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
