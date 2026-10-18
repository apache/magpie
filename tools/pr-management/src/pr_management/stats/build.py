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
"""`pr-management stats build` — the whole pr-management-stats dashboard, as code.

Reads the files `vetted-op-read --save` wrote (or, with `fetch_with_gh`,
fetches through `gh` directly, for CI), classifies every PR, computes every
panel and writes the HTML (or Markdown) dashboard. A missing read comes back
under `needs`; the skill saves it and builds again.

Saved file names, under the vetted-ops workspace's `saved/`:

* `stats-open.json` — `gql-pr-stats-open` (every page).
* `stats-closed-page-<k>.json` — `gql-pr-stats-closed-page <cursor>`, pages
  1, 2, …: the default closed path. Built page by page until a page's oldest
  `updatedAt` predates the cutoff.
* `stats-closed-search.json` — `gql-pr-stats-closed-search <date>`: the
  `fast-closed` opt-in.
* `team-members.txt` — `team-members <slug>`: optional, sharpens maintainer
  detection in the triager-activity and ready-split panels.

CODEOWNERS is read from the adopter checkout (`.github/CODEOWNERS`,
`CODEOWNERS`, `docs/CODEOWNERS`, first match wins).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shlex
from pathlib import Path
from typing import Any

from .. import config, people
from ..layers import personal_dir
from . import dashboard, reference

CLOSED_PAGE = "stats-closed-page-{k}.json"
OPEN_FILE = "stats-open.json"
FAST_CLOSED_FILE = "stats-closed-search.json"
TEAM_FILE = "team-members.txt"
SEARCH_CAP = 1000
CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
SESSION_STATE_FILE = "session-state.json"


def _load(path: Path) -> Any:
    # GitHub bodies routinely carry raw control characters (the stats spec).
    return json.loads(path.read_text(encoding="utf-8"), strict=False)


def _search_pages(document: Any) -> tuple[list[dict[str, Any]], int | None]:
    pages = document if isinstance(document, list) else [document]
    nodes: list[dict[str, Any]] = []
    count = None
    for page in pages:
        search = ((page or {}).get("data") or {}).get("search") or {}
        nodes += [n for n in search.get("nodes") or [] if n and "number" in n]
        if search.get("issueCount") is not None:
            count = int(search["issueCount"])
    return nodes, count


def _closed_pages(saved: Path, cutoff: dt.datetime) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """The default closed path: every saved page, and the next page to save if one is due."""
    nodes: list[dict[str, Any]] = []
    k = 1
    last: dict[str, Any] | None = None
    while (saved / CLOSED_PAGE.format(k=k)).is_file():
        data = _load(saved / CLOSED_PAGE.format(k=k))
        conn = (((data.get("data") or {}).get("repository") or {}).get("pullRequests")) or {}
        nodes += [n for n in conn.get("nodes") or [] if n]
        last = conn
        k += 1
    if last is None:
        return nodes, {"op": "gql-pr-stats-closed-page", "params": ["start"], "save": CLOSED_PAGE.format(k=1)}
    page_nodes = last.get("nodes") or []
    updated = [reference.parse_iso(n.get("updatedAt")) for n in page_nodes if n and n.get("updatedAt")]
    oldest = min((u for u in updated if u), default=None)
    info = last.get("pageInfo") or {}
    if info.get("hasNextPage") and oldest is not None and oldest >= cutoff:
        return nodes, {
            "op": "gql-pr-stats-closed-page",
            "params": [info.get("endCursor")],
            "save": CLOSED_PAGE.format(k=k),
        }
    return nodes, None


def _codeowners(project_root: Path) -> str:
    for rel in CODEOWNERS_PATHS:
        path = project_root / rel
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return ""


def _files(open_prs: list[dict[str, Any]]) -> dict[int, list[str]]:
    return {
        pr["number"]: [f["path"] for f in (pr.get("files") or {}).get("nodes") or [] if f]
        for pr in open_prs
        if pr.get("_has_ready") and pr.get("files")
    }


def _cap_note(closed: list[dict[str, Any]], count: int | None, weeks: list[Any]) -> str | None:
    """the stats spec: a capped closed series must say which weeks it truncated."""
    if len(closed) < SEARCH_CAP and (count is None or count <= len(closed)):
        return None
    closed_at = [reference.parse_iso(n.get("closedAt")) for n in closed if n.get("closedAt")]
    floor = min((c for c in closed_at if c), default=None)
    truncated = [s.date().isoformat() for s, _ in weeks if floor is None or s < floor]
    authoritative = [s.date().isoformat() for s, _ in weeks if floor is not None and s >= floor]
    return (
        f"Search cap: the closed/merged series hit GitHub's {SEARCH_CAP}-result limit "
        f"({count if count is not None else len(closed)} matched). Weeks starting "
        f"{', '.join(truncated) or '—'} are cap-truncated; authoritative weeks: "
        f"{', '.join(authoritative) or '—'}. Run without fast-closed for full counts."
    )


#: A gist id: hex, as GitHub issues them. Anything else is refused, because the
#: id is spliced into a command the agent runs.
GIST_ID = re.compile(r"^[0-9a-f]{5,40}$")
#: `owner/name`, conservative on both halves.
REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")


def _state_path(project_root: Path) -> Path | None:
    home = personal_dir(project_root)
    return home / SESSION_STATE_FILE if home is not None else None


def publish(project_root: Path, html: Path, repo: str) -> dict[str, Any]:
    """The gist the dashboard goes to, and the exact command that puts it there.

    The tool never writes to GitHub: the skill proposes the command and runs
    it on confirmation. The stable gist id lives in the personal layer's
    session-state (`stats_gist_id`); `record-gist` stores a new one.
    """
    state_path = _state_path(project_root)
    gist_id = None
    if state_path is not None and state_path.is_file():
        try:
            gist_id = json.loads(state_path.read_text(encoding="utf-8")).get("stats_gist_id")
        except (OSError, json.JSONDecodeError):
            gist_id = None
    warnings: list[str] = []
    if gist_id is not None and not (isinstance(gist_id, str) and GIST_ID.match(gist_id)):
        # The session state is a file the agent can write; never let its
        # contents reach a command line.
        warnings.append(f"ignored stats_gist_id {gist_id!r} in {state_path}: not a gist id")
        gist_id = None
    if not REPO.match(repo):
        raise ValueError(f"repository {repo!r} is not an owner/name slug")
    payload = None
    if gist_id:
        # Update in place, so the preview URL stays stable across runs.
        payload = html.with_suffix(".gist-payload.json")
        payload.write_text(
            json.dumps({"files": {html.name: {"content": html.read_text(encoding="utf-8")}}}),
            encoding="utf-8",
        )
        command = shlex.join(["gh", "api", "-X", "PATCH", f"gists/{gist_id}", "--input", str(payload)])
    else:
        command = shlex.join(
            [
                "gh",
                "gist",
                "create",
                str(html),
                "--desc",
                f"{repo} — PR Backlog Dashboard ({dt.date.today()})",
            ]
        )
    return {
        "gist_id": gist_id,
        "command": command,
        "payload": str(payload) if payload else None,
        "after_create": None
        if gist_id
        else "uv run --project <framework>/tools/pr-management pr-management stats record-gist <id from the gist URL>",
        "preview_url": f"https://gistpreview.github.io/?{gist_id}" if gist_id else None,
        "state_file": str(state_path) if state_path else None,
        "warnings": warnings,
    }


def record_gist(project_root: Path, gist_id: str) -> dict[str, Any]:
    """Store a newly created gist's id so later runs edit it in place."""
    state_path = _state_path(project_root)
    if state_path is None:
        return {"stored": False, "reason": "no personal config layer (not a git repository)"}
    data: dict[str, Any] = {}
    if state_path.is_file():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    if not GIST_ID.match(gist_id):
        return {"stored": False, "reason": f"{gist_id!r} is not a gist id (hex, from the gist URL)"}
    data["stats_gist_id"] = gist_id
    state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"stored": True, "state_file": str(state_path), "gist_id": gist_id}


