# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""contributor-metrics CLI: `fetch` from the code host and tracker, `score` offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from contributor_metrics.backends.jira import InvalidJiraConfig, InvalidJiraUser, JiraError, JiraTracker
from contributor_metrics.fetch import (
    SUBSTANTIVE_BODY_CHARS,
    SUBSTANTIVE_LINE_COMMENTS,
    GhError,
    InvalidLogin,
    InvalidRepo,
    fetch_items,
)
from contributor_metrics.floors import DEFAULT_RELAXATION, propose_floors
from contributor_metrics.model import Item, Weights
from contributor_metrics.score import score


def _since(end: str, months: int) -> str:
    e = date.fromisoformat(end)
    y, m = divmod(e.year * 12 + e.month - 1 - months, 12)
    return date(y, m + 1, min(e.day, 28)).isoformat()


def _cache_file(
    cache_dir: str,
    repo: str,
    login: str,
    since: str,
    end: str,
    phrases: list[str],
    maintainers: list[str],
    substantive: tuple[int, int] = (SUBSTANTIVE_BODY_CHARS, SUBSTANTIVE_LINE_COMMENTS),
    backends: dict[str, Any] | None = None,
) -> Path:
    parts: list[Any] = [sorted(phrases), sorted(maintainers)]
    if substantive != (SUBSTANTIVE_BODY_CHARS, SUBSTANTIVE_LINE_COMMENTS):
        parts.append(list(substantive))  # default thresholds keep the keys of existing caches
    if backends:
        parts.append(backends)  # GitHub-only fetches keep the keys of existing caches
    key = hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:12]
    return Path(cache_dir) / f"{repo.replace('/', '__')}__{login}__{since}__{end}__{key}.json"


_CONFIG_ROW = re.compile(r"^\|\s*`?(url|project_key|tracker_type)`?\s*\|\s*(.*?)\s*\|\s*$")
TRACKER_TYPES = {"jira": "jira", "github-issues": "github", "github": "github"}


def read_tracker_config(path: str) -> dict[str, str]:
    """`url`, `project_key` and `tracker_type` from `<project-config>/issue-tracker-config.md`.

    The file's *URL and project key* table is the source other skills read for
    `<issue-tracker>`; unset (`TODO:`) values are skipped.
    """
    out: dict[str, str] = {}
    for line in Path(path).read_text().splitlines():
        m = _CONFIG_ROW.match(line.strip())
        if not m:
            continue
        value = m.group(2).strip().strip("`").strip()
        if value and not value.upper().startswith("TODO"):
            out.setdefault(m.group(1), value)
    return out


def _resolve_tracker(args: argparse.Namespace) -> tuple[str, str, str]:
    """(kind, url, project) for the tracker side; flags override the config file."""
    cfg = read_tracker_config(args.tracker_config) if args.tracker_config else {}
    kind = args.tracker or TRACKER_TYPES.get(cfg.get("tracker_type", "").lower(), "")
    if not kind:
        if cfg.get("tracker_type"):
            raise InvalidJiraConfig(
                f"unsupported tracker_type {cfg['tracker_type']!r} (expected jira or github-issues)"
            )
        kind = "github"
    url = project = ""
    if kind == "jira":
        url = args.jira_url or cfg.get("url") or os.environ.get("ISSUE_TRACKER_URL", "")
        project = args.jira_project or cfg.get("project_key") or os.environ.get("ISSUE_TRACKER_PROJECT", "")
        if not url or not project:
            raise InvalidJiraConfig(
                "a Jira tracker needs a URL and a project key (config file, flags or environment)"
            )
    elif cfg.get("project_key") and cfg["project_key"].lower() != args.repo.lower():
        raise InvalidJiraConfig(
            f"GitHub issues on {cfg['project_key']!r} differ from --repo {args.repo!r}; not supported"
        )
    return kind, url, project


