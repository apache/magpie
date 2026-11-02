#!/usr/bin/env python3
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

"""
Fetch + classify primitives of the pr-management-stats dashboard.

`pr-management stats build` (stats/build.py) is the entry point: it feeds
these predicates the files `vetted-op-read --save` wrote, or, with
`--fetch-with-gh`, the gh fetch below; `dashboard.assemble` renders every
panel. The `main()` here remains a fetch-and-classify sidecar for CI.

Every panel definition (is_engaged, is_triaged, is_untriaged, the pressure
weight, the health rating, the recommendation rules) lives in this package;
the skill's panels.md explains them to a maintainer.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .. import markers, people

# --------------------------------------------------------------------------
# Constants (project-overridable via --config)
# --------------------------------------------------------------------------

# Example default values for the reference instance these scripts were built
# against. They are NOT vendor-neutral, and that is fine here: per RFC-AI-0004
# every project-specific value is a CLI override (the --triage-marker /
# --ai-footer / --ready-label / --area-prefix flags below), so an adopter for
# another project supplies their own without editing this file. The framework's
# placeholder convention governs repo slugs / URLs in prose, not these runtime
# config defaults.
DEFAULT_TRIAGE_MARKER = "Pull Request quality criteria"
DEFAULT_AI_FOOTER = "AI-assisted triage tool"
DEFAULT_READY_LABEL = "ready for maintainer review"
DEFAULT_AREA_PREFIX = "area:"
COLLAB_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}

# stderr markers that indicate a transient (retryable) gh/GraphQL failure.
_TRANSIENT_MARKERS = ("502", "503", "504", "rate limit", "timeout", "timed out", "abuse")


def parse_iso(t):
    if not t:
        return None
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def is_bot(login):
    """The shared bot rule (`people.is_bot`), plus Copilot and a missing login.

    A Copilot review is automation, not engagement, so the dashboard counts it
    as a bot; a ghost (deleted) account carries no login at all.
    """
    if not login:
        return True
    return people.is_bot(login) or people.is_copilot(login)


def is_maintainer(ctx, login, association):
    """The shared maintainer rule (`people.Maintainers`) when the run loaded a
    committers-team roster or permission reads into ``ctx["maintainers"]``;
    otherwise the association first filter, as the roster-less shared rule
    decides an unknown collaborator."""
    roster = ctx.get("maintainers")
    if roster is None:
        return association in COLLAB_ASSOCIATIONS
    return roster.is_maintainer(login or "", association or "NONE")


# Backport / release-branch PR titles, e.g. "[v3-1-test] ..." or "[2-10-stable] ...".
# These are release-branch housekeeping, not contributor triage; they are
# excluded from the drafts-&-closes attribution panel (see the stats spec
# § Drafts & closes attribution by person).
BACKPORT_TITLE_RE = re.compile(r"^\s*\[.*(test|stable)\]", re.IGNORECASE)


def is_backport(pr):
    """True if a PR targets a non-main branch or carries a backport title.

    A PR is a backport when its base branch is not ``main`` (``baseRefName`` is
    present and != "main") OR its title matches the ``[v*-test]`` / ``[*-stable]``
    pattern. A missing ``baseRefName`` is treated as non-backport (we cannot
    prove otherwise from the fetched data, so default to including the PR).
    """
    base = pr.get("baseRefName")
    if base and base != "main":
        return True
    title = pr.get("title") or ""
    return bool(BACKPORT_TITLE_RE.match(title))


# --------------------------------------------------------------------------
# GraphQL templates — keep parity with tools/vetted-ops queries/pr-stats-*.graphql
# --------------------------------------------------------------------------

OPEN_PRS_QUERY = """
query($q: String!, $first: Int!, $after: String) {
  search(query: $q, type: ISSUE, first: $first, after: $after) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title isDraft createdAt updatedAt body
        author { login __typename } authorAssociation
        baseRefName reviewDecision
        labels(first: 20) { nodes { name } }
        commits(last: 1) { nodes { commit { oid committedDate } } }
        comments(last: 25) {
          nodes { author { login __typename } authorAssociation createdAt body }
        }
        latestReviews(last: 10) {
          nodes { author { login } state submittedAt }
        }
        reviewThreads(first: 30) {
          nodes {
            isResolved
            comments(first: 3) {
              nodes { author { login } authorAssociation createdAt body }
            }
          }
        }
        timelineItems(last: 50, itemTypes: [LABELED_EVENT, READY_FOR_REVIEW_EVENT, CONVERT_TO_DRAFT_EVENT]) {
          nodes {
            __typename
            ... on LabeledEvent { createdAt actor { login } label { name } }
            ... on ReadyForReviewEvent { createdAt actor { login } }
            ... on ConvertToDraftEvent { createdAt actor { login } }
          }
        }
      }
    }
  }
  rateLimit { remaining cost }
}
"""

CLOSED_PRS_QUERY = """
query($q: String!, $first: Int!, $after: String) {
  search(query: $q, type: ISSUE, first: $first, after: $after) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title isDraft createdAt closedAt mergedAt merged state body
        author { login __typename } authorAssociation
        baseRefName
        labels(first: 20) { nodes { name } }
        comments(last: 25) {
          nodes { author { login __typename } authorAssociation createdAt body }
        }
        timelineItems(itemTypes: [CLOSED_EVENT], last: 1) {
          nodes { ... on ClosedEvent { actor { login } } }
        }
      }
    }
  }
  rateLimit { remaining cost }
}
"""


def run_gh(*args, **kwargs):
    return subprocess.run(["gh", *args], capture_output=True, text=True, **kwargs)


def _is_rate_limited(errors):
    """True if a GraphQL errors[] payload reports RATE_LIMITED."""
    return any(isinstance(e, dict) and e.get("type") == "RATE_LIMITED" for e in errors or [])


def _run_graphql_page(cmd, page, max_retries, backoff):
    """Run one gh GraphQL page, retrying transient (5xx / rate-limit) failures.

    Returns the parsed response dict, or None on a permanent failure (caller
    should treat None as "pagination cut short"). Backoff uses ``time.sleep``
    looked up at call time so tests can patch it.
    """
    for attempt in range(max_retries + 1):
        r = subprocess.run(cmd, capture_output=True, text=True)
        retries_left = attempt < max_retries
        if r.returncode != 0:
            transient = any(m in r.stderr.lower() for m in _TRANSIENT_MARKERS)
            if transient and retries_left:
                print(f"  page {page}: transient error, retry {attempt + 1}/{max_retries}", file=sys.stderr)
                time.sleep(backoff * (attempt + 1))
                continue
            print(f"  page {page}: error {r.stderr[:200]}", file=sys.stderr)
            return None
        try:
            d = json.loads(r.stdout)
        except json.JSONDecodeError:
            if retries_left:
                time.sleep(backoff * (attempt + 1))
                continue
            print(f"  page {page}: invalid JSON response", file=sys.stderr)
            return None
        if "errors" in d:
            if _is_rate_limited(d["errors"]) and retries_left:
                print(f"  page {page}: RATE_LIMITED, retry {attempt + 1}/{max_retries}", file=sys.stderr)
                time.sleep(backoff * (attempt + 1))
                continue
            print(f"  page {page}: errors {d['errors'][:1]}", file=sys.stderr)
            return None
        return d
    return None


def paginated_search(query, search_q, page_size=30, max_pages=40, *, max_retries=1, backoff=2.0, status=None):
    """Run a paginated GraphQL search query, return all nodes.

    Retries transient (5xx / RATE_LIMITED) failures up to ``max_retries`` times
    with linear backoff. If ``status`` is a dict, sets ``status["partial"] =
    True`` when pagination was cut short — an error, or ``max_pages`` reached
    while more pages remained — so callers can flag incomplete output rather
    than silently publish a truncated result.
    """
    all_nodes = []
    cursor = None
    partial = False
    for page in range(1, max_pages + 1):
        cmd = [
            "gh",
            "api",
            "graphql",
            "-F",
            f"first={page_size}",
            "-F",
            f"q={search_q}",
            "-F",
            f"query={query}",
        ]
        if cursor:
            cmd.extend(["-F", f"after={cursor}"])
        d = _run_graphql_page(cmd, page, max_retries, backoff)
        if d is None:
            partial = True
            break
        nodes = d["data"]["search"]["nodes"]
        all_nodes.extend(nodes)
        pi = d["data"]["search"]["pageInfo"]
        print(f"  page {page}: +{len(nodes)} (total {len(all_nodes)})", file=sys.stderr)
        if not pi["hasNextPage"]:
            break
        cursor = pi["endCursor"]
    else:
        # Loop ran the full max_pages without the hasNextPage=False break —
        # there were (or may have been) more pages we never fetched.
        partial = True
    if status is not None:
        status["partial"] = status.get("partial", False) or partial
    return all_nodes


def fetch_ready_pr_files(repo, ready_pr_numbers):
    """Aliased GraphQL: 20 PRs per call, fetch files(first:100) per PR."""
    owner, name = repo.split("/")
    out = {}
    for batch_start in range(0, len(ready_pr_numbers), 20):
        batch = ready_pr_numbers[batch_start : batch_start + 20]
        aliases = [
            f"pr{i}: pullRequest(number: {n}) {{ number files(first: 100) {{ nodes {{ path }} }} }}"
            for i, n in enumerate(batch)
        ]
        q = (
            f'query {{ repository(owner:"{owner}",name:"{name}") {{ '
            + " ".join(aliases)
            + " } rateLimit { remaining cost } }"
        )
        r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}"], capture_output=True, text=True)
        if r.returncode != 0:
            continue
        d = json.loads(r.stdout)
        if "errors" in d:
            continue
        for pr in d["data"]["repository"].values():
            if pr and "number" in pr:
                out[pr["number"]] = [f["path"] for f in pr["files"]["nodes"]]
    return out


def fetch_codeowners(repo):
    """Try .github/CODEOWNERS, CODEOWNERS, docs/CODEOWNERS."""
    owner, name = repo.split("/")
    for path in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        r = run_gh("api", f"repos/{owner}/{name}/contents/{path}", "--jq", ".content")
        if r.returncode == 0 and r.stdout.strip():
            import base64

            try:
                return base64.b64decode(r.stdout.strip().replace("\n", "")).decode()
            except Exception:
                continue
    return ""


# --------------------------------------------------------------------------
# Classification — see the stats spec
# --------------------------------------------------------------------------


def fold_triaged_at(pr):
    """Timestamp of the pr-body fold triage note, or None.

    The default ``pr-body`` feedback channel folds the triage note into the PR
    *description* as a ``pr-triage-fold`` block. Parsed by the shared
    ``markers.parse_fold`` (untrusted, author-controlled text: an unparsable
    or zone-less ``triaged=`` is no timestamp, and a malformed marker above
    the real block cannot hide it). A fold carrying a confirmation request is
    not a triage marker (shared rules). A fold is always AI-drafted.
    """
    fold = markers.parse_fold(pr.get("body") or "")
    if fold is None or fold.action == markers.CONFIRMATION_ACTION:
        return None
    return fold.triaged


def fold_is_stale(pr):
    """The fold's ``head=`` no longer matches the PR head: the author pushed since."""
    fold = markers.parse_fold(pr.get("body") or "")
    nodes = (pr.get("commits") or {}).get("nodes") or []
    oid = ((nodes[-1] if nodes else {}).get("commit") or {}).get("oid")
    return bool(fold and fold.head and oid and not oid.startswith(fold.head))


