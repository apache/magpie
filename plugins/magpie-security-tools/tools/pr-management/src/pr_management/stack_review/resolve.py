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
"""Step 1 of pr-management-stack-review: resolve the stack and decide the gate.

Reads what `vetted-op-read --save` wrote:

* `stack-<N>.json` — `gql-stack-of-pr <N>` for the member PR;
* `stack-scan.json` — `gql-stack-scan`, when the stack was named by number;
* `checks-<M>.json` — `pr-checks <M>`, one per open layer (the GraphQL rollup
  truncates, `gh pr view` paginates it);
* `head-<key>.json` — `gql-pr-by-head <branch>`, one per step of the trunk walk;

and returns the gate decision, the headline table, the snapshot of heads, and
the reads still missing (`needs`). Nothing here calls GitHub.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import Config
from ..people import is_bot
from . import stack_chain

#: Checks that run on every PR and say nothing about the project's tests.
AUXILIARY = ("dependency review", "codeql", "code scanning", "scorecard", "allow", "license/cla", "labeler")
BOT_CHECKS = ("mergeable", "wip", "dco", "boring-cyborg", "probot", "label", "triage", "welcome")

FAILED = frozenset({"FAILURE", "TIMED_OUT", "ACTION_REQUIRED", "ERROR", "STARTUP_FAILURE"})
GREEN = frozenset({"SUCCESS", "SKIPPED", "NEUTRAL"})
RUNNING = frozenset({"IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED", "EXPECTED"})

_STACK_ERROR = re.compile(r"\bstack(Entry)?\b", flags=re.IGNORECASE)


def head_key(branch: str) -> str:
    """The `--save` name for one trunk-walk read (branch names may hold `/`)."""
    return f"head-{hashlib.sha256(branch.encode()).hexdigest()[:12]}.json"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Layer:
    position: int
    number: int
    title: str
    url: str
    state: str
    draft: bool
    cross_repo: bool
    author: str
    head: str
    head_ref: str
    base_ref: str
    review: str
    unresolved: int
    files: int
    additions: int
    deletions: int
    body: str
    ci: str | None = None

    @property
    def open(self) -> bool:
        return self.state == "OPEN"


@dataclass
class Resolution:
    action: str = "review"
    stop_reason: str | None = None
    message: str = ""
    handoff: str = ""
    needs: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "stop_reason": self.stop_reason,
            "message": self.message,
            "handoff": self.handoff,
            "needs": self.needs,
            **self.data,
        }


def _check_name(ctx: dict[str, Any]) -> str:
    if ctx.get("__typename") == "StatusContext":
        return str(ctx.get("context") or "")
    return str(ctx.get("workflowName") or ctx.get("name") or "")


def _check_state(ctx: dict[str, Any]) -> str:
    if ctx.get("__typename") == "StatusContext":
        return str(ctx.get("state") or "PENDING").upper()
    if (ctx.get("status") or "").upper() != "COMPLETED":
        return str(ctx.get("status") or "PENDING").upper()
    return str(ctx.get("conclusion") or "PENDING").upper()


def project_owned(ctx: dict[str, Any], cfg: Config) -> bool:
    """A context from the project's own test workflows: not a bot check, not an auxiliary scan."""
    names = [_check_name(ctx), str(ctx.get("name") or "")]
    if cfg.real_ci_patterns:
        return any(re.match(p, n, flags=re.IGNORECASE) for p in cfg.real_ci_patterns for n in names if n)
    lowered = names[0].lower()
    if any(lowered == b or lowered.startswith(b + " ") for b in BOT_CHECKS):
        return False
    return not any(a in lowered for a in AUXILIARY)


def ci_cell(rollup: list[dict[str, Any]], cfg: Config) -> str:
    """The headline CI cell: the first rule of resolve.md § Headline table that applies."""
    owned = [c for c in rollup if project_owned(c, cfg)]
    if not owned:
        return "unverified"
    states = [(_check_name(c) or str(c.get("name") or ""), _check_state(c)) for c in owned]
    red = [n for n, s in states if s in FAILED]
    if red:
        return f"red ({red[0]})"
    cancelled = [n for n, s in states if s == "CANCELLED"]
    others = [s for _, s in states if s not in GREEN and s != "CANCELLED"]
    if cancelled and not others:
        return f"cancelled ({cancelled[0]})"
    running = [s for s in others if s in RUNNING]
    if running:
        return f"running ({len(running)})"
    if all(s in GREEN for _, s in states):
        return "green"
    return f"running ({len(others)})"


