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

Repositories: <every project repository measured>; inactive in the window: <list, or "none">
Thresholds: <source file>, calibrated on <calibrated_on, or "not calibrated">
Sources collected: <list>; not collected: <list, with the reason>
Pool: <N> contributors; pre-filter kept <N> (committer <N>, <governance-body> <N>)
Details links open live searches; the counts in each section were measured at <end>.

## People

- [<Real Name> (handle)](#<anchor of their section>) — <target>

## Summary of findings

<One or two paragraphs describing what was found across the list — kinds
of work, areas, sources not collected. No comparison between people or with
any threshold, no ordering, no readiness judgement.>

## <Real Name> ([handle](https://github.com/handle)) — <target>

Details: [merged PRs](<search URL>) · [reviewed PRs](<search URL>) · [issues filed](<search URL>) · [commented](<search URL>)

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

## Details links

Every person's section opens with a **Details** line linking to live code-host searches of their activity in the window, so a reader can open the full lists behind the counts.
Each link is one search covering every project repository the screen measured (Step 1) — `<upstream>` and, for an ASF project, every other repository of the project active in the window.
On GitHub, each is `https://github.com/search?type=<type>&q=<query>`, with spaces in the query written as `+` and one `repo:<owner>/<name>` qualifier per repository:

| Link | `type` | Query |
|------|--------|-------|
| merged PRs | `pullrequests` | `repo:<r> is:pr is:merged author:<handle> merged:<since>..<end>` |
| reviewed PRs | `pullrequests` | `repo:<r> is:pr reviewed-by:<handle> -author:<handle> updated:>=<since>` |
| issues filed | `issues` | `repo:<r> is:issue author:<handle> created:<since>..<end>` |
| commented | `issues` | `repo:<r> commenter:<handle> updated:>=<since>` |

For example, for `kshah` on `apache/example-project` from 2026-03-26 to 2026-09-25, the merged-PRs link is
`https://github.com/search?type=pullrequests&q=repo:apache/example-project+is:pr+is:merged+author:kshah+merged:2026-03-26..2026-09-25`.

- The links show the live state, so they can differ slightly from the counts measured at `<end>`, which stay authoritative; the report says so once, under the header.
- Links never search by email address, so there is no mailing-list search link; the person's mailing-list work is linked message by message in their Community section.
- The **Details** line is links only — no counts or comments of its own.