def _author_comments(pr):
    """The PR author's comments: issue comments and review-thread replies."""
    author = (pr.get("author") or {}).get("login")
    found = list((pr.get("comments") or {}).get("nodes") or [])
    for thread in (pr.get("reviewThreads") or {}).get("nodes") or []:
        found += (thread.get("comments") or {}).get("nodes") or []
    return [c for c in found if c.get("author") and author and c["author"].get("login") == author]


def triage_marker_events(pr, ctx):
    """All triage-marker occurrences across BOTH feedback channels.

    Returns ``(at, is_ai)`` tuples -- one per collaborator comment carrying the
    QC marker (``comment`` channel) plus one for the pr-body fold block
    (``pr-body`` channel, always AI). Empty when the PR was never triaged in
    either channel. The single source of truth for "is this PR triaged, when,
    and by which channel" -- classification and every velocity metric route
    through it so the fold channel is never invisible again."""
    events = []
    pr_author = (pr.get("author") or {}).get("login")
    for c in (pr.get("comments", {}) or {}).get("nodes", []) or []:
        commenter = (c.get("author") or {}).get("login")
        if (
            c.get("authorAssociation") in COLLAB_ASSOCIATIONS
            and commenter != pr_author
            and ctx["triage_marker"] in c.get("body", "")
        ):
            at = parse_iso(c.get("createdAt"))
            if at:
                events.append((at, ctx["ai_footer"] in c.get("body", "")))
    fat = fold_triaged_at(pr)
    if fat:
        events.append((fat, True))
    return events


