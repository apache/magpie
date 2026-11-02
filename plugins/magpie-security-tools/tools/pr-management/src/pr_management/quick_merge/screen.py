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
"""The three-stage quick-merge screen, as a pure function of saved reads.

Stage 1 (quality gates) and Stage 2 (triviality and tier) run over the saved
ready-queue sweep; Stage 3 (live merge-readiness) over one live read per
survivor. A survivor without its live read comes back under `needs`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import ci, markers, model
from ..config import Config
from ..model import PR
from ..triage import signals
from . import globs
from .config import QuickMergeConfig

#: Saved-read file names (`vetted-op-read --save`).
READY = "express-ready.json"
ACTION_REQUIRED = "action-required.json"


def one_file(number: int) -> str:
    return f"express-one-{number}.json"


def live_file(number: int) -> str:
    return f"live-{number}.json"


def review_file(number: int) -> str:
    return f"review-{number}.json"


REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")

#: Drop reasons reported with PR numbers (the "so-close" PRs); the rest are counts.
NAMED_DROPS = ("too-large", "path-denied", "path-unmatched", "gate:G5-conflict", "gate:G5-blocked")

#: Directive-shaped phrases in contributor text: a cheap first screen. The agent
#: still reads every flagged PR as data and records what it ignored.
INJECTION = re.compile(
    r"ignore (?:the |all |any |your |previous |prior )|disregard (?:the |all |your )|skip (?:the )?(?:gate|check|review|screen)"
    r"|(?:safe|ok|okay) to merge|merge (?:this|it) (?:now|immediately|right away)|you are now|system prompt"
    r"|new instructions|surface this as",
    flags=re.IGNORECASE,
)

READY_STATES = frozenset({"clean", "has_hooks", "unstable", "behind"})

#: Classification documents, relative to the skill directory.
DOCS = {
    "ready": "classifications/ready-to-merge.md",
    "needs-approval": "classifications/needs-approval.md",
    "tier:A": "classifications/tier-a.md",
    "tier:B": "classifications/tier-b.md",
    "too-large": "classifications/too-large.md",
    "path-denied": "classifications/path-denied.md",
    "path-unmatched": "classifications/path-unmatched.md",
    "gate:G5-conflict": "classifications/g5-conflict.md",
    "gate:G5-blocked": "classifications/g5-blocked.md",
    "gate:G5-unknown": "classifications/g5-unknown.md",
}
#: One document per Stage-1 gate. Gate drops are reported as counts, so these
#: are reference reading — listed when the gate fired, read when the maintainer asks.
GATE_DOCS = {
    "gate:G1": "classifications/g1-ready-label.md",
    "gate:G2": "classifications/g2-real-ci-green.md",
    "gate:G3": "classifications/g3-checks-done.md",
    "gate:G4": "classifications/g4-workflow-approval.md",
    "gate:G5": "classifications/g5-batch-conflict.md",
    "gate:G6": "classifications/g6-collaborator-threads.md",
    "gate:G7": "classifications/g7-changes-requested.md",
}
ACTION_DOCS = {
    "present": "actions/present.md",
    "approve": "actions/approve.md",
    "handoff": "actions/hand-off.md",
}


@dataclass
class Screened:
    pr: PR
    files: list[dict[str, Any]]
    stage: str = "candidate"  # "drop" | "candidate" | "needs"
    drop: str | None = None
    tier: str | None = None
    bucket: str | None = None
    reason: str = ""
    live: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=dict)
    injection: list[str] = field(default_factory=list)
    needs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def churn(self) -> int:
        return self.pr.additions + self.pr.deletions


def _nodes(document: Any) -> list[dict[str, Any]]:
    pages = document if isinstance(document, list) else [document]
    found: list[dict[str, Any]] = []
    for page in pages:
        data = (page or {}).get("data") or {}
        search = data.get("search")
        if search is not None:
            found += [n for n in search.get("nodes") or [] if n and "number" in n]
            continue
        pull = (data.get("repository") or {}).get("pullRequest")
        if pull:
            found.append(pull)
    return found


def load(saved: Path, single: int | None = None) -> list[tuple[PR, list[dict[str, Any]]]]:
    """The screened PRs and their files; a fresh one-PR read replaces the sweep's copy."""
    nodes: dict[int, dict[str, Any]] = {}
    sweep = saved / READY
    if single is None and sweep.is_file():
        for node in _nodes(json.loads(sweep.read_text(encoding="utf-8"))):
            nodes[int(node["number"])] = node
    for path in sorted(saved.glob("express-one-*.json")):
        for node in _nodes(json.loads(path.read_text(encoding="utf-8"))):
            if single is None or int(node["number"]) == single:
                nodes[int(node["number"])] = node
    out = []
    for number in sorted(nodes):
        node = nodes[number]
        files = [f for f in ((node.get("files") or {}).get("nodes") or []) if f]
        out.append((model.from_node(node), files))
    return out


