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

"""Deterministic vendor-neutrality score for Magpie.

The score answers a single question with no hidden judgement: **for each
capability *contract*, does Magpie already work across more than one
vendor — and is any skill locked to a vendor that has no alternative?**

It reads three machine-readable inputs from the repository and nothing
else, so the same tree always yields the same score:

1.  ``tools/*/README.md`` — every contract tool declares
    ``**Capability:**`` (the ``contract:<name>`` it fulfils),
    ``**Kind:**`` (``interface`` for a pure spec, ``implementation``
    for a concrete backend), and ``**Vendor:**`` (the backend identity,
    or ``agnostic`` for an interface).
2.  ``skills/*/SKILL.md`` — the ``organization:`` frontmatter field
    (declared org scope) plus the skill body (scanned for the concrete
    backends it names).
3.  The policy below — which of three neutrality *classes* each
    contract belongs to. This is the only hand-maintained input and it
    lives in one reviewable place.

Scoring rule (substrates are Magpie's own machinery and never count):

* ``vendor-backed`` contract -> GREEN when at least
  ``MIN_VENDORS`` distinct backend vendors implement it.
* ``agnostic`` contract -> GREEN by construction (one vendor-neutral
  spec serves every backend; there is no vendor to be neutral between).
* ``single-org`` contract -> GREEN by exemption (the capability is
  bound to one organisation's data model; there is no vendor choice to
  make).

The overall score is ``green_contracts / total_contracts``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Policy (the only hand-maintained input)
# ---------------------------------------------------------------------------

VENDOR_BACKED = "vendor-backed"
AGNOSTIC = "agnostic"
SINGLE_ORG = "single-org"

# Minimum distinct backend vendors a vendor-backed contract needs to be
# considered vendor neutral (the criterion from apache/magpie-site#17).
MIN_VENDORS = 2

# contract -> (neutrality class, human-readable capability summary)
CONTRACT_POLICY: dict[str, tuple[str, str]] = {
    "contract:tracker": (VENDOR_BACKED, "Issue / board / label backend"),
    "contract:source-control": (VENDOR_BACKED, "Branch / commit / diff / push (VCS)"),
    "contract:change-request": (
        VENDOR_BACKED,
        "Proposed-change review + merge gate (PR / MR / Gerrit change)",
    ),
    "contract:mail-archive": (VENDOR_BACKED, "Mailing-list / forum archive reads"),
    "contract:mail-source": (VENDOR_BACKED, "Inbound-mail ingestion (mbox / IMAP / …)"),
    "contract:mail-draft": (VENDOR_BACKED, "Outbound mail composition (draft, never send)"),
    "contract:cve-authority": (VENDOR_BACKED, "CVE allocation / record management / publication"),
    "contract:report-relay": (AGNOSTIC, "Inbound security-report relay detection"),
    "contract:scan-format": (AGNOSTIC, "Security-scanner report parsing"),
    "contract:project-metadata": (SINGLE_ORG, "Governance rosters / people / releases"),
}

# Which capability *contract* a skill actually invokes, keyed by
# high-confidence usage signals: MCP tool-call names, specific CLI verbs,
# and canonical hostnames. A skill is coupled only when a contract it
# invokes has no alternative backend — so this maps *usage*, not prose
# mentions (a skill that merely names "GitHub" in a sentence is not caught;
# one that calls ``gh issue`` or ``mcp__github__*`` is). Contracts that are
# agnostic by construction (report-relay, scan-format) and mail-source
# (indistinguishable from archive reads at the token level) are omitted —
# they never change a skill's verdict.
#
# ``gh pr`` is deliberately NOT a tracker signal: driving pull requests is the
# change-request contract (below), which only GitHub implements today. Jira —
# the second tracker backend — has no pull-request model, so a skill that runs
# ``gh pr`` is coupled to GitHub even though the *issue* side of tracker is
# portable.
CONTRACT_USAGE_TOKENS: dict[str, tuple[str, ...]] = {
    "contract:tracker": (
        r"mcp__github__",
        r"\bgh (?:issue|api|search|run|workflow|release|label)\b",
        r"\bJIRA\b",
    ),
    "contract:change-request": (r"\bgh pr\b",),
    "contract:source-control": (
        r"\bgit (?:commit|push|checkout|branch|rebase|merge|switch|worktree)\b",
        r"\bsvn (?:checkout|commit|update|cat|list|mkdir|import|move|delete|switch|copy)\b",
    ),
    "contract:mail-archive": (
        r"mcp__ponymail__",
        r"mcp__claude_ai_Gmail__(?:search_threads|get_thread|list_)",
    ),
    "contract:mail-draft": (
        r"mcp__claude_ai_Gmail__create_draft",
        r"\bcreate_draft\b",
    ),
    "contract:cve-authority": (
        r"\bVulnogram\b",
        r"\bcveawg\b",
        r"\bcve\.org\b",
    ),
    "contract:project-metadata": (
        r"mcp__apache-projects__",
        r"\bprojects\.apache\.org\b",
    ),
}

_CAP_RE = re.compile(r"^\*\*Capability:\*\*[ \t]+(.+)$", re.MULTILINE)
_KIND_RE = re.compile(r"^\*\*Kind:\*\*[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_VENDOR_RE = re.compile(r"^\*\*Vendor:\*\*[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_ORG_RE = re.compile(r"^organization:[ \t]*(.+?)[ \t]*$", re.MULTILINE)

INTERFACE = "interface"
IMPLEMENTATION = "implementation"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolMeta:
    """A contract tool's declared vendor-neutrality metadata."""

    name: str
    contracts: tuple[str, ...]
    kind: str
    vendor: str