def classify(pr, ctx, *, partial=False):
    """Annotate a PR node in place with `_`-prefixed classification fields.

    `partial=True` declares that the PR came from a reduced schema (the
    closed-PR query, which omits the heavy engagement collections —
    commits / latestReviews / reviewThreads / timelineItems). Those signals are
    read defensively below, so an absent collection contributes False to
    `_is_engaged` rather than raising. `isDraft` IS required from both queries
    (CLOSED_PRS_QUERY now selects it); it falls back to False only as a guard.
    """
    author = pr["author"]["login"] if pr["author"] else None
    assoc = pr.get("authorAssociation", "?")
    pr["_author"] = author
    pr["_assoc"] = assoc
    pr["_base_ref"] = pr.get("baseRefName")
    pr["_review_decision"] = pr.get("reviewDecision")
    pr["_is_backport"] = is_backport(pr)
    pr["_is_collab"] = assoc in COLLAB_ASSOCIATIONS
    pr["_is_contrib"] = (not pr["_is_collab"]) and (not is_bot(author))
    labels = [lbl["name"] for lbl in pr["labels"]["nodes"]]
    pr["_labels"] = labels
    pr["_areas"] = [lbl for lbl in labels if lbl.startswith(ctx["area_prefix"])]
    pr["_has_ready"] = ctx["ready_label"] in labels
    pr["_age_days"] = (ctx["now"] - parse_iso(pr["createdAt"])).days

    # Engagement signals — per the stats spec is_engaged predicate
    has_collab_comment = any(
        c.get("authorAssociation") in COLLAB_ASSOCIATIONS
        and not is_bot(c["author"]["login"] if c["author"] else None)
        for c in pr["comments"]["nodes"]
    )
    # Triage marker across BOTH channels: collaborator comments (comment
    # channel) AND the pr-body fold block (pr-body channel, the default).
    triage_events = triage_marker_events(pr, ctx)
    has_qc_marker = bool(triage_events)
    has_ai_footer = any(is_ai for _, is_ai in triage_events)
    has_review = any(
        r.get("author", {}).get("login") and not is_bot(r["author"]["login"])
        for r in (pr.get("latestReviews", {}).get("nodes") or [])
    )
    # reviewThreads — required for inline-comment-only engagement (e.g. line review without submitted review)
    has_review_thread_collab = False
    for thread in pr.get("reviewThreads", {}).get("nodes") or []:
        for c in thread.get("comments", {}).get("nodes") or []:
            if c.get("authorAssociation") in COLLAB_ASSOCIATIONS and not is_bot(
                c["author"]["login"] if c["author"] else None
            ):
                has_review_thread_collab = True
                break
        if has_review_thread_collab:
            break
    # Timeline events (LabeledEvent / draft conversion by maintainer)
    has_maintainer_event = False
    label_added_at = None
    for ev in pr.get("timelineItems", {}).get("nodes") or []:
        actor = (ev.get("actor") or {}).get("login")
        if actor and not is_bot(actor):
            has_maintainer_event = True
        if ev.get("label", {}).get("name") == ctx["ready_label"]:
            at = parse_iso(ev.get("createdAt"))
            if label_added_at is None or (at and at > label_added_at):
                label_added_at = at
    pr["_label_added_at"] = label_added_at

    pr["_has_qc_marker"] = has_qc_marker
    pr["_has_ai_footer"] = has_ai_footer
    pr["_is_engaged"] = (
        has_collab_comment
        or has_review
        or has_maintainer_event
        or has_review_thread_collab
        or pr["_has_ready"]
    )
    pr["_is_triaged"] = has_qc_marker
    pr["_is_untriaged"] = (
        not pr["_is_engaged"] and pr["_is_contrib"] and not pr.get("isDraft", False) and not pr["_has_ready"]
    )

    # Triage timestamp + responded -- latest marker across both channels
    triage_at = max((at for at, _ in triage_events), default=None)
    pr["_triage_at"] = triage_at

    # Shared rule: responded when the author commented (issue comment or
    # thread reply) or pushed after the newest marker, or the fold is stale.
    responded = False
    if triage_at:
        responded = any(
            (at := parse_iso(c.get("createdAt"))) is not None and at > triage_at for c in _author_comments(pr)
        )
        if not responded and pr.get("commits", {}).get("nodes"):
            lc = parse_iso(pr["commits"]["nodes"][-1]["commit"]["committedDate"])
            if lc and lc > triage_at:
                responded = True
        if not responded and fold_is_stale(pr):
            responded = True
    pr["_responded"] = responded

    pr["_waiting_ai"] = pr["_is_triaged"] and not pr["_responded"] and pr["_has_ai_footer"]
    pr["_waiting_manual"] = pr["_is_triaged"] and not pr["_responded"] and not pr["_has_ai_footer"]
    return pr


