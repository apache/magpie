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
"""`pr-management code-review …` — discovered by the main CLI.

Every subcommand reads saved files and prints JSON. When a decision needs a
read that is not saved yet, the result lists it under `needs` as
`{op, params, save}`; the skill runs `vetted-op-read --save <save> <op>
<params…>` and repeats the command. Commands the agent runs to post are
printed `shlex.join`-built from validated values.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shlex
from pathlib import Path
from typing import Any

from .. import config, mentions, model
from ..triage import guards as triage_guards
from . import body as review_body
from . import codeowners, criteria, data, deps, disposition, reviewers, scans, selectors, session, slop
from . import diff as difflib

FAMILY = "code-review"
CODEOWNERS_OPS = ("cr-codeowners-github", "cr-codeowners-root", "cr-codeowners-docs")
_PR = re.compile(r"^[0-9]{1,10}$")


def _now(value: str | None) -> dt.datetime:
    if value:
        parsed = model.parse_time(value)
        if parsed is None:
            raise SystemExit(f"pr-management: --now {value!r} is not an ISO-8601 time")
        return parsed
    return dt.datetime.now(dt.UTC)


def _need(op: str, params: list[str], save: str, why: str) -> dict[str, Any]:
    return {"op": op, "params": params, "save": save, "why": why}


def _file(saved: Path, name: str) -> Path | None:
    path = saved / name
    return path if path.is_file() else None


def _codeowners(saved: Path) -> tuple[list[codeowners.Rule], str | None]:
    for op in CODEOWNERS_OPS:
        text = data.decode_content(_file(saved, f"{op}.json"))
        if text:
            return codeowners.parse(text), op
    return [], None


def _codeowners_needs(saved: Path) -> list[dict[str, Any]]:
    if any(_file(saved, f"{op}.json") for op in CODEOWNERS_OPS):
        return []
    return [
        _need(
            CODEOWNERS_OPS[0],
            [],
            f"{CODEOWNERS_OPS[0]}.json",
            "the ownership file (a 404 is fine: then try cr-codeowners-root, then cr-codeowners-docs)",
        )
    ]


def _viewer_teams(
    saved: Path, rules: list[codeowners.Rule], viewer: str, org: str | None
) -> tuple[set[str], list[dict[str, Any]]]:
    teams: set[str] = set()
    needs = []
    for team in codeowners.teams(rules):
        team_org, _, slug = team.partition("/")
        if org and team_org.lower() != org.lower():
            continue  # team-members reads only the upstream organisation
        members = data.load_lines(_file(saved, f"team-{slug}.txt"))
        if not members and not _file(saved, f"team-{slug}.txt"):
            needs.append(_need("team-members", [slug], f"team-{slug}.txt", f"is the viewer in @{team}?"))
        elif viewer.lower() in (m.lower() for m in members):
            teams.add(team.lower())
    return teams, needs


def _active_set(
    saved: Path, prs: list[data.PR], viewer: str, sel: selectors.Selector, base: str, now: dt.datetime
) -> tuple[set[str], list[dict[str, Any]]]:
    active = {f for pr in prs if pr.author.lower() == viewer.lower() for f in pr.files}
    if "touching-mine" not in sel.signals:
        return active, []
    commits = data.load_json(_file(saved, "viewer-commits.json"))
    since = (now - dt.timedelta(days=sel.since_days)).date().isoformat()
    if commits is None:
        return active, [
            _need(
                "cr-viewer-commits",
                [viewer, since, base],
                "viewer-commits.json",
                "touching-mine: the viewer's commits on the base branch",
            )
        ]
    needs = []
    pages = commits if isinstance(commits, list) and commits and isinstance(commits[0], list) else [commits]
    for page in pages:
        for commit in page or []:
            sha = str((commit or {}).get("sha") or "")
            if not sha:
                continue
            files = data.load_json(_file(saved, f"commit-files-{sha[:12]}.json"))
            if files is None:
                needs.append(
                    _need("cr-commit-files", [sha], f"commit-files-{sha[:12]}.json", "touching-mine")
                )
            else:
                active.update(files.get("files") or [])
    return active, needs


def _queue(args: argparse.Namespace, cfg: config.Config) -> dict[str, Any]:
    sel = selectors.parse(args.selector)
    saved: Path = args.saved_dir
    now = _now(args.now)
    sweep = _file(saved, "cr-open.json")
    if sweep is None:
        return {
            "selector": sel.as_dict(),
            "needs": [_need("gql-cr-open", [], "cr-open.json", "the open-PR sweep")],
        }
    prs = data.load_open(sweep)
    rules, source = _codeowners(saved)
    needs = _codeowners_needs(saved) if "codeowner" in sel.signals and sel.mode != "single-pr" else []
    org = (cfg.upstream_repo or "").split("/")[0] or None
    teams, team_needs = _viewer_teams(saved, rules, args.viewer, org)
    needs += team_needs
    active, active_needs = _active_set(saved, prs, args.viewer, sel, cfg.default_branch, now)
    needs += active_needs
    entries = selectors.queue(prs, sel, cfg, args.viewer, active, rules, teams, now)
    rows = []
    for entry in entries:
        pr = entry.pr
        rows.append(
            {
                "number": pr.number,
                "url": pr.url,
                "title": pr.title,
                "author": pr.author,
                "association": pr.association,
                "chips": entry.chips,
                "skip": entry.skip,
                "ask": entry.ask,
                "real_ci": entry.real_ci,
                "updated": pr.updated.isoformat() if pr.updated else None,
            }
        )
    announcements = []
    if "codeowner" in sel.signals and not rules and not needs:
        announcements.append(
            "No CODEOWNERS in the repository: the codeowner signal contributes nothing this session."
        )
    if "touching-mine" in sel.signals and not active and not active_needs:
        announcements.append(
            "The touching-mine active set is empty: that signal contributes nothing this session."
        )
    return {
        "selector": sel.as_dict(),
        "codeowners_source": source,
        "needs": needs,
        "queue": [r for r in rows if r["skip"] is None],
        "auto_skipped": [r for r in rows if r["skip"] is not None],
        "count": sum(1 for r in rows if r["skip"] is None),
        "empty_message": None
        if rows
        else f"No PRs match {' '.join(args.selector) or 'my reviews'}. Nothing to review.",
        "announcements": announcements,
        "docs": _queue_docs(sel, rows),
    }


def _queue_docs(sel: selectors.Selector, rows: list[dict[str, Any]]) -> list[str]:
    docs = []
    if sel.mode != "my-reviews":
        docs.append(f"classifications/selector-{sel.mode}.md")
    for row in rows:
        for reason in (row["skip"], row["ask"]):
            if reason and f"classifications/skip-{reason}.md" not in docs:
                docs.append(f"classifications/skip-{reason}.md")
    return docs


def _ci_line(pr: data.PR, real: bool) -> str:
    state = pr.rollup_state or "none reported"
    if state == "SUCCESS" and not real:
        return "CI: no real CI has run (bot checks only)"
    return f"CI: {state}"


def _merge_line(pr: data.PR) -> str:
    if pr.mergeable == "CONFLICTING" or pr.merge_state == "DIRTY":
        return "Merge: conflicts with the base"
    if pr.mergeable == "UNKNOWN":
        return "Merge: not yet computed (re-read once; never report it clean)"
    return f"Merge: {pr.merge_state or pr.mergeable}"


def _context(args: argparse.Namespace, cfg: config.Config) -> dict[str, Any]:
    saved: Path = args.saved_dir
    n = args.pr
    needs = []
    pr_path = _file(saved, f"cr-pr-{n}.json")
    diff_path = _file(saved, f"diff-{n}.patch")
    if pr_path is None:
        needs.append(_need("gql-cr-pr", [str(n)], f"cr-pr-{n}.json", "the PR in full"))
    if diff_path is None:
        needs.append(_need("pr-diff", [str(n)], f"diff-{n}.patch", "the unified diff"))
    if _file(saved, "cr-pr-template.json") is None:
        needs.append(_need("cr-pr-template", [], "cr-pr-template.json", "the PR template (a 404 means none)"))
    if _file(saved, f"stack-{n}.json") is None:
        needs.append(
            _need("gql-cr-pr-stack", [str(n)], f"stack-{n}.json", "stack membership (an error means none)")
        )
    if pr_path is None or diff_path is None:
        return {"pr": n, "needs": needs}
    pr = data.load_pr(pr_path)
    files = difflib.parse(diff_path.read_text(encoding="utf-8", errors="replace"))
    template = data.decode_content(_file(saved, "cr-pr-template.json"))
    real = selectors.real_ci(pr, cfg)
    crit = criteria.load(args.project_root, args.config_dir)
    stack = ((data.load_json(_file(saved, f"stack-{n}.json")) or {}).get("data") or {}).get(
        "repository"
    ) or {}
    stack = (stack.get("pullRequest") or {}).get("stack")
    added = [f.path for f in files if f.is_new]
    sources = crit.applies(list(pr.files))
    agents = scans.agents_files(list(pr.files), args.repo_root)
    sources += [a for a in agents if a not in sources]
    slop_result = slop.scan(pr, files, cfg, template)
    security = scans.security_disclosure(pr)
    ai = scans.ai_disclosure(pr.body, template)
    findings = (
        scans.compiled_artifacts(added, set(args.in_release or []))
        + scans.third_party_licences(files)
        + scans.licence_headers(files, [c.name for c in pr.contexts])
    )
    if ai["finding"]:
        findings.append(
            {
                "file": None,
                "severity": "minor",
                "finding_category": "AI-generated code signals",
                "reason": "AI-authorship signals present but the project's required disclosure is "
                "missing or unchecked",
                "signals": ai["signals"],
            }
        )
    headline = [
        f"PR #{pr.number} — {pr.title}",
        f"  {pr.url}",
        f"  Author: {pr.author} ({pr.association})",
        f"  Base:   {pr.base}  •  Head: {pr.head_sha[:8]}"
        + (f"  •  Stack: #{stack.get('number')} of {stack.get('size')}" if stack else ""),
        f"  {_ci_line(pr, real)}  •  Threads: {pr.unresolved_threads} unresolved  •  Reviews: {len(pr.reviews)}",
        f"  {_merge_line(pr)}",
        f"  Files:  {pr.changed_files} changed  +{pr.additions} \u2212{pr.deletions}",
        f"  Labels: {', '.join(pr.labels) or '—'}",
    ]
    docs = ["review-flow.md"]
    outcome = slop_result["outcome"]
    if outcome != "silent":
        docs.append(f"classifications/slop-{outcome}.md")
    if security["triggered"]:
        docs.append("classifications/security-disclosure.md")
    for f in findings:
        doc = f"criteria/{_doc_name(f.get('finding_category') or 'Quality signals to check')}.md"
        if doc not in docs:
            docs.append(doc)
    if scans.images(added):
        docs.append("criteria/image-ip.md")
    if crit.is_backport(pr.base):
        docs.append("classifications/backport.md")
    if stack:
        docs.append("classifications/stacked-layer.md")
    return {
        "pr": n,
        "head_sha": pr.head_sha,
        "node_id": pr.node_id,
        "needs": needs,
        "headline": "\n".join(headline),
        "files_tab": f"{pr.url}/files" if pr.url else None,
        "ci": {"state": pr.rollup_state, "real_ci": real},
        "mergeable": pr.mergeable,
        "merge_state": pr.merge_state,
        "stack": stack,
        "backport": crit.is_backport(pr.base),
        "sources_to_read": sources,
        "section_anchors": crit.anchors,
        "slop": slop_result,
        "security_disclosure": security,
        "ai_disclosure": ai,
        "images_to_judge": scans.images(added),
        "candidate_findings": findings,
        "docs": docs,
    }


def _doc_name(category: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", category.lower().split(" (")[0]).strip("-")


def _disposition(args: argparse.Namespace, cfg: config.Config) -> dict[str, Any]:
    pr = data.load_pr(args.saved_dir / f"cr-pr-{args.pr}.json")
    findings = json.loads(Path(args.findings).read_text(encoding="utf-8")) if args.findings else []
    saved_permission = data.load_lines(_file(args.saved_dir, "permission.txt"))
    permission = args.permission or (saved_permission[0] if saved_permission else None)
    permission = permission or (pr.viewer_permission or "").lower() or None
    result = disposition.pick(
        findings,
        ci_state=pr.rollup_state,
        real_ci=selectors.real_ci(pr, cfg),
        unresolved_threads=pr.unresolved_threads,
        other_changes_requested=disposition.other_changes_requested(list(pr.reviews), args.viewer, pr.author),
        unanswered_question=args.unanswered_question,
        ci_diff_caused=args.ci_diff_caused,
        mergeable=pr.mergeable,
        merge_state=pr.merge_state,
        permission=permission,
    )
    result["docs"] = [
        f"classifications/disposition-{result['disposition'].lower().replace('_', '-')}.md",
        f"classifications/footer-{result['footer']}.md",
    ]
    return result


def _reviewers(args: argparse.Namespace, cfg: config.Config) -> dict[str, Any]:
    saved: Path = args.saved_dir
    pr = data.load_pr(saved / f"cr-pr-{args.pr}.json")
    rules, _ = _codeowners(saved)
    needs = _codeowners_needs(saved)
    detail = sorted(
        pr.file_details, key=lambda f: -(int(f.get("additions") or 0) + int(f.get("deletions") or 0))
    )
    top = [str(f.get("path")) for f in detail[:3]] or list(pr.files[:3])
    path_commits = {}
    for path in top:
        if path.startswith("."):
            continue  # the path validator refuses a leading dot
        saved_commits = data.load_json(_file(saved, f"path-commits-{data.slug(path)}.json"))
        if saved_commits is None:
            needs.append(
                _need("cr-path-commits", [path], f"path-commits-{data.slug(path)}.json", "recent authors")
            )
        else:
            path_commits[path] = saved_commits
    prior: list[str] = []
    for path, commits in path_commits.items():
        for commit in commits[:2]:
            pulls = data.load_json(_file(saved, f"commit-pulls-{str(commit.get('sha'))[:12]}.json"))
            if pulls is None and args.prior_reviews:
                needs.append(
                    _need(
                        "cr-commit-pulls",
                        [str(commit.get("sha"))],
                        f"commit-pulls-{str(commit.get('sha'))[:12]}.json",
                        f"prior PRs on {path}",
                    )
                )
            for pull in pulls or []:
                number = str(pull.get("number"))
                if not _PR.match(number):
                    continue
                reviews = data.load_json(_file(saved, f"reviews-{number}.json"))
                if reviews is None:
                    needs.append(
                        _need("pr-reviews", [number], f"reviews-{number}.json", f"who reviewed #{number}")
                    )
                    continue
                prior += [
                    str((r.get("user") or {}).get("login"))
                    for r in reviews
                    if (r.get("user") or {}).get("login")
                ]
    exclude = {pr.author, args.viewer, *pr.requested_users, *(r.author for r in pr.reviews)}
    committers = set(data.load_lines(_file(saved, "committers.txt")))
    team_slug = cfg.committers_team_slug
    if team_slug:
        committers |= set(data.load_lines(_file(saved, f"team-{team_slug}.txt")))
    result = reviewers.suggest(
        paths=list(pr.files),
        rules=rules,
        path_commits=path_commits,
        prior_reviewers=prior,
        exclude=exclude,
        committers=committers,
        now=_now(args.now),
    )
    result["needs"] = needs
    return result


def _render(args: argparse.Namespace, cfg: config.Config) -> dict[str, Any]:
    saved: Path = args.saved_dir
    pr = data.load_pr(saved / f"cr-pr-{args.pr}.json")
    files = difflib.parse((saved / f"diff-{args.pr}.patch").read_text(encoding="utf-8", errors="replace"))
    findings = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    summary = Path(args.summary).read_text(encoding="utf-8").strip()
    anchored = [f for f in findings if f.get("line")]
    picked = review_body.pick(args.keep or "A", len(anchored)) if args.inline == "on" else {"keep": []}
    allow = mentions.allowed(cfg)
    inline = review_body.inline_comments(findings, picked["keep"], files, allow)
    kept = [k for k in picked["keep"] if k not in {u["index"] for u in inline["unanchorable"]}]
    variant = disposition.footer_variant(args.disposition, args.permission or pr.viewer_permission)
    project = cfg.project_name or (cfg.upstream_repo or "the project").split("/")[-1].capitalize()
    footer_text = review_body.footer(variant, project, cfg.contributing_docs_url)
    suggested = (
        json.loads(Path(args.reviewers).read_text(encoding="utf-8")).get("suggestions")
        if args.reviewers
        else []
    )
    conflict = None
    if pr.mergeable == "CONFLICTING" or pr.merge_state == "DIRTY":
        conflict = (
            f"The branch currently conflicts with `{pr.base}` and needs a rebase before this can merge."
        )
    elif pr.mergeable == "UNKNOWN":
        conflict = "GitHub has not yet computed whether this branch merges cleanly with its base."
    security_note = Path(args.security_note).read_text(encoding="utf-8") if args.security_note else None
    text = review_body.compose(
        allowed=allow,
        summary=summary,
        findings=findings,
        inline_kept=kept,
        footer_text=footer_text,
        reviewers=suggested,
        conflict_note=conflict,
        security_note=security_note,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    body_file = args.out_dir / f"review-body-{args.pr}.md"
    body_file.write_text(text + "\n", encoding="utf-8")
    hits = review_body.mention_scan(text + "\n" + "\n".join(t["body"] for t in inline["threads"]), allow)
    check = review_body.verify_footer(text, variant)
    flag = {"APPROVE": "--approve", "REQUEST_CHANGES": "--request-changes", "COMMENT": "--comment"}[
        args.disposition
    ]
    repo = cfg.upstream_repo or ""
    if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", repo) or not _PR.match(str(args.pr)):
        raise SystemExit("pr-management: the upstream repo or PR number is not valid for a command")
    payload_file = None
    if inline["threads"] and pr.node_id:
        payload_file = args.out_dir / f"review-payload-{args.pr}.json"
        payload_file.write_text(
            review_body.review_payload(pr.node_id, args.disposition, text, inline["threads"]),
            encoding="utf-8",
        )
        command = shlex.join(["gh", "api", "graphql", "--input", str(payload_file)])
    else:
        command = shlex.join(
            ["gh", "pr", "review", str(args.pr), "--repo", repo, flag, "--body-file", str(body_file)]
        )
    verify = shlex.join(["gh", "api", f"repos/{repo}/pulls/{args.pr}/reviews"])
    return {
        "pr": args.pr,
        "disposition": args.disposition,
        "footer": variant,
        "footer_verified": check["footer_present"],
        "body_file": str(body_file),
        "payload_file": str(payload_file) if payload_file else None,
        "inline_threads": len(inline["threads"]),
        "unanchorable": inline["unanchorable"],
        "live_mentions": hits,
        "post_command": command,
        "verify_command": verify,
        "verify_note": "Empty output from the post is success. Never re-run it: count the viewer's reviews instead.",
        "preview": text.splitlines()[:40],
        "docs": ["posting.md"],
    }


def _guard(args: argparse.Namespace) -> dict[str, Any]:
    liveness = _file(args.saved_dir, f"liveness-{args.pr}.json")
    if liveness is None:
        return {
            "pr": args.pr,
            "proceed": False,
            "needs": [
                _need("gql-pr-liveness", [str(args.pr)], f"liveness-{args.pr}.json", "the SHA recheck")
            ],
        }
    live = triage_guards.load_liveness(liveness)
    pr_path = _file(args.saved_dir, f"cr-pr-{args.pr}.json")
    author = data.load_pr(pr_path).author if pr_path else None
    if author and author.lower() == args.viewer.lower():
        return {"pr": args.pr, "proceed": False, "reason": "self-authored: GitHub refuses a self-review"}
    head = live.get("head_sha") or ""
    if head and not head.startswith(args.head) and not args.head.startswith(head):
        return {
            "pr": args.pr,
            "proceed": False,
            "reason": f"new commits since the draft ({args.head[:8]} → {head[:8]})",
            "choices": ["refresh", "post-anyway", "body-only-now", "skip"],
            "inline_positions_stale": True,
        }
    return {"pr": args.pr, "proceed": True}


def _slop_comment(args: argparse.Namespace, cfg: config.Config) -> dict[str, Any]:
    issues = [
        line.strip() for line in Path(args.issues).read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    project = cfg.project_name or (cfg.upstream_repo or "the project").split("/")[-1].capitalize()
    text = review_body.template("slop-warning").replace("<PROJECT>", project)
    text = text.replace("<issues>", "\n".join(i if i.startswith("- ") else f"- {i}" for i in issues))
    text = text.replace("<upstream_contributing_docs_url>", cfg.contributing_docs_url or "CONTRIBUTING.md")
    text = text.replace(
        "<footer>",
        review_body.footer(
            disposition.footer_variant("COMMENT", args.permission), project, cfg.contributing_docs_url
        ),
    )
    text = review_body.escape_handles(text, mentions.allowed(cfg))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"slop-warning-{args.pr}.md"
    path.write_text(text, encoding="utf-8")
    repo = cfg.upstream_repo or ""
    return {
        "body_file": str(path),
        "comment_command": shlex.join(
            ["gh", "pr", "comment", str(args.pr), "--repo", repo, "--body-file", str(path)]
        ),
        "close_commands": [
            shlex.join(["gh", "pr", "close", str(args.pr), "--repo", repo]),
            shlex.join(
                [
                    "gh",
                    "api",
                    "--method",
                    "PUT",
                    f"repos/{repo}/issues/{args.pr}/lock",
                    "--field",
                    "lock_reason=off-topic",
                ]
            ),
        ],
        "report_hint": f"Optional, only for genuine spam: {cfg.upstream_repo and f'https://github.com/{repo}/pull/{args.pr}'} "
        "→ … menu → Report content.",
        "preview": text.splitlines()[:30],
    }


def add_parsers(sub: Any) -> None:
    family = sub.add_parser(FAMILY, help="pr-management-code-review")
    commands = family.add_subparsers(dest="command", required=True)

    res = commands.add_parser("resolve", help="parse the selector arguments")
    res.add_argument("selector", nargs="*")

    que = commands.add_parser("queue", help="Step 1: the working list with match-reason chips")
    que.add_argument("--saved-dir", type=Path, required=True)
    que.add_argument("--viewer", required=True)
    que.add_argument("--now", default=None)
    que.add_argument("selector", nargs="*")

    ctx = commands.add_parser("context", help="Steps 1-4: headline, sources, slop, scans for one PR")
    ctx.add_argument("--saved-dir", type=Path, required=True)
    ctx.add_argument("--pr", type=int, required=True)
    ctx.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="the local checkout, for AGENTS.md discovery"
    )
    ctx.add_argument(
        "--in-release", nargs="*", default=[], help="added artifacts the agent confirmed ship in a release"
    )

    slo = commands.add_parser("slop-outcome", help="the threshold table over the confirmed signals")
    slo.add_argument("--fired", default="", help="comma-separated signal ids, e.g. H1,H3,S2")

    dep = commands.add_parser("deps", help="classify a dependency constraint ledger")
    dep.add_argument("--ledger", type=Path, required=True)

    dis = commands.add_parser("disposition", help="Step 6: the auto-pick and the footer variant")
    dis.add_argument("--saved-dir", type=Path, required=True)
    dis.add_argument("--pr", type=int, required=True)
    dis.add_argument("--viewer", required=True)
    dis.add_argument("--findings", default=None, help="the findings JSON (Step 4 shape)")
    dis.add_argument("--permission", default=None)
    dis.add_argument("--unanswered-question", action="store_true")
    dis.add_argument("--ci-diff-caused", action="store_true")

    rev = commands.add_parser("reviewers", help="Step 4.5: grounded reviewer suggestions")
    rev.add_argument("--saved-dir", type=Path, required=True)
    rev.add_argument("--pr", type=int, required=True)
    rev.add_argument("--viewer", required=True)
    rev.add_argument(
        "--prior-reviews", action="store_true", help="also ask for reviewers of prior merged PRs"
    )
    rev.add_argument("--now", default=None)

    ren = commands.add_parser("render", help="Steps 7a-7b: the body, the inline threads, the post command")
    mentions.add_flag(ren)
    ren.add_argument("--saved-dir", type=Path, required=True)
    ren.add_argument("--pr", type=int, required=True)
    ren.add_argument("--findings", required=True)
    ren.add_argument("--summary", required=True, help="a file holding the one-sentence summary line")
    ren.add_argument("--disposition", choices=("APPROVE", "REQUEST_CHANGES", "COMMENT"), required=True)
    ren.add_argument("--out-dir", type=Path, required=True)
    ren.add_argument("--keep", default=None, help="the inline picker's answer (A, N, 1,3, -2)")
    ren.add_argument("--inline", choices=("on", "off"), default="on")
    ren.add_argument("--reviewers", default=None, help="the reviewers command's output")
    ren.add_argument("--security-note", default=None)
    ren.add_argument("--permission", default=None)

    pic = commands.add_parser("pick", help="read the inline picker's answer")
    pic.add_argument("--spec", required=True)
    pic.add_argument("--count", type=int, required=True)

    men = commands.add_parser("mention-scan", help="live @-mentions outside code")
    mentions.add_flag(men)
    men.add_argument("--body", type=Path, required=True)

    ver = commands.add_parser("verify-footer", help="Golden rule 5: the verbatim footer is present")
    ver.add_argument("--body", type=Path, required=True)
    ver.add_argument("--variant", default=None)

    grd = commands.add_parser("guard", help="Step 8: SHA recheck and self-review guard")
    grd.add_argument("--saved-dir", type=Path, required=True)
    grd.add_argument("--pr", type=int, required=True)
    grd.add_argument("--head", required=True)
    grd.add_argument("--viewer", required=True)

    slc = commands.add_parser("slop-comment", help="the [C] warning body and the [X] close commands")
    mentions.add_flag(slc)
    slc.add_argument("--pr", type=int, required=True)
    slc.add_argument("--issues", required=True, help="one plain-English issue per line")
    slc.add_argument("--out-dir", type=Path, required=True)
    slc.add_argument("--permission", default=None)

    ses = commands.add_parser("session", help="the session ledger and the Step 3 summary")
    ses_sub = ses.add_subparsers(dest="session_command", required=True)
    rec = ses_sub.add_parser("record")
    rec.add_argument("--session", type=Path, required=True)
    rec.add_argument("--pr", type=int, required=True)
    rec.add_argument("--outcome", required=True, choices=session.OUTCOMES)
    rec.add_argument("--reason", default=None)
    rec.add_argument("--adversarial", choices=("yes", "no"), default=None)
    rec.add_argument("--calls", type=int, default=session.CALLS_PER_PR)
    rec.add_argument("--now", default=None)
    summ = ses_sub.add_parser("summary")
    summ.add_argument("--session", type=Path, required=True)
    summ.add_argument("--untouched", type=int, default=0)
    summ.add_argument("--now", default=None)


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    cfg = mentions.apply_flag(config.load(args.project_root, args.config_dir), args)
    command = args.command
    if command == "resolve":
        try:
            return {"selector": selectors.parse(args.selector).as_dict()}
        except selectors.SelectorError as exc:
            return {"error": str(exc)}
    if command == "queue":
        try:
            return _queue(args, cfg)
        except selectors.SelectorError as exc:
            return {"error": str(exc)}
    if command == "context":
        return _context(args, cfg)
    if command == "slop-outcome":
        fired = [f.strip() for f in args.fired.split(",") if f.strip()]
        return {
            "fired": fired,
            "outcome": slop.outcome(fired),
            "docs": [f"classifications/slop-{slop.outcome(fired)}.md"]
            if slop.outcome(fired) != "silent"
            else [],
        }
    if command == "deps":
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        ledgers = ledger if isinstance(ledger, list) else [ledger]
        return {"packages": [deps.classify(item) for item in ledgers]}
    if command == "disposition":
        return _disposition(args, cfg)
    if command == "reviewers":
        return _reviewers(args, cfg)
    if command == "render":
        return _render(args, cfg)
    if command == "pick":
        return review_body.pick(args.spec, args.count)
    if command == "mention-scan":
        hits = review_body.mention_scan(args.body.read_text(encoding="utf-8"), mentions.allowed(cfg))
        return {"live_handles": [h["handle"] for h in hits], "prompt_shown": bool(hits), "hits": hits}
    if command == "verify-footer":
        return review_body.verify_footer(args.body.read_text(encoding="utf-8"), args.variant)
    if command == "guard":
        return _guard(args)
    if command == "slop-comment":
        return _slop_comment(args, cfg)
    now = _now(getattr(args, "now", None))
    if args.session_command == "record":
        adversarial = None if args.adversarial is None else args.adversarial == "yes"
        return session.record(
            args.session,
            pr=args.pr,
            outcome=args.outcome,
            reason=args.reason,
            adversarial=adversarial,
            calls=args.calls,
            now=now,
        )
    return session.summary(args.session, untouched=args.untouched, now=now)