def injection_hits(pr: PR) -> list[str]:
    text = f"{pr.title}\n{markers.FOLD_RE.sub('', pr.body)}"
    return sorted({m.group(0) for m in INJECTION.finditer(text)})


def stage1(pr: PR, cfg: Config, action_required: dict[str, list[dict[str, Any]]]) -> tuple[str | None, str]:
    """The first failing gate (G1 → G7) and why, or (None, attestation)."""
    if cfg.ready_label not in pr.labels:
        return "gate:G1", f"G1 fails: the {cfg.ready_label!r} label is not on the PR."
    if pr.rollup_state != "SUCCESS":
        return "gate:G2", f"G2 fails: statusCheckRollup is {pr.rollup_state or 'missing'}, not SUCCESS."
    if not ci.real_ci_ran(pr, cfg):
        names = ", ".join(c.name for c in pr.contexts) or "none"
        return "gate:G2", f"G2 fails: SUCCESS but no real-CI context ran — only {names}."
    failed = ci.failed_checks(pr)
    pending = ci.pending_checks(pr)
    if failed or pending:
        what = ", ".join([*(f"{n} failed" for n in failed), *(f"{n} still running" for n in pending)])
        return "gate:G3", f"G3 fails: {what} — the PR is not done and green."
    if pr.head_sha in action_required:
        return "gate:G4", "G4 fails: a workflow run on the head is awaiting approval."
    if pr.mergeable == "CONFLICTING":
        return "gate:G5", "G5 fails: the batch reports a merge conflict."
    threads = signals.collaborator_threads(pr)
    if threads:
        who = ", ".join(sorted({t.first.author for t in threads if t.first}))
        return "gate:G6", f"G6 fails: {len(threads)} unresolved collaborator thread(s) ({who})."
    # `latestReviews` holds each reviewer's latest review, so a CHANGES_REQUESTED
    # here still stands. A later push does not dismiss it: only the reviewer can.
    for review in pr.reviews:
        if review.state == "CHANGES_REQUESTED":
            return "gate:G7", f"G7 fails: {review.author}'s request for changes still stands."
    green = [
        c.name for c in pr.contexts if c.conclusion in ("SUCCESS",) and ci.real_ci_ran(_only(pr, c), cfg)
    ]
    return None, f"all gates green (real CI: {', '.join(green) or 'present'}; no unresolved threads)"


def _only(pr: PR, ctx: Any) -> PR:
    """A copy of `pr` whose only context is `ctx` — to ask whether that one check is real CI."""
    from dataclasses import replace

    return replace(pr, contexts=(ctx,))


def stage2(
    pr: PR, files: list[dict[str, Any]], qcfg: QuickMergeConfig, tiers: tuple[str, ...], max_churn: int
) -> tuple[str | None, str | None, str]:
    """(drop reason, tier, reason)."""
    churn = pr.additions + pr.deletions
    count = pr.changed_files or len(files)
    if churn > max_churn:
        return "too-large", None, f"churn {churn} exceeds max_churn {max_churn}"
    if count > qcfg.max_files:
        return "too-large", None, f"{count} changed files exceed max_files {qcfg.max_files}"
    paths = [str(f.get("path")) for f in files]
    if count and len(paths) < count:
        return "too-large", None, f"{count} changed files, but only {len(paths)} listed — not screenable"
    for path in paths:
        hit = globs.first_match(qcfg.deny, path)
        if hit:
            return "path-denied", None, f"{path} matches the deny glob {hit} — deny wins at any size"
    allow_b = "B" in tiers
    tier_of: dict[str, str] = {}
    for path in paths:
        if globs.first_match(qcfg.tier_a, path):
            tier_of[path] = "A"
        elif allow_b and globs.first_match(qcfg.tier_b, path):
            tier_of[path] = "B"
        else:
            return (
                "path-unmatched",
                None,
                f"{path} matches no allow glob — unknown paths are not assumed safe",
            )
    tier = "B" if "B" in tier_of.values() else "A"
    mixed = len(set(tier_of.values())) == 2
    reason = (
        f"{count} file(s), {churn} lines — within budget (max {qcfg.max_files} files, {max_churn} churn); "
        f"{'mixed Tier A + Tier B → Tier B overall' if mixed else f'every file matches Tier {tier}'}; "
        "no deny-list match"
    )
    return None, tier, reason


