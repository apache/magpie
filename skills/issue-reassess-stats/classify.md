<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Classify — bucketing the verdicts

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 2:
bucketing each parsed verdict for the aggregation step.

Classification is pure function of the parsed verdicts produced by
[`fetch.md`](fetch.md) — no network, no writes. Any rule change
here must agree with the producer's labelling logic in
[`issue-reproducer/verification.md`](../issue-reproducer/verification.md).

## Primary axis: `classification`

Ten labels per
[`issue-reproducer/verdict-composition.md`](../issue-reproducer/verdict-composition.md):

| Label | Dashboard bucket |
|---|---|
| `fixed-on-master` | `fixed` (closure candidates) |
| `still-fails-same` | `still-failing` (action candidates) |
| `still-fails-different` | `still-failing` (action candidates) — but flagged: the failure shape differs from the original report |
| `intended-behaviour` | `closed-as-intended` (closure candidates with docs-pointer) |
| `duplicate-of-resolved` | `closed-as-duplicate` (closure candidates with sibling-key) |
| `cannot-run-extraction` | `unrun` (limitations bucket) |
| `cannot-run-environment` | `unrun` |
| `cannot-run-dependency` | `unrun` |
| `timeout` | `unrun` |
| `needs-separate-workspace` | `unrun` |

The four bucket-level labels (`fixed`, `still-failing`, `closed-
as-intended`, `closed-as-duplicate`, `unrun`) drive the
dashboard's hero cards.

## Secondary axis: `nature`

Five labels per
[`issue-reproducer/verdict-composition.md` → *"The nature field"*](../issue-reproducer/verdict-composition.md#the-nature-field):

| Label | Dashboard bucket |
|---|---|
| `bug-as-advertised` | `real-bug` |
| `bug-as-advertised-partial-fix` | `real-bug-partial` (a sub-bucket; surfaces in the partial-fix panel) |
| `feature-request` | `feature` |
| `feature-request-disguised-as-bug` | `feature-disguised` (surfaces in the tracker-hygiene panel) |
| `intended-and-documented` | `intended` (surfaces in the closure panel with docs-pointer) |

## Cross-tabulation

The most informative view: classification × nature. Common cells:

| Classification × Nature | What it means |
|---|---|
| `still-fails-same` × `bug-as-advertised` | Direct action candidate — real bug, still broken, fix it |
| `still-fails-same` × `feature-request-disguised-as-bug` | Tracker-hygiene candidate — re-type as Improvement, may or may not be implemented |
| `still-fails-same` × `bug-as-advertised-partial-fix` | Partial-fix candidate — some cases pass now, others still fail; finish the fix |
| `fixed-on-master` × `bug-as-advertised` | Standard closure — confirm and close |
| `intended-behaviour` × `intended-and-documented` | Documentation-gap candidate when the reporter mis-read the docs (note in dashboard) |

The classifier emits the full N × M counts; the
[`aggregate.md`](aggregate.md) step turns these into the
dashboard's headline counts.

## Multi-case partial-fix detection

When a verdict's `cases` array has mixed `match_on_master`
values, the classifier flags the verdict as a multi-case partial
fix. The flag is independent of the verdict's `classification`
field — a verdict can be `still-fails-same` overall (because some
cases still fail like the reporter said) AND be a partial fix
(because other cases that used to fail now pass).

The dashboard's *"partial-fix surfaces"* panel lists these
verdicts with their `cases_summary` line.

## New-issue candidates from probes

A verdict's `cross_type_probe.findings` or
`operator_variants_probe.findings` field, when non-empty, indicates
the probe surfaced a bug in a sibling type that the original
report didn't mention. These are new-issue candidates.

The classifier collects every such finding across the campaign
into the *"new-issue candidates"* list. Aggregation in
[`aggregate.md`](aggregate.md) clusters related findings (e.g.,
multiple probes from one family that surface the same sibling-
type bug).

## Per-component bucketing

When verdicts carry component labels (extracted from the
description or from a campaign-level metadata file), classify also
buckets by component for the per-component breakdown.

If no verdicts carry component data, the per-component section is
omitted from the dashboard.

## Age bucketing

Compute `age_days` per verdict from the issue's creation date
(extracted from `description.md` when present) and the campaign
run date (`fetched_at` or filesystem mtime as fallback). Buckets:

| Age | `age_days` | Label |
|---|---|---|
| < 90 days | `< 90` | `recent` |
| 90 days – 1 year | `90 – 365` | `mid` |
| 1 – 5 years | `365 – 1825` | `old` |
| ≥ 5 years | `≥ 1825` | `ancient` |

Bands are contiguous (no gaps) and evaluated low-to-high. The
narrower `recent` band keeps genuinely fresh issues distinguishable
from ones already unresolved for many months — issues under a year
old are where most reassess decisions actually land, so collapsing
them into one bucket hid the signal.

These bands are reasonable defaults, not a contract. "Recent" is
project-relative — a month-old issue is fresh for a fast-moving
project but stale for a long-stable one. An adopter retunes the
band edges via `.apache-magpie-overrides/issue-reassess-stats.md`
(see [`SKILL.md`](SKILL.md) failure modes); absent an override,
the defaults above apply.

The age axis informs the dashboard's *"oldest unresolved"* panel.

## Output

Return to the orchestrator a dict with:

- `by_classification: {label: count, ...}` — primary axis counts.
- `by_nature: {label: count, ...}` — secondary axis counts.
- `cross_tab: {(classification, nature): count, ...}` — full
  cross-tabulation.
- `partial_fix: [verdict, ...]` — multi-case partial-fix flagged
  verdicts.
- `new_issue_candidates: [finding, ...]` — from probe `findings`
  fields.
- `by_component: {component: {classification: count, ...}, ...}`
  — per-component breakdown.
- `by_age: {bucket: [verdict, ...], ...}` — age-bucketed verdicts.

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration.
- [`fetch.md`](fetch.md) — produces the parsed verdicts this
  step buckets.
- [`aggregate.md`](aggregate.md) — turns these buckets into
  dashboard payload.
- [`issue-reproducer/verification.md`](../issue-reproducer/verification.md) —
  the producer's classification logic this step mirrors.
- [`issue-reproducer/verdict-composition.md`](../issue-reproducer/verdict-composition.md) —
  the nature taxonomy.