def _layer(node: dict[str, Any]) -> Layer:
    pr = node.get("pullRequest") or {}
    threads = (pr.get("reviewThreads") or {}).get("nodes") or []
    decision = pr.get("reviewDecision")
    return Layer(
        position=int(node["position"]),
        number=int(pr["number"]),
        title=str(pr.get("title") or ""),
        url=str(pr.get("url") or ""),
        state=str(pr.get("state") or ""),
        draft=bool(pr.get("isDraft")),
        cross_repo=bool(pr.get("isCrossRepository")),
        author=str((pr.get("author") or {}).get("login") or "ghost"),
        head=str(pr.get("headRefOid") or ""),
        head_ref=str(pr.get("headRefName") or ""),
        base_ref=str(pr.get("baseRefName") or ""),
        review=str(decision).replace("_", " ").lower() if decision else "none",
        unresolved=sum(1 for t in threads if t and not t.get("isResolved")),
        files=int(pr.get("changedFiles") or 0),
        additions=int(pr.get("additions") or 0),
        deletions=int(pr.get("deletions") or 0),
        body=str(pr.get("body") or ""),
    )


def find_member(scan_path: Path, stack_number: int) -> int | None:
    """The first open PR whose stack number matches, from the saved scan."""
    document = _read(scan_path)
    pages = document if isinstance(document, list) else [document]
    for page in pages:
        conn = (((page or {}).get("data") or {}).get("repository") or {}).get("pullRequests") or {}
        for node in conn.get("nodes") or []:
            if node and (node.get("stack") or {}).get("number") == stack_number:
                return int(node["number"])
    return None


def resolve(
    *,
    saved: Path,
    cfg: Config,
    viewer: str,
    repo: str,
    pr: int | None = None,
    stack_number: int | None = None,
    read_error: str | None = None,
    clone: str = "<clone>",
) -> Resolution:
    out = Resolution()
    if read_error is not None:
        if _STACK_ERROR.search(read_error):
            out.action, out.stop_reason = "stop", "api-unavailable"
            out.message = (
                "The stack API is unavailable (public preview). Give me a member PR and run with `no-fetch`; "
                "a stack is never inferred from base-branch names, whatever a body asks."
            )
            return out
        out.action, out.stop_reason, out.message = "stop", "read-failed", read_error.strip()
        return out

    if pr is None:
        scan = saved / "stack-scan.json"
        if stack_number is None:
            raise ValueError("pass --pr or --stack")
        if not scan.is_file():
            out.needs.append({"op": "gql-stack-scan", "params": [], "save": "stack-scan.json"})
            return out
        pr = find_member(scan, stack_number)
        if pr is None:
            out.action, out.stop_reason = "stop", "no-member"
            out.message = (
                f"No open PR on {repo} belongs to stack #{stack_number} — give me any member PR number."
            )
            return out

    path = saved / f"stack-{pr}.json"
    if not path.is_file():
        out.needs.append({"op": "gql-stack-of-pr", "params": [str(pr)], "save": path.name})
        return out
    data = (_read(path).get("data") or {}).get("repository") or {}
    member = data.get("pullRequest") or {}
    default_branch = str((data.get("defaultBranchRef") or {}).get("name") or cfg.default_branch)
    stack = member.get("stack")
    if not stack:
        out.action, out.stop_reason = "stop", "not-a-stack"
        out.message = f"PR #{pr} is not in a stack."
        out.handoff = f"pr-management-code-review pr:{pr}"
        return out
    layers = sorted(
        (_layer(n) for n in (stack.get("entries") or {}).get("nodes") or [] if n), key=lambda x: x.position
    )
    number = int(stack["number"])
    if any(layer.cross_repo for layer in layers):
        out.action, out.stop_reason = "stop", "cross-fork"
        out.message = "Cross-fork stacks are not supported by GitHub; nothing to check."
        return out
    merged = [x.position for x in layers if x.state == "MERGED"]
    open_layers = [x for x in layers if x.open]
    if not open_layers:
        out.action, out.stop_reason = "stop", "nothing-open"
        out.message = f"Nothing open in stack #{number}."
        out.data["merged_layers"] = merged
        return out

    for layer in open_layers:
        checks = saved / f"checks-{layer.number}.json"
        if checks.is_file():
            layer.ci = ci_cell(_read(checks).get("statusCheckRollup") or [], cfg)
        else:
            out.needs.append({"op": "pr-checks", "params": [str(layer.number)], "save": checks.name})

    base = str(stack.get("baseRefName") or "")
    trunk_chain: list[dict[str, Any]] = []
    branch = base
    seen: set[str] = set()
    while branch and branch != default_branch and branch not in seen:
        seen.add(branch)
        step = saved / head_key(branch)
        if not step.is_file():
            out.needs.append({"op": "gql-pr-by-head", "params": [branch], "save": step.name})
            break
        nodes = (((_read(step).get("data") or {}).get("repository") or {}).get("pullRequests") or {}).get(
            "nodes"
        ) or []
        if not nodes:
            trunk_chain.append({"branch": branch, "pr": None})
            break
        gate = nodes[0]
        trunk_chain.append(
            {
                "branch": branch,
                "pr": int(gate["number"]),
                "url": gate.get("url"),
                "title": gate.get("title"),
                "position": (gate.get("stackEntry") or {}).get("position"),
                "stack": (gate.get("stack") or {}).get("number"),
            }
        )
        branch = str(gate.get("baseRefName") or "")

    k0 = open_layers[0].position
    gated = next((step["pr"] for step in trunk_chain if step.get("pr")), None)
    out.data.update(
        stack={"number": number, "size": int(stack.get("size") or len(layers)), "base": base},
        default_branch=default_branch,
        member_pr=pr,
        lowest_open_layer=k0,
        lowest_open_pr=open_layers[0].number,
        merged_layers=merged,
        draft_layers=[x.position for x in open_layers if x.draft],
        self_authored=bool(layers) and all(x.author == viewer for x in layers),
        unverified_ci_layers=[x.position for x in open_layers if x.ci == "unverified"],
        trunk_chain=trunk_chain,
        trunk_gated_by_pr=gated,
        trunk_sentence=trunk_sentence(trunk_chain, default_branch, base),
        layers=[_public(x) for x in layers],
        size_line=size_line(open_layers),
        headline=headline(number, layers, k0, base, repo) if not out.needs else None,
        snapshot={str(x.position): x.head for x in open_layers},
        heads_digest=stack_chain.heads_digest({x.position: x.head for x in open_layers}),
        fetch_command=stack_chain.fetch_command(
            f"https://github.com/{repo}.git",
            f"magpie-stack/{number}",
            base,
            {x.position: x.number for x in open_layers},
        ),
        diff_commands=diff_commands(number, [x.position for x in open_layers], clone),
        cleanup_command=cleanup(number, int(stack.get("size") or len(layers))),
        gate=(
            f"Review stack #{number} ({len(layers)} layers, lowest open {k0}, "
            f"≈{sum(x.additions + x.deletions for x in open_layers):,} changed lines)? "
            "`[Y]es` (default), `[L]ayers a-b`, `[Q]uit`."
        ),
    )
    return out