def stage3(item: Screened, saved: Path) -> None:
    """Bucket a candidate from its live read, or record the reads it needs."""
    number = item.pr.number
    live_path = saved / live_file(number)
    if not live_path.is_file():
        item.stage = "needs"
        item.needs.append({"op": "pr-live-state", "params": [str(number)], "save": live_file(number)})
        return
    live = json.loads(live_path.read_text(encoding="utf-8"))
    item.live = live
    head = str(live.get("head_sha") or "")
    if head and not head.startswith(item.pr.head_sha[:7]):
        item.stage = "needs"
        item.needs.append({"op": "gql-pr-express-one", "params": [str(number)], "save": one_file(number)})
        item.reason = "the head moved since the sweep — re-screen this PR"
        return
    mergeable = live.get("mergeable")
    state = str(live.get("mergeable_state") or "unknown").lower()
    if mergeable is False or state == "dirty":
        item.stage, item.drop = "drop", "gate:G5-conflict"
        item.reason = "live: merge conflict — the contributor must rebase and resolve it"
        return
    if mergeable is None or state not in READY_STATES | {"blocked"}:
        item.stage, item.drop = "drop", "gate:G5-unknown"
        item.reason = f"live: mergeability still {state} — dropped this run, it qualifies once settled"
        return
    if state in READY_STATES:
        item.bucket = "ready"
        note = {"unstable": " (a non-required check is not green)", "behind": " (branch behind, still clean)"}
        item.reason += f"; live: mergeable, {state}{note.get(state, '')}"
        _load_review(item, saved, required=False)
        return
    review_path = saved / review_file(number)
    if not review_path.is_file():
        item.stage = "needs"
        item.needs.append(
            {"op": "gql-pr-review-decision", "params": [str(number)], "save": review_file(number)}
        )
        return
    _load_review(item, saved, required=True)
    if item.review.get("decision") == "REVIEW_REQUIRED":
        item.bucket = "needs-approval"
        item.reason += "; live: blocked on a missing committer approval (REVIEW_REQUIRED)"
    else:
        item.stage, item.drop = "drop", "gate:G5-blocked"
        item.reason = f"live: blocked, review decision {item.review.get('decision') or 'none'} — an approval does not clear it"


def _load_review(item: Screened, saved: Path, *, required: bool) -> None:
    path = saved / review_file(item.pr.number)
    if not path.is_file():
        return
    pull = ((json.loads(path.read_text(encoding="utf-8")).get("data") or {}).get("repository") or {}).get(
        "pullRequest"
    ) or {}
    rule = ((pull.get("baseRef") or {}).get("branchProtectionRule")) or {}
    item.review = {
        "decision": pull.get("reviewDecision"),
        "approvals": int(((pull.get("reviews") or {}).get("totalCount")) or 0),
        "required_approvals": rule.get("requiredApprovingReviewCount")
        if rule.get("requiresApprovingReviews")
        else None,
    }


def merge_command(template: str, number: int, repo: str) -> str:
    tokens = [t.replace("<N>", str(number)).replace("<repo>", repo) for t in shlex.split(template)]
    return shlex.join(tokens)


def approve_command(number: int, repo: str, body_file: str | None = None) -> str:
    argv = ["gh", "pr", "review", str(number), "--repo", repo, "--approve"]
    if body_file:
        argv += ["--body-file", body_file]
    return shlex.join(argv)