def build(
    *,
    project_root: Path,
    config_dir: Path | None,
    saved: Path | None,
    viewer: str,
    out: Path,
    since: str | None,
    fast_closed: bool = False,
    fetch_with_gh: bool = False,
    repo: str | None = None,
    fmt: str = "html",
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    cfg = config.load(project_root, config_dir)
    repo = repo or cfg.upstream_repo or ""
    now = now or dt.datetime.now(dt.UTC)
    weeks = 6
    cutoff = (
        dt.datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=dt.UTC)
        if since
        else now - dt.timedelta(weeks=weeks)
    )
    ctx: dict[str, Any] = {
        "now": now,
        "cutoff": cutoff,
        "weeks": reference.weeks_buckets(now, weeks),
        "triage_marker": cfg.marker,
        "ai_footer": reference.DEFAULT_AI_FOOTER,
        "ready_label": cfg.ready_label,
        "area_prefix": cfg.area_label_prefix or "",
        "repo": repo,
        "viewer": viewer,
    }
    warnings = list(cfg.warnings)
    needs: list[dict[str, Any]] = []
    partial = False
    closed_count: int | None = None

    if fetch_with_gh:
        if not repo:
            raise SystemExit("pr-management: --fetch-with-gh needs --repo or upstream_repo in project.md")
        status: dict[str, bool] = {"partial": False}
        open_prs = reference.paginated_search(
            reference.OPEN_PRS_QUERY, f"is:pr is:open repo:{repo}", page_size=30, status=status
        )
        closed_prs = reference.paginated_search(
            reference.CLOSED_PRS_QUERY,
            f"is:pr is:closed repo:{repo} closed:>={cutoff.date()}",
            page_size=50,
            max_pages=20,
            status=status,
        )
        partial = status["partial"]
        fast_closed = True
        codeowners = reference.fetch_codeowners(repo)
    else:
        if saved is None:
            raise SystemExit("pr-management: pass --saved-dir (or --fetch-with-gh for CI)")
        open_file = saved / OPEN_FILE
        if not open_file.is_file():
            needs.append({"op": "gql-pr-stats-open", "params": [], "save": OPEN_FILE})
            open_prs = []
        else:
            open_prs, open_count = _search_pages(_load(open_file))
            if open_count is not None and open_count > len(open_prs):
                partial = True
                warnings.append(f"open sweep returned {len(open_prs)} of {open_count} PRs (search cap)")
        if fast_closed:
            fast = saved / FAST_CLOSED_FILE
            if fast.is_file():
                closed_prs, closed_count = _search_pages(_load(fast))
            else:
                closed_prs = []
                needs.append(
                    {
                        "op": "gql-pr-stats-closed-search",
                        "params": [cutoff.date().isoformat()],
                        "save": FAST_CLOSED_FILE,
                    }
                )
        else:
            closed_prs, nxt = _closed_pages(saved, cutoff)
            if nxt is not None:
                needs.append(nxt)
            closed_prs = [
                n
                for n in closed_prs
                if (c := reference.parse_iso(n.get("closedAt"))) is not None and c >= cutoff
            ]
        codeowners = _codeowners(project_root)
        team = saved / TEAM_FILE
        if team.is_file():
            ctx["maintainers"] = people.Maintainers(team=people.load_team(team))

    if needs:
        return {"needs": needs, "warnings": warnings}

    for pr in open_prs:
        reference.classify(pr, ctx)
    for pr in closed_prs:
        reference.classify(pr, ctx, partial=True)
    files = (
        reference.fetch_ready_pr_files(repo, [p["number"] for p in open_prs if p["_has_ready"]])
        if (fetch_with_gh and codeowners)
        else _files(open_prs)
    )
    cap = _cap_note(closed_prs, closed_count, ctx["weeks"]) if fast_closed else None
    built = dashboard.assemble(
        ctx, open_prs, closed_prs, codeowners, files, partial=partial, cap_note=cap, fast_closed=fast_closed
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "markdown":
        out.write_text(render_markdown(built, ctx), encoding="utf-8")
    else:
        out.write_text(built["html"], encoding="utf-8")
    out.with_suffix(".json").write_text(
        json.dumps(built["intermediates"], indent=2, default=str), encoding="utf-8"
    )
    hero = built["hero"]
    return {
        "out": str(out),
        "format": fmt,
        "summary": {
            "health": built["health"][0],
            "open": hero["open_total"],
            "contributor_non_draft": hero["contrib_nondraft_total"],
            "untriaged": hero["untriaged"],
            "untriaged_over_4_weeks": hero["untriaged_4w"],
            "triaged": hero["qc_triaged"],
            "responded": hero["responded"],
            "ready": hero["ready"],
            "recommendations": [f"{r['title']} — {r['action']}" for r in built["recs"][:5]],
            "line": _summary_line(hero, built["recent_drafts"]),
        },
        "partial": partial,
        "cap_note": cap,
        "warnings": warnings,
        "publish": publish(project_root, out, repo) if fmt == "html" else None,
    }


def _summary_line(hero: dict[str, Any], recent_drafts: int) -> str:
    """the stats spec § End-of-output summary — one stable plain-text line."""
    triaged = hero["qc_triaged"]
    return (
        f"Summary: {hero['open_total']} open · {triaged} triaged "
        f"({dashboard.pct(triaged, hero['contrib_nondraft_total'])}%) · {hero['responded']} responded "
        f"({dashboard.pct(hero['responded'], triaged)}% of triaged) · {hero['ready']} ready for review · "
        f"{recent_drafts} drafted by triager in last 7d."
    )


def render_markdown(built: dict[str, Any], ctx: dict[str, Any]) -> str:
    """the stats spec § Markdown fallback — the same logical sections, flat GFM."""
    hero, (rating, _) = built["hero"], built["health"]
    lines = [
        f"# {ctx['repo']} — Maintainer dashboard",
        "",
        f"{ctx['now'].strftime('%A, %B %d, %Y · %H:%M UTC')} · viewer @{ctx['viewer']} · "
        f"6-week window since {ctx['cutoff'].date()}",
        "",
    ]
    if built["intermediates"].get("cap_note"):
        lines += [f"> ⚠ {built['intermediates']['cap_note']}", ""]
    if built["intermediates"].get("partial"):
        lines += ["> ⚠ INCOMPLETE DATA — one or more pages failed to fetch.", ""]
    lines += [
        "| Health | Open | Untriaged (>4w) | Ready |",
        "|---|---|---|---|",
        f"| {rating} | {hero['open_total']} | {hero['untriaged']} ({hero['untriaged_4w']}) | {hero['ready']} |",
        "",
        "## What needs attention",
        "",
    ]
    lines += [f"- {r['icon']} **{r['title']}** — {r['detail']} `{r['action']}`" for r in built["recs"]] or [
        "- Nothing."
    ]
    lines += ["", "## Closure velocity", ""]
    for w in built["weekly"]:
        total = w["merged"] + w["closed_not_merged"]
        lines.append(f"- {w['start'].date()}: {w['merged']}✓ / {w['closed_not_merged']}✗ (total {total})")
    lines += ["", "## Opened vs closed", ""]
    for b in built["opened_vs_closed"]:
        lines.append(
            f"- {b['start'].date()}: opened {b['opened']} / closed {b['closed']} (net {b['net']:+d})"
        )
    lines += ["", "## Pressure by area", "", "| Area | Score | Contrib. PRs | Ready |", "|---|---|---|---|"]
    lines += [f"| {a} | {v['score']} | {v['contribs']} | {v['ready']} |" for a, v in built["pressure"]]
    f = built["funnel"]
    lines += [
        "",
        "## Triage funnel",
        "",
        "| Ready | Responded | Waiting for author | Not yet triaged |",
        "|---|---|---|---|",
        f"| {f['ready']} | {f['responded']} | {f['waiting_manual'] + f['waiting_ai']} | {f['untriaged']} |",
        "",
        f"## Triaged PRs — final state since {ctx['cutoff'].date()}",
        "",
        "| Area | Triaged | Closed | Merged | Responded |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['area']} | {r['triaged_total']} | {r['closed']} | {r['merged']} | {r['responded']} |"
        for r in built["table_final"]
    ]
    lines += [
        "",
        "## Triaged PRs — still open",
        "",
        "| Area | Total | Contrib. | Triaged | Responded | Ready | Drafted by triager |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['area']} | {r['total']} | {r['contribs']} | {r['triaged']} | {r['responded']} | {r['ready']} | "
        f"{r['drafted_by_triager']} |"
        for r in built["table_open"]
    ]
    lines += [
        "",
        "## Legend",
        "",
        "- **Contrib.** — non-collaborator-authored PRs.",
        "- **Triaged** — a triage marker: a maintainer comment with the quality-criteria link, or the folded triage note.",
        "- **Responded** — the author commented or pushed after the triage marker.",
        "- **Ready** — PRs carrying the ready-for-review label.",
        "- **Drafted by triager** — drafts that also carry a triage marker.",
        "",
        _summary_line(hero, built["recent_drafts"]),
        "",
    ]
    return "\n".join(lines)
