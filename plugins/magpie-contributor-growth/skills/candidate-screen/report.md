<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Report

Layout of the `candidate-screen` report.

## Layout

```markdown
# Candidate screen — <upstream> — <since> → <end>

> This report is a floor to help notice candidates. It is never a decision; decisions are the <governance-body>'s.

Thresholds: <source file>, calibrated on <calibrated_on, or "not calibrated">
Sources collected: <list>; not collected: <list, with the reason>
Pool: <N> contributors; pre-filter kept <N>; shortlisted <N> (committer <N>, <governance-body> <N>)

## Summary

| Candidate | Target | Floors met | Community | Automated-work flags |
|-----------|--------|------------|-----------|----------------------|
| <Real Name> ([handle](https://github.com/handle)) | committer | 5 of 6 | +12 / −0 | none |

## <Real Name> ([handle](https://github.com/handle)) — <target>

<Two or three paragraphs: what they built and in which areas; review, mentoring
and community work; factual flags. Every claim links to its evidence.>

### Areas

| Area | PRs merged (adjusted, share) | Reviews (adjusted, share) |
|------|------------------------------|---------------------------|
| <area> | N.N (NN.N %) | N.N (NN.N %) |

### Against the floors

| Dimension | Raw | Discounted | Penalty | Adjusted | Floor | Met |
|-----------|-----|------------|---------|----------|-------|-----|

### Community

<Section per community-signals.md § Reporting.>

## Considered, not shortlisted

| Handle | Floors met | PRs merged | Reviews |
|--------|------------|------------|---------|

## Dropped by the pre-filter

| Handle | Merged PRs | Reviewed PRs |
|--------|------------|--------------|
```

## Rules

- A handle is always a plain link, `[handle](https://github.com/handle)` — never `@handle`, so no one is notified.
- Names follow [`real-names.md`](../nomination/real-names.md); a person with no verified name is listed by handle.
- Shares are percentages with one decimal.
- Candidates are ordered by floors met, then by adjusted merged PRs.
- No email addresses, and no quotes from private material.