def run(
    saved: Path,
    cfg: Config,
    qcfg: QuickMergeConfig,
    *,
    tiers: tuple[str, ...] | None = None,
    max_churn: int | None = None,
    single: int | None = None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = cfg.upstream_repo or ""
    if not REPO.match(repo):
        raise SystemExit(f"pr-management: upstream_repo {repo!r} in project.md is not an owner/name slug")
    tiers = tiers or qcfg.default_tiers
    churn_cap = max_churn if max_churn is not None else qcfg.max_churn
    approved = (session or {}).get("approved", {})
    action_required = ci.load_action_required(
        saved / ACTION_REQUIRED if (saved / ACTION_REQUIRED).is_file() else None
    )
    items: list[Screened] = []
    prefetch: list[dict[str, Any]] = []
    if not (saved / ACTION_REQUIRED).is_file():
        prefetch.append({"op": "runs-action-required", "params": [], "save": ACTION_REQUIRED})
    for pr, files in load(saved, single):
        prior = approved.get(str(pr.number))
        if prior and prior.get("head") == pr.head_sha:
            continue
        item = Screened(pr, files, injection=injection_hits(pr))
        drop, why = stage1(pr, cfg, action_required)
        if drop:
            item.stage, item.drop, item.reason = "drop", drop, why
        else:
            drop, tier, why2 = stage2(pr, files, qcfg, tiers, churn_cap)
            if drop:
                item.stage, item.drop, item.reason = "drop", drop, why2
            else:
                item.tier, item.reason = tier, f"{why}; {why2}"
                stage3(item, saved)
        if item.injection and item.stage != "needs":
            item.reason += "; directive-shaped text in the PR was treated as data and ignored"
        items.append(item)
    return _output(items, repo, qcfg, tiers, prefetch)


def _entry(item: Screened, repo: str, qcfg: QuickMergeConfig) -> dict[str, Any]:
    pr = item.pr
    entry: dict[str, Any] = {
        "number": pr.number,
        "title": pr.title,
        "url": pr.url,
        "author": pr.author,
        "head_sha": pr.head_sha,
        "size": f"+{pr.additions}/-{pr.deletions}",
        "files": [f"{f.get('path')}  +{f.get('additions', 0)}/-{f.get('deletions', 0)}" for f in item.files],
        "tier": item.tier,
        "mergeable_state": item.live.get("mergeable_state"),
        "reason": item.reason,
        "merge_command": merge_command(qcfg.merge_template, pr.number, repo),
    }
    if item.review:
        entry["approvals"] = item.review.get("approvals")
        entry["required_approvals"] = item.review.get("required_approvals")
    if item.bucket == "needs-approval" and qcfg.enable_approve:
        entry["approve"] = f"pr-management quick-merge approve-check --pr {pr.number} --head {pr.head_sha}"
    if item.injection:
        entry["injection_suspect_untrusted"] = item.injection
    return entry


def _rank(items: list[Screened]) -> list[Screened]:
    epoch = dt.datetime.min.replace(tzinfo=dt.UTC)
    return sorted(items, key=lambda i: (i.tier != "A", i.churn, i.pr.updated or epoch))


def _output(
    items: list[Screened],
    repo: str,
    qcfg: QuickMergeConfig,
    tiers: tuple[str, ...],
    prefetch: list[dict[str, Any]],
) -> dict[str, Any]:
    ready = _rank([i for i in items if i.stage == "candidate" and i.bucket == "ready"])
    approval = _rank([i for i in items if i.stage == "candidate" and i.bucket == "needs-approval"])
    drops: dict[str, list[int]] = {}
    for item in items:
        if item.stage == "drop" and item.drop:
            drops.setdefault(item.drop, []).append(item.pr.number)
    needs = [n | {"pr": i.pr.number} for i in items if i.stage == "needs" for n in i.needs]
    docs: list[str] = []

    def want(doc: str) -> None:
        if doc not in docs:
            docs.append(doc)

    if ready or approval:
        want(ACTION_DOCS["present"])
    if ready:
        want(DOCS["ready"])
    if approval:
        want(DOCS["needs-approval"])
        if qcfg.enable_approve:
            want(ACTION_DOCS["approve"])
    for item in [*ready, *approval]:
        want(DOCS[f"tier:{item.tier}"])
    for reason in drops:
        if reason in DOCS:
            want(DOCS[reason])
    handoff = sorted(n for r in ("too-large", "path-denied", "path-unmatched") for n in drops.get(r, []))
    if handoff:
        want(ACTION_DOCS["handoff"])
    candidates = len(ready) + len(approval)
    screened = len(items)
    return {
        "repo": repo,
        "tiers": list(tiers),
        "screened": screened,
        "ready": [_entry(i, repo, qcfg) for i in ready],
        "needs_approval": [_entry(i, repo, qcfg) for i in approval],
        "drops": {
            reason: (sorted(numbers) if reason in NAMED_DROPS else len(numbers))
            for reason, numbers in sorted(drops.items())
        },
        "drop_reasons": {
            str(i.pr.number): i.reason for i in items if i.stage == "drop" and i.drop in NAMED_DROPS
        },
        "needs": needs,
        "prefetch": prefetch,
        "handoff": {
            "prs": handoff,
            "suggestion": "pr-management-code-review" if handoff else None,
        },
        "summary": {
            "candidates": candidates,
            "by_tier": {t: sum(1 for i in [*ready, *approval] if i.tier == t) for t in ("A", "B")},
            "ready": len(ready),
            "needs_approval": len(approval),
            "dropped": sum(len(v) for v in drops.values()),
            "fast_track_fraction": round(candidates / screened, 3) if screened else 0.0,
        },
        "docs": docs,
        "reference_docs": [GATE_DOCS[r] for r in sorted(drops) if r in GATE_DOCS],
        "approve_enabled": qcfg.enable_approve,
        "warnings": list(qcfg.warnings),
    }