@dataclass
class ContractResult:
    contract: str
    klass: str
    summary: str
    green: bool
    basis: str
    interfaces: list[str] = field(default_factory=list)
    implementations: list[ToolMeta] = field(default_factory=list)

    @property
    def vendors(self) -> list[str]:
        return sorted({t.vendor for t in self.implementations})


@dataclass
class SkillResult:
    name: str
    organization: str
    contracts: list[str]  # capability contracts the skill invokes
    verdict: str
    coupled: list[tuple[str, str]]  # (sole vendor, contract) with no alternative


# ---------------------------------------------------------------------------
# Repo discovery + parsing
# ---------------------------------------------------------------------------


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward until a directory holds the framework's tool + skill trees."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "tools").is_dir() and (candidate / "docs" / "labels-and-capabilities.md").is_file():
            return candidate
    # Fall back to the repo this file ships in.
    return Path(__file__).resolve().parents[4]


def _parse_capabilities(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split("+") if part.strip())


def load_tools(repo_root: Path) -> list[ToolMeta]:
    """Read every ``tools/*/README.md`` that declares a ``contract:*`` capability."""
    tools: list[ToolMeta] = []
    for readme in sorted((repo_root / "tools").glob("*/README.md")):
        text = readme.read_text(encoding="utf-8")
        cap_m = _CAP_RE.search(text)
        if not cap_m:
            continue
        caps = _parse_capabilities(cap_m.group(1))
        contracts = tuple(c for c in caps if c.startswith("contract:"))
        if not contracts:
            continue  # substrate-only tool: Magpie's own machinery, excluded
        name = readme.parent.name
        kind_m = _KIND_RE.search(text)
        vendor_m = _VENDOR_RE.search(text)
        if not kind_m or not vendor_m:
            raise ValueError(
                f"tools/{name}/README.md declares {contracts} but is missing "
                f"a '**Kind:**' and/or '**Vendor:**' field required for scoring"
            )
        kind = kind_m.group(1).strip()
        if kind not in (INTERFACE, IMPLEMENTATION):
            raise ValueError(
                f"tools/{name}: **Kind:** must be '{INTERFACE}' or '{IMPLEMENTATION}', got '{kind}'"
            )
        tools.append(ToolMeta(name=name, contracts=contracts, kind=kind, vendor=vendor_m.group(1).strip()))
    return tools


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter, body) for a ``---``-delimited markdown file."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[1], parts[2]
    return "", text


