<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Aggregate — totals, health rating, recommendations

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 3:
turning classification buckets into the dashboard's hero cards,
action panel, and per-component breakdown.

## Hero-card values

Five hero cards at the top of the dashboard:

| Card | Source | When to highlight |
|---|---|---|
| **Candidates** | total parsed verdicts | always |
| **Still failing** | `still-fails-same` + `still-fails-different` count | red when > 20% of total, amber when > 5%, green otherwise |
| **Fixed on master** | `fixed-on-master` count | green |
| **Partial fix** | partial-fix-flagged verdicts (from classify) | amber when > 0 |
| **Unrun** | sum of `cannot-run-*` + `timeout` + `needs-separate-workspace` | amber when > 30% of total, red when > 50% |

The "highlight" colour is the dashboard's at-a-glance signal.

## Health rating

Compute one of three project-level ratings:

| Rating | Threshold |
|---|---|
| **Healthy** | Still-failing < 5% of total AND unrun < 20% of total |
| **Needs attention** | Still-failing 5–20% of total, or unrun 20–40% |
| **Action needed** | Still-failing > 20%, or unrun > 40% |

Thresholds are reasonable defaults; adopters override via
[`.apache-magpie-overrides/issue-reassess-stats.md`](../../docs/setup/agentic-overrides.md)
when the project's scale or expectations differ.

## Action candidates

Compute the prioritised action list. Higher-priority actions go
first in the dashboard's action panel:

1. **Direct fixes** — `still-fails-same` × `bug-as-advertised`,
   ordered by:
   - Has reproducer (per the verdict's evidence package)
   - Issue is well-formed (description + comments + at least one
     piece of context beyond the reporter)
   - Age — newer issues often have more context fresh in
     maintainers' minds
2. **Partial fixes** — multi-case partial-fix verdicts. The
   `cases_summary` line is the one-line description; the action
   is *"finish the remaining N cases"*.
3. **New-issue candidates** — from probe findings, clustered by
   family. The action is *"file a new issue for sibling-type
   bug"*.
4. **Tracker hygiene** — `still-fails-same` × `feature-request-
   disguised-as-bug`. Action: *"re-type to Improvement; may not be
   implemented but the type matches"*.
5. **Closure candidates** — `fixed-on-master` with strong evidence
   (clean run, identified fixing commit if `notes` cited one).
   Action: *"confirm and close"*.

Each action carries:

- The candidate's tracker key (clickable URL via
  `<project-config>/issue-tracker-config.md` → `issue_url_template`).
- One-line title (from description.md when available, key alone
  otherwise).
- The recommended next slash command:
  - `/issue-fix-workflow <KEY>` for direct fixes
  - manual close for closure candidates
  - manual file-new-issue for new-issue candidates
  - manual re-type for tracker-hygiene

## Closure recommendations

For each closure candidate, surface:

- The classification (`fixed-on-master`, `duplicate-of-resolved`,
  `intended-behaviour`).
- The supporting evidence:
  - Fixing commit (cited in `notes`) for `fixed-on-master`.
  - Canonical issue key for `duplicate-of-resolved`.
  - Documentation pointer for `intended-behaviour`.
- A polite-but-direct recommendation phrasing per
  [`SKILL.md`](SKILL.md)'s Golden rule 5 in the parent
  `issue-reassess` skill.

Phrase as recommendations, not directives. The dashboard is a
view, not an actor.

## New-issue cluster aggregation

Group new-issue candidates by family:

| Family | Examples |
|---|---|
| Type-family probes | range/index across List / Array / String backings; GPath across backend models |
| Operator-variant probes | safe-navigation variants; spread variants; comparison variants |

Within each family, cluster findings that point at the same
sibling-type bug. The dashboard shows one entry per cluster with
the count of contributing probes — better than N near-duplicate
entries.

## Per-component breakdown

When verdicts carry component data, surface the per-component view:

```text
Component      | Total | Fixed | Still-failing | Unrun | Rating
core           | 12    | 8     | 2             | 2     | Needs attention
xml            | 5     | 1     | 3             | 1     | Action needed
build          | 3     | 1     | 1             | 1     | Action needed
```

Per-component health rating uses the same thresholds as the
project-level rating, applied to that component's slice. Helps
maintainers route action candidates to the right component owner
without re-reading the per-issue table.

## Oldest-unresolved panel

For the still-failing tail, surface the oldest issues by
`created` date (extracted from description.md). The panel lists
the top-5 oldest with their age and one-line title. Useful for
periodic *"what's been broken longest"* checks.

## Methodology footer

Compute the *"about this campaign"* footer:

- **Pool** — from the campaign's `report.md` if present, otherwise
  *"unknown"*.
- **Rev / runtime** — from any one verdict's `rev` and `jdk`
  fields (they should all agree; if not, surface a *"mixed rev"*
  warning).
- **Run window** — earliest and latest `fetched_at` timestamps
  across the verdicts.
- **Limitations** — count of parse-error files, count of
  `cannot-run-*` verdicts with rough shape breakdown.

## Output

Return to the orchestrator the full dashboard payload:

```text
{
  hero_cards: {total, still_failing, fixed, partial, unrun, with thresholds + colours},
  health_rating: "Healthy" | "Needs attention" | "Action needed",
  action_candidates: [<ordered>],
  closure_candidates: [<list>],
  new_issue_clusters: [<by family>],
  tracker_hygiene: [<list>],
  by_component: {component: {total, fixed, still_failing, unrun, rating}, ...},
  oldest_unresolved: [<top-5>],
  methodology: {pool, rev, runtime, run_window, limitations},
  parse_errors: [<paths>]
}
```

[`render.md`](render.md) takes this payload and emits the HTML.

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration.
- [`fetch.md`](fetch.md) — produces the parsed verdicts.
- [`classify.md`](classify.md) — buckets the verdicts.
- [`render.md`](render.md) — turns this payload into HTML.
- [`<project-config>/issue-tracker-config.md`](../../projects/_template/issue-tracker-config.md) —
  `issue_url_template` for clickable links.