def last_author_at(pr):
    """The PR author's latest activity: opening the PR, a comment, or the head commit."""
    times = [parse_iso(pr.get("createdAt"))]
    times += [parse_iso(c.get("createdAt")) for c in _author_comments(pr)]
    nodes = (pr.get("commits") or {}).get("nodes") or []
    if nodes:
        times.append(parse_iso(((nodes[-1] or {}).get("commit") or {}).get("committedDate")))
    found = [t for t in times if t]
    return max(found) if found else None


def pressure_weight(pr, now):
    """the stats spec § Pressure score — one contributor PR's weight, first match wins.

    Collaborator PRs 0; ready label 1; triaged-waiting with the marker ≥ 7 days
    old 2; draft 0; untriaged non-draft by the author's last activity: ≥ 28
    days 5, ≥ 7 days 3, else 1. Anything else (triaged, responded) adds 0.
    Needs `classify` to have run.
    """
    if pr.get("_is_collab"):
        return 0
    if pr.get("_has_ready"):
        return 1
    triage_at = pr.get("_triage_at")
    if pr.get("_is_triaged") and not pr.get("_responded") and triage_at and (now - triage_at).days >= 7:
        return 2
    if pr.get("isDraft"):
        return 0
    if not pr.get("_is_untriaged"):
        return 0
    last = last_author_at(pr)
    idle = (now - last).days if last else 0
    if idle >= 28:
        return 5
    if idle >= 7:
        return 3
    return 1