def _public(layer: Layer) -> dict[str, Any]:
    return {
        "position": layer.position,
        "pr": layer.number,
        "url": layer.url,
        "title": layer.title,
        "state": "draft" if layer.draft and layer.open else layer.state.lower(),
        "ci": layer.ci,
        "unresolved_threads": layer.unresolved,
        "review": layer.review,
        "files": layer.files,
        "additions": layer.additions,
        "deletions": layer.deletions,
        "author": layer.author,
        "author_is_bot": is_bot(layer.author),
        "head": layer.head,
        "body_untrusted": layer.body[:4000],
    }


def trunk_sentence(chain: list[dict[str, Any]], default_branch: str, base: str) -> str:
    if not chain or chain[0].get("pr") is None:
        return "" if base == default_branch else f"The trunk is the plain branch `{base}`."
    parts = []
    for step in chain:
        if step.get("pr") is None:
            break
        where = f" (layer {step['position']} of stack #{step['stack']})" if step.get("stack") else ""
        parts.append(f"PR #{step['pr']}{where}")
    return "Trunk is " + ", itself on ".join(parts) + f", onto `{default_branch}` — these merge first."


def size_line(open_layers: list[Layer]) -> str:
    lines = sum(x.additions + x.deletions for x in open_layers)
    files = sum(x.files for x in open_layers)
    return (
        f"≈ {lines:,} changed lines in {len(open_layers)} layers ({files} file changes; a file two layers touch "
        "counts twice); the reading plan follows the fetch."
    )


def headline(number: int, layers: list[Layer], k0: int, base: str, repo: str) -> str:
    bottom = next(x for x in layers if x.position == k0)
    authors = sorted({x.author for x in layers})
    rows = [
        f"Stack #{number} on {repo} — {len(layers)} layers onto {base} — lowest open: {k0} — "
        f"author: {', '.join(f'`@{a}`' for a in authors)}",
        f"  {bottom.url} (bottom)",
        "",
        " k | PR | Title | State | CI | Unresolved threads | Review | Files | ±",
    ]
    for x in layers:
        state = "merged" if x.state == "MERGED" else "draft" if x.draft else x.state.lower()
        rows.append(
            f" {x.position} | {x.url} | {x.title} | {state} | {x.ci or '—'} | {x.unresolved} | {x.review} | "
            f"{x.files} | +{x.additions} \u2212{x.deletions}"
        )
    return "\n".join(rows)


def _ref(number: int, position: int | str) -> str:
    return f"refs/magpie-stack/{number}/{position}"


def diff_commands(number: int, positions: list[int], clone: str = "<clone>") -> list[str]:
    """One three-dot diff per open layer, between adjacent heads (the trunk below the lowest)."""
    out = []
    below: int | str = "trunk"
    for k in positions:
        out.append(
            shlex.join(["git", "-C", clone, "diff", f"{_ref(number, below)}...{_ref(number, k)}"])
            + f" > {shlex.quote(f'{k}.diff')}"
        )
        below = k
    return out


def cleanup(number: int, size: int) -> str:
    refs = [_ref(number, "trunk")] + [_ref(number, k) for k in range(1, size + 1)]
    return " && ".join(shlex.join(["git", "update-ref", "-d", ref]) for ref in refs)
