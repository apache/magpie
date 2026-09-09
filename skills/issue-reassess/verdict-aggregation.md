<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Verdict aggregation — turning per-issue results into a campaign report

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 4
(aggregation) and Step 5 (report composition).

## Reading the verdicts

After the per-issue loop, the campaign has one `verdict.json` per
candidate under `<scratch>/<campaign-id>/<KEY>/verdict.json`. The
aggregation reads each file and pulls:

- `classification` — one of ten labels per
  [`issue-reproducer/verification.md`](../issue-reproducer/verification.md).
- `nature` — one of five labels per
  [`issue-reproducer/verdict-composition.md` → *"The nature field"*](../issue-reproducer/verdict-composition.md#the-nature-field).
- `cases` (if present) — multi-case state.
- `cross_type_probe.findings` (if present) — new-issue candidates.
- `notes` — any maintainer-citation shortcuts used.

The aggregation is purely a read over these files; no further
reproduction.

## Tally tables

Compute two orthogonal tallies. The matrix is informative —
nature × classification surfaces patterns the single-axis tallies
miss.

**By classification:**

| Classification | Count |
|---|---|
| `fixed-on-master` | N |
| `still-fails-same` | N |
| `still-fails-different` | N |
| `cannot-run-extraction` | N |
| `cannot-run-environment` | N |
| `cannot-run-dependency` | N |
| `timeout` | N |
| `intended-behaviour` | N |
| `duplicate-of-resolved` | N |
| `needs-separate-workspace` | N |

**By nature:**

| Nature | Count |
|---|---|
| `bug-as-advertised` | N |
| `bug-as-advertised-partial-fix` | N |
| `feature-request` | N |
| `feature-request-disguised-as-bug` | N |
| `intended-and-documented` | N |

**Cross-tabulation** (classification × nature) is the most useful
view — e.g., a high count of `(still-fails-same, feature-request-disguised-as-bug)`
indicates the project has accumulated unfiled-as-improvements
wishlist debt; a high count of
`(fixed-on-master, bug-as-advertised)` is straight-up closure-
candidate yield.

## Headline extraction

Per `SKILL.md` Golden rule 4, surface headlines, not stats. The
aggregation picks out:

### Action candidates (top of the report)

- **Still-failing bugs where a fix is likely small** —
  `still-fails-same` + `bug-as-advertised`, ideally with a small
  reproducer per shape A/B.
- **Partial-fix surfaces** — multi-case issues with mixed verdicts
  (`bug-as-advertised-partial-fix`). The `cases_summary` line in
  the verdict is the one-line description.
- **New-issue candidates** — entries from
  `cross_type_probe.findings` across the campaign. Often
  cluster (one probe family with several broken siblings → multiple
  related new issues).
- **Documentation-gap candidates** — `intended-and-documented` with
  a `notes` field saying the reporter mis-read the docs. Often a
  one-paragraph docs PR closes a class of similar reports.

### Closure candidates

- `fixed-on-master` with a confident verdict and an
  identifiable fixing commit (the `notes` field cites it).
- `duplicate-of-resolved` with the canonical issue named.
- `intended-behaviour` with a documented citation.

These are the *"a maintainer should consider closing X"*
recommendations — phrased as recommendations, not directives (per
`SKILL.md` Golden rule 5).

### Tracker-hygiene candidates

- `feature-request-disguised-as-bug` — recommend re-typing as
  Improvement / New Feature.
- Issues lacking component or area labels (if surfaced).
- Issues whose reporter clearly belongs in a different tracker.

## Per-component breakdown

When candidates carry component labels (from
`<project-config>/scope-labels.md`), aggregate by component:

```text
Component         | Total | fixed-on-master | still-fails-* | cannot-run-*
core              | 12    | 8               | 2             | 2
xml               | 5     | 1               | 3             | 1
build             | 3     | 1               | 1             | 1
```

Useful for routing the report's action candidates to the right
maintainer subset, and for surfacing components with disproportionate
silent-fix or still-failing rates.

## Campaign-level notes

The aggregation also surfaces meta-observations the report should
mention:

- **Run environment** — runtime version, JDK / interpreter version,
  `<default-branch>` rev at campaign start. If multiple JDKs were
  used (rare), list each per the per-issue verdicts.
- **Limitations** — issues not run because `cannot-run-*`, with a
  count and rough shape breakdown. *"3 of 10 needed
  needs-separate-workspace; not assessed by this campaign."*
- **Resumability** — if the campaign was resumed across sessions,
  note the session boundaries (visible in the `verdict.json`
  timestamps).

## Report-section ordering

The report-section order in `SKILL.md` Step 5 is deliberate:

1. **Summary** (brief — the maintainer's 30-second view).
2. **Headlines** — action candidates first.
3. **Closure candidates**.
4. **Tracker-hygiene candidates**.
5. **Per-issue table** (the comprehensive view).
6. **Methodology** (pool selected, limitations, environment).

A maintainer skimming the top should see *"here's what to act on"*
before *"here's the full data"*. The per-issue table is for the
detail pass after the headlines convince them to read on.

## Hand-back to `issue-fix-workflow`

For each `still-fails-*` headline candidate, the campaign already
produced:

- The adapted `reproducer.<ext>` (per
  [`issue-reproducer/extraction.md`](../issue-reproducer/extraction.md)).
- The `verdict.json` capturing the observed behaviour.
- The original report's relevant excerpts in `description.md`.

[`issue-fix-workflow`](../issue-fix-workflow/SKILL.md) accepts these
as inputs — the maintainer invokes it per candidate, the fix-flow
picks up the adapted reproducer as a regression-test starting point.

The aggregation surfaces this hand-back chain explicitly in the
report:

```text
## Ready for fix-workflow

These candidates have adapted reproducers ready as regression-test
starting points. Invoke `issue-fix-workflow <KEY>` to draft a fix:

- <KEY>-9999 — <one-line>; reproducer at <path>
- ...
```

## Hand-back to `issue-reassess-stats`

The campaign artefacts (one `verdict.json` per candidate plus the
top-level `report.md`) are exactly what
[`issue-reassess-stats`](../issue-reassess-stats/SKILL.md) reads to
produce its dashboard. The aggregation does not need to do
anything special; the dashboard consumes the same on-disk
artefacts.

When the campaign completes, surface to the user:

```text
Campaign aggregate written to <scratch>/<campaign-id>/report.md
Dashboard view: issue-reassess-stats <scratch>/<campaign-id>/
```

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration; this file expands Steps
  4–6.
- [`pool-selection.md`](pool-selection.md) — what the candidate set
  looked like.
- [`per-issue-flow.md`](per-issue-flow.md) — what each per-issue
  verdict captured.
- [`issue-reproducer/verdict-composition.md`](../issue-reproducer/verdict-composition.md) —
  the `verdict.json` schema being read.
- [`issue-reassess-stats`](../issue-reassess-stats/SKILL.md) —
  dashboard consumer.
- [`issue-fix-workflow`](../issue-fix-workflow/SKILL.md) — next-skill
  consumer for `still-fails-*` candidates.