# --------------------------------------------------------------------------
# Aggregations — see the stats spec
# --------------------------------------------------------------------------


def weeks_buckets(now, weeks=6):
    return [
        (now - timedelta(days=(weeks - i) * 7), now - timedelta(days=(weeks - 1 - i) * 7))
        for i in range(weeks)
    ]


def compute_weekly_velocity(closed_prs, weeks, ctx):
    out = []
    for s, e in weeks:
        b = {
            "start": s,
            "end": e,
            "merged": 0,
            "closed_not_merged": 0,
            "merged_triaged": 0,
            "closed_after_responded": 0,
            "closed_after_triage": 0,
            "closed_no_triage": 0,
        }
        for pr in closed_prs:
            ca = parse_iso(pr.get("closedAt"))
            if not ca or not (s <= ca < e):
                continue
            # Triage across both channels (comments + pr-body fold)
            events = triage_marker_events(pr, ctx)
            has_triage = bool(events)
            t_at = min((at for at, _ in events), default=None)
            responded = False
            if has_triage and t_at:
                for c in pr["comments"]["nodes"]:
                    if (
                        c["author"]
                        and pr["author"]
                        and c["author"]["login"] == pr["author"]["login"]
                        and parse_iso(c["createdAt"]) > t_at
                    ):
                        responded = True
                        break
            if pr.get("merged"):
                b["merged"] += 1
                if has_triage:
                    b["merged_triaged"] += 1
            else:
                b["closed_not_merged"] += 1
            if has_triage and responded:
                b["closed_after_responded"] += 1
            elif has_triage:
                b["closed_after_triage"] += 1
            else:
                b["closed_no_triage"] += 1
        out.append(b)
    return out


