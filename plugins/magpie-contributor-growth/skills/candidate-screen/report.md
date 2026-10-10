<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Report

Layout of the `candidate-screen` report.

## Layout

```markdown
# Candidate screen — <upstream> — <since> → <end>

> This report only shows activity data. It covers everyone who passed a pre-filter that
> drops the long tail, deliberately more people than the <governance-body> would consider.
> Nobody is scored or compared with any threshold, it is not a ranking — people appear in
> alphabetical order of GitHub handle — and it does not say whether anyone is ready.
> Every decision is made by <governance-body> members.

Thresholds: <source file>, calibrated on <calibrated_on, or "not calibrated">
Sources collected: <list>; not collected: <list, with the reason>
Pool: <N> contributors; pre-filter kept <N> (committer <N>, <governance-body> <N>)

## People

- [<Real Name> (handle)](#<anchor of their section>) — <target>

## Summary of findings

<One or two paragraphs describing what was found across the list — kinds
of work, areas, sources not collected. No comparison between people or with
any threshold, no ordering, no readiness judgement.>

## <Real Name> ([handle](https://github.com/handle)) — <target>

<Two or three paragraphs: what they built and in which areas; review, mentoring
and community work; factual flags. Every claim links to its evidence.>

### Areas

| Area | PRs merged (adjusted, share) | Reviews (adjusted, share) |
|------|------------------------------|---------------------------|
| <area> | N.N (NN.N %) | N.N (NN.N %) |

### Activity

| Dimension | Raw | Discounted | Penalty | Adjusted |
|-----------|-----|------------|---------|----------|

### Community

<Section per community-signals.md § Reporting.>

## Dropped by the pre-filter

| Handle | Merged PRs | Reviewed PRs |
|--------|------------|--------------|
```

## Rules

- A handle is always a plain link, `[handle](https://github.com/handle)` — never `@handle`, so no one is notified.
- Names follow [`real-names.md`](../nomination/real-names.md); a person with no verified name is listed by handle.
- Shares are percentages with one decimal.
- A count fed by a capped stream is written `≥ N` and footnoted *"at least N — the search returned more than was fetched"*; any `notes` from `metrics.json` are listed under the candidate.
- Every list and table of people — measured or dropped — is in alphabetical order of GitHub handle, case-insensitive; never by floors met, counts, or any other measure.
- No threshold or reference column, no count of floors met, no score, and no wording that says or implies someone is ready, close, or not ready.
- No email addresses, and no quotes from private material.