def _read(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="contributor-metrics")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="fetch a contributor's activity items from the code host and tracker")
    f.add_argument("--repo", required=True, help="the code-host repository, owner/name")
    f.add_argument("--login", required=True, help="the contributor's code-host handle")
    f.add_argument(
        "--code-host",
        choices=("github",),
        default="github",
        help="backend for PRs and reviews (default github)",
    )
    f.add_argument(
        "--tracker",
        choices=("github", "jira"),
        help="backend for issues; default: from --tracker-config, else the code host",
    )
    f.add_argument(
        "--tracker-config", help="<project-config>/issue-tracker-config.md (tracker_type, url, project_key)"
    )
    f.add_argument("--jira-url", help="Jira base URL; overrides the config file and ISSUE_TRACKER_URL")
    f.add_argument(
        "--jira-project", help="Jira project key; overrides the config file and ISSUE_TRACKER_PROJECT"
    )
    f.add_argument(
        "--tracker-login", help="the contributor's account on the tracker, when it differs from --login"
    )
    f.add_argument(
        "--tracker-maintainers-file",
        help="whitespace-separated maintainer accounts on the tracker (default: --maintainers-file)",
    )
    f.add_argument("--end", required=True)
    f.add_argument("--months", type=int, default=6)
    f.add_argument("--since", help="window start YYYY-MM-DD; overrides --months")
    f.add_argument(
        "--substantive-body-chars",
        type=int,
        default=SUBSTANTIVE_BODY_CHARS,
        help="a review is substantive when its body is longer than this many characters",
    )
    f.add_argument(
        "--substantive-line-comments",
        type=int,
        default=SUBSTANTIVE_LINE_COMMENTS,
        help="... or when it carries at least this many line comments",
    )
    f.add_argument(
        "--cache-dir",
        default=os.path.join(os.environ.get("TMPDIR") or tempfile.gettempdir(), "contributor-metrics-cache"),
    )
    f.add_argument("--refresh", action="store_true", help="ignore any cached result and fetch again")
    f.add_argument("--phrases-file")
    f.add_argument("--maintainers-file")
    f.add_argument("--out", required=True)
    s = sub.add_parser("score", help="apply weights and the pushback penalty to fetched items")
    s.add_argument("--items", required=True)
    s.add_argument("--classes")
    s.add_argument("--weights")
    s.add_argument("--area-prefix", default="area:")
    s.add_argument("--since", help="score only items on or after this date (a sub-window of the fetched one)")
    s.add_argument(
        "--timeline-kinds",
        help="comma-separated item kinds the timeline counts (default: every kind)",
    )
    s.add_argument("--out", required=True)
    fl = sub.add_parser("floors", help="propose threshold floors from measured past nominations")
    fl.add_argument(
        "--rows", required=True, help="JSON list of {target, outcome, vote_date, metrics, capped}"
    )
    fl.add_argument("--today", default=date.today().isoformat())
    fl.add_argument("--halflife", type=float, default=2.0)
    fl.add_argument("--min-elected", type=int, default=5)
    fl.add_argument(
        "--relaxation",
        type=float,
        default=DEFAULT_RELAXATION,
        help="scale the elected p25 down by this factor, in (0, 1]; deliberately surfaces more people",
    )
    fl.add_argument("--out", required=True)
    args = p.parse_args(argv)

    if args.cmd == "floors":
        rows = json.loads(Path(args.rows).read_text())
        result = propose_floors(
            rows,
            today=args.today,
            halflife=args.halflife,
            min_elected=args.min_elected,
            relaxation=args.relaxation,
        )
        Path(args.out).write_text(json.dumps(result, indent=2))
        return 0

    if args.cmd == "fetch":
        try:
            end_day = date.fromisoformat(args.end)
            since = (
                date.fromisoformat(args.since).isoformat() if args.since else _since(args.end, args.months)
            )
        except ValueError as exc:
            print(f"invalid date (expected YYYY-MM-DD): {exc}", file=sys.stderr)
            return 2
        if since > end_day.isoformat():
            print(f"--since {since} is after --end {args.end}", file=sys.stderr)
            return 2
        substantive = (args.substantive_body_chars, args.substantive_line_comments)
        phrases = Path(args.phrases_file).read_text().splitlines() if args.phrases_file else []
        maintainers = Path(args.maintainers_file).read_text().split() if args.maintainers_file else []
        try:
            kind, jira_url, jira_project = _resolve_tracker(args)
        except (InvalidJiraConfig, OSError) as exc:
            print(f"invalid tracker configuration: {exc}", file=sys.stderr)
            return 2
        tracker_login = args.tracker_login or args.login
        tracker_maintainers = (
            Path(args.tracker_maintainers_file).read_text().split() if args.tracker_maintainers_file else None
        )
        backends: dict[str, Any] = {}
        tracker_kwargs: dict[str, Any] = {}
        if kind == "jira":
            backends = {
                "code_host": args.code_host,
                "tracker": "jira",
                "tracker_url": jira_url.rstrip("/"),
                "tracker_project": jira_project,
                "tracker_login": tracker_login,
            }
            try:
                tracker = JiraTracker(jira_url, jira_project)
            except InvalidJiraConfig as exc:
                print(f"invalid tracker configuration: {exc}", file=sys.stderr)
                return 2
            tracker_kwargs = {
                "tracker": tracker,
                "tracker_login": tracker_login,
                "tracker_maintainers": tracker_maintainers,
            }
        cached = _cache_file(
            args.cache_dir,
            args.repo,
            args.login,
            since,
            args.end,
            phrases,
            maintainers,
            substantive,
            {**backends, "tracker_maintainers": sorted(tracker_maintainers or [])} if backends else None,
        )
        if cached.exists() and not args.refresh:
            Path(args.out).write_text(cached.read_text())
            return 0
        try:
            items, caps, fetch_notes = fetch_items(
                args.repo,
                args.login,
                since=since,
                end=args.end,
                phrases=phrases,
                maintainers=maintainers,
                substantive_body_chars=substantive[0],
                substantive_line_comments=substantive[1],
                **tracker_kwargs,
            )
        except InvalidLogin as exc:
            print(f"invalid GitHub handle: {exc}", file=sys.stderr)
            return 2
        except InvalidRepo as exc:
            print(f"invalid repository (expected owner/name): {exc}", file=sys.stderr)
            return 2
        except InvalidJiraUser as exc:
            print(f"invalid Jira username: {exc}", file=sys.stderr)
            return 2
        except GhError as exc:
            print(f"gh failed: {exc}", file=sys.stderr)
            return 1
        except JiraError as exc:
            print(f"jira failed: {exc}", file=sys.stderr)
            return 1
        payload: dict[str, Any] = {
            "login": args.login,
            "repo": args.repo,
            "since": since,
            "end": args.end,
            "caps_hit": caps,
            "notes": fetch_notes,
            "items": [i.to_json() for i in items],
        }
        if backends:
            payload["backends"] = backends
        text = json.dumps(payload, indent=2)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(text)
        Path(args.out).write_text(text)
        return 0

    data = _read(args.items)
    raw_weights = json.loads(Path(args.weights).read_text()) if args.weights else {}
    if not isinstance(raw_weights, dict):
        print("weights file must hold a JSON object of setting names to numbers", file=sys.stderr)
        return 2
    weights, notes = Weights.from_mapping(raw_weights)
    result = score(
        [Item.from_json(d) for d in data["items"]],
        _read(args.classes),
        weights,
        since=args.since or data["since"],
        end=data["end"],
        area_prefix=args.area_prefix,
        caps_hit=data.get("caps_hit", []),
        timeline_kinds=tuple(k.strip() for k in args.timeline_kinds.split(",") if k.strip())
        if args.timeline_kinds
        else None,
    )
    result["notes"] = notes + list(data.get("notes", [])) + result["notes"]
    Path(args.out).write_text(json.dumps(result, indent=2))
    return 0