def parse_codeowners(text):
    rules = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "#" in stripped:
            stripped = stripped[: stripped.index("#")].strip()
            if not stripped:
                continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = [o.lstrip("@") for o in parts[1:] if o.startswith("@")]
        if owners:
            rules.append((pattern, owners))
    return rules


def codeowners_match(file_path, rules):
    matched = []
    for pattern, owners in rules:
        pat = pattern
        pat = "^" + pat[1:] if pat.startswith("/") else "(^|.*/)" + pat
        if pat.endswith("/"):
            pat = pat + ".*"
        pat = pat.replace("*", "[^/]*")
        try:
            if re.match(pat, file_path):
                matched = owners
        except re.error:
            continue
    return matched


def compute_codeowners_panel(open_prs, files_per_pr, codeowners_text):
    rules = parse_codeowners(codeowners_text)
    owner_prs = defaultdict(set)
    owner_waiting = defaultdict(set)
    ready_by_num = {pr["number"]: pr for pr in open_prs if pr["_has_ready"]}
    for pr_num, files in files_per_pr.items():
        pr = ready_by_num.get(pr_num)
        if not pr:
            continue
        owners_for_pr = set()
        for f in files:
            for o in codeowners_match(f, rules):
                owners_for_pr.add(o)
        author = pr["_author"]
        author_last_act = None
        if pr.get("commits", {}).get("nodes"):
            author_last_act = parse_iso(pr["commits"]["nodes"][0]["commit"]["committedDate"])
        for c in pr["comments"]["nodes"]:
            if c["author"] and c["author"]["login"] == author:
                at = parse_iso(c["createdAt"])
                if author_last_act is None or at > author_last_act:
                    author_last_act = at
        for owner in owners_for_pr:
            owner_prs[owner].add(pr_num)
            for c in pr["comments"]["nodes"]:
                if c["author"] and c["author"]["login"] == owner:
                    at = parse_iso(c["createdAt"])
                    if at and (author_last_act is None or at > author_last_act):
                        owner_waiting[owner].add(pr_num)
                        break
    return sorted([(o, len(owner_prs[o]), len(owner_waiting[o])) for o in owner_prs], key=lambda x: -x[1])