def load_skills(repo_root: Path) -> list[tuple[str, str, str]]:
    """Return (name, organization, body) for every ``skills/*/SKILL.md``."""
    out: list[tuple[str, str, str]] = []
    for skill_md in sorted((repo_root / "skills").glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        front, body = _split_frontmatter(text)
        org_m = _ORG_RE.search(front)
        org = org_m.group(1).strip() if org_m else "agnostic"
        out.append((skill_md.parent.name, org, body))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_contracts(tools: list[ToolMeta]) -> list[ContractResult]:
    """Compute the per-contract vendor-neutrality result."""
    seen = {c for t in tools for c in t.contracts}
    unknown = seen - CONTRACT_POLICY.keys()
    if unknown:
        raise ValueError(f"contract(s) {sorted(unknown)} declared by a tool but absent from CONTRACT_POLICY")

    results: list[ContractResult] = []
    for contract, (klass, summary) in CONTRACT_POLICY.items():
        providers = [t for t in tools if contract in t.contracts]
        interfaces = sorted(t.name for t in providers if t.kind == INTERFACE)
        impls = [t for t in providers if t.kind == IMPLEMENTATION]
        res = ContractResult(
            contract=contract,
            klass=klass,
            summary=summary,
            green=False,
            basis="",
            interfaces=interfaces,
            implementations=sorted(impls, key=lambda t: t.vendor),
        )
        if klass == AGNOSTIC:
            res.green = True
            res.basis = "vendor-neutral by construction — one spec serves every backend"
        elif klass == SINGLE_ORG:
            res.green = True
            org = ", ".join(res.vendors) or "a single organisation"
            res.basis = f"single-organisation capability ({org}); no vendor choice to make"
        else:  # vendor-backed
            n = len(res.vendors)
            res.green = n >= MIN_VENDORS
            if res.green:
                res.basis = f"{n} backend vendors: {', '.join(res.vendors)}"
            elif n == 0:
                res.basis = "no backend implemented yet"
            else:
                res.basis = (
                    f"only {n} backend vendor ({', '.join(res.vendors)}); needs {MIN_VENDORS - n} more"
                )
        results.append(res)
    return results


def score_skills(
    skills: list[tuple[str, str, str]],
    contract_results: list[ContractResult],
) -> list[SkillResult]:
    """Assess each skill: which capability contracts it invokes, and whether
    any of those contracts has no alternative backend (a real lock-in)."""
    green_by_contract = {r.contract: r.green for r in contract_results}
    # A not-green vendor-backed contract with a single backend is a lock-in;
    # name the sole vendor so the report can attribute it.
    sole_vendor = {
        r.contract: r.vendors[0]
        for r in contract_results
        if r.klass == VENDOR_BACKED and not r.green and len(r.vendors) == 1
    }
    patterns = {c: [re.compile(p) for p in pats] for c, pats in CONTRACT_USAGE_TOKENS.items()}
    out: list[SkillResult] = []
    for name, org, body in skills:
        used = sorted(c for c, regexes in patterns.items() if any(r.search(body) for r in regexes))
        coupled = sorted(
            (sole_vendor[c], c) for c in used if not green_by_contract.get(c, True) and c in sole_vendor
        )
        if not used:
            verdict = "capability-pure"
        elif coupled:
            verdict = "vendor-coupled"
        else:
            verdict = "portable"
        out.append(SkillResult(name=name, organization=org, contracts=used, verdict=verdict, coupled=coupled))
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_MARK = {True: "✅", False: "❌"}


def _overall(contract_results: list[ContractResult]) -> tuple[int, int, int]:
    green = sum(1 for r in contract_results if r.green)
    total = len(contract_results)
    pct = round(100 * green / total) if total else 0
    return green, total, pct


def render_text(contract_results: list[ContractResult], skill_results: list[SkillResult]) -> str:
    green, total, pct = _overall(contract_results)
    lines = [
        "Vendor-neutrality score (deterministic)",
        "=" * 40,
        f"Overall: {green}/{total} capability contracts vendor neutral ({pct}%)",
        "",
        "Per-contract status:",
    ]
    for r in contract_results:
        lines.append(f"  {_MARK[r.green]} {r.contract:26} [{r.klass:12}] {r.basis}")
    # Skill summary
    by_verdict: dict[str, int] = {}
    by_org: dict[str, int] = {}
    for s in skill_results:
        by_verdict[s.verdict] = by_verdict.get(s.verdict, 0) + 1
        by_org[s.organization] = by_org.get(s.organization, 0) + 1
    lines += ["", f"Skills: {len(skill_results)} total"]
    for verdict in ("capability-pure", "portable", "vendor-coupled"):
        if verdict in by_verdict:
            lines.append(f"  {verdict:16} {by_verdict[verdict]}")
    lines.append("  organization scope: " + ", ".join(f"{o}={n}" for o, n in sorted(by_org.items())))
    coupled = [s for s in skill_results if s.verdict == "vendor-coupled"]
    if coupled:
        lines += ["", "Vendor-coupled skills (no alternative backend for a named capability):"]
        for s in coupled:
            detail = "; ".join(f"{v} → {c}" for v, c in s.coupled)
            lines.append(f"  - {s.name}: {detail}")
    return "\n".join(lines) + "\n"


def render_json(contract_results: list[ContractResult], skill_results: list[SkillResult]) -> str:
    green, total, pct = _overall(contract_results)
    payload = {
        "overall": {"green": green, "total": total, "percent": pct},
        "contracts": [
            {
                "contract": r.contract,
                "class": r.klass,
                "green": r.green,
                "basis": r.basis,
                "vendors": r.vendors,
                "interfaces": r.interfaces,
                "implementations": [{"tool": t.name, "vendor": t.vendor} for t in r.implementations],
            }
            for r in contract_results
        ],
        "skills": [
            {
                "skill": s.name,
                "organization": s.organization,
                "contracts_used": s.contracts,
                "verdict": s.verdict,
                "coupled": [{"vendor": v, "contract": c} for v, c in s.coupled],
            }
            for s in skill_results
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_markdown(contract_results: list[ContractResult], skill_results: list[SkillResult]) -> str:
    """Emit the generated block for docs/vendor-neutrality.md."""
    green, total, pct = _overall(contract_results)
    lines = [
        f"**Overall vendor-neutrality score: {green}/{total} capability contracts "
        f"({pct}%).** Generated by [`tools/vendor-neutrality-score`](../tools/vendor-neutrality-score/); "
        "re-run it to refresh this section.",
        "",
        "| Capability contract | Neutral? | Class | Backends today | Basis |",
        "|---|---|---|---|---|",
    ]
    for r in contract_results:
        backends = ", ".join(r.vendors) if r.vendors else "—"
        lines.append(f"| `{r.contract}` | {_MARK[r.green]} | {r.klass} | {backends} | {r.basis} |")

    by_verdict: dict[str, int] = {}
    by_org: dict[str, int] = {}
    for s in skill_results:
        by_verdict[s.verdict] = by_verdict.get(s.verdict, 0) + 1
        by_org[s.organization] = by_org.get(s.organization, 0) + 1
    neutral = by_verdict.get("capability-pure", 0) + by_verdict.get("portable", 0)
    lines += [
        "",
        f"**Per-skill assessment: {neutral}/{len(skill_results)} skills carry no vendor lock-in.** "
        "A skill is *capability-pure* when it names no backend at all, *portable* when every backend "
        "it names has an alternative (its contract is green), and *vendor-coupled* only when it reaches "
        "for a backend that is the sole implementation of a capability.",
        "",
        "| Skill neutrality | Count |",
        "|---|---|",
        f"| capability-pure (names no backend) | {by_verdict.get('capability-pure', 0)} |",
        f"| portable (named backends are swappable) | {by_verdict.get('portable', 0)} |",
        f"| vendor-coupled (sole-backend dependency) | {by_verdict.get('vendor-coupled', 0)} |",
        "",
        "Organization scope (declared, orthogonal to vendor): "
        + ", ".join(f"{o} = {n}" for o, n in sorted(by_org.items()))
        + ".",
    ]
    coupled = [s for s in skill_results if s.verdict == "vendor-coupled"]
    if coupled:
        lines += ["", "Vendor-coupled skills (the only lock-ins today):", ""]
        for s in coupled:
            detail = "; ".join(f"`{v}` → `{c}`" for v, c in s.coupled)
            lines.append(f"- `{s.name}` — {detail}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def compute(repo_root: Path) -> tuple[list[ContractResult], list[SkillResult]]:
    tools = load_tools(repo_root)
    contract_results = score_contracts(tools)
    skill_results = score_skills(load_skills(repo_root), contract_results)
    return contract_results, skill_results


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic Magpie vendor-neutrality score.")
    parser.add_argument(
        "--repo-root", type=Path, default=None, help="Repository root (default: auto-detect)."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Emit the full result as JSON.")
    group.add_argument(
        "--markdown", action="store_true", help="Emit the generated block for docs/vendor-neutrality.md."
    )
    parser.add_argument(
        "--fail-under",
        type=int,
        default=None,
        metavar="PCT",
        help="Exit non-zero if the overall percentage is below PCT (for CI gating).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
    try:
        contract_results, skill_results = compute(repo_root)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(render_json(contract_results, skill_results))
    elif args.markdown:
        print(render_markdown(contract_results, skill_results))
    else:
        print(render_text(contract_results, skill_results), end="")

    if args.fail_under is not None:
        _, _, pct = _overall(contract_results)
        if pct < args.fail_under:
            print(f"error: score {pct}% is below --fail-under {args.fail_under}%", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