# (Remaining aggregation functions + render are kept inline below for self-contained reference.)
# For brevity in this reference, the full computations are in the agent-emitted version;
# this file is a runnable seed that an adopter can fork and extend per their own panels.
# Every panel listed in the stats spec MUST be implemented; do NOT silently omit any.

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="pr-management-stats canonical render")
    ap.add_argument("--repo", required=True, help="owner/name, e.g. apache/airflow")
    ap.add_argument("--viewer", required=True, help="viewer GitHub login")
    ap.add_argument("--since", help="cutoff YYYY-MM-DD (default: 6 weeks ago)")
    ap.add_argument("--out", default="dashboard.html", help="output HTML path")
    ap.add_argument("--triage-marker", default=DEFAULT_TRIAGE_MARKER)
    ap.add_argument("--ai-footer", default=DEFAULT_AI_FOOTER)
    ap.add_argument("--ready-label", default=DEFAULT_READY_LABEL)
    ap.add_argument("--area-prefix", default=DEFAULT_AREA_PREFIX)
    ap.add_argument("--page-size", type=int, default=30)
    args = ap.parse_args()

    now = datetime.now(UTC)
    weeks = 6
    cutoff = now - timedelta(weeks=weeks)
    if args.since:
        cutoff = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=UTC)

    ctx = {
        "now": now,
        "cutoff": cutoff,
        "weeks": weeks_buckets(now, weeks),
        "triage_marker": args.triage_marker,
        "ai_footer": args.ai_footer,
        "ready_label": args.ready_label,
        "area_prefix": args.area_prefix,
    }

    print("== pr-management-stats canonical render ==", file=sys.stderr)
    print(f"  repo={args.repo}  viewer={args.viewer}  cutoff={cutoff.date()}", file=sys.stderr)

    print("Fetching open PRs (full engagement schema) ...", file=sys.stderr)
    open_prs = paginated_search(OPEN_PRS_QUERY, f"is:pr is:open repo:{args.repo}", page_size=args.page_size)
    print(f"  -> {len(open_prs)} open PRs", file=sys.stderr)
    for pr in open_prs:
        classify(pr, ctx)

    print(f"Fetching closed/merged PRs since {cutoff.date()} ...", file=sys.stderr)
    closed_prs = paginated_search(
        CLOSED_PRS_QUERY,
        f"is:pr is:closed repo:{args.repo} closed:>={cutoff.date()}",
        page_size=50,
        max_pages=20,
    )
    print(f"  -> {len(closed_prs)} closed PRs (capped at 1000 per GitHub search)", file=sys.stderr)

    print("Fetching CODEOWNERS + ready PR files ...", file=sys.stderr)
    codeowners = fetch_codeowners(args.repo)
    ready_nums = [pr["number"] for pr in open_prs if pr["_has_ready"]]
    files_per_pr = fetch_ready_pr_files(args.repo, ready_nums)
    print(
        f"  -> CODEOWNERS={len(codeowners)} chars, ready files for {len(files_per_pr)} PRs", file=sys.stderr
    )

    # This entry point stops at fetch + classify + the JSON sidecar; the
    # aggregation and the HTML are `dashboard.assemble`, reached through
    # `pr-management stats build`.

    # Persist intermediate state for the agent / downstream rendering:
    out_dir = Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    intermediates = {
        "fetched_at": now.isoformat(),
        "repo": args.repo,
        "viewer": args.viewer,
        "cutoff": cutoff.isoformat(),
        "open_count": len(open_prs),
        "closed_count": len(closed_prs),
        "ready_count": sum(1 for p in open_prs if p["_has_ready"]),
        "untriaged_count": sum(1 for p in open_prs if p["_is_untriaged"]),
        "untriaged_4w_count": sum(1 for p in open_prs if p["_is_untriaged"] and p["_age_days"] > 28),
        "engaged_count": sum(1 for p in open_prs if p["_is_engaged"]),
        "ai_triaged_count": sum(1 for p in open_prs if p["_has_ai_footer"]),
        "files_per_ready_pr_count": len(files_per_pr),
        "codeowners_bytes": len(codeowners),
    }
    side = Path(args.out).with_suffix(".json")
    side.write_text(json.dumps(intermediates, indent=2))
    print(f"\nIntermediate state written to {side}", file=sys.stderr)
    print(json.dumps(intermediates, indent=2))


if __name__ == "__main__":
    main()
