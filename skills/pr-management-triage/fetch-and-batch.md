<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Fetch and batch

Every rate-limit problem this skill is going to have, if it has
one, will come from making too many small queries. This file
documents the single batched GraphQL shape the skill uses for
every page of PRs, the **full-pagination loop** that walks the
entire candidate set before classification runs, and the
session-scoped cache that holds the fetched set.

---

## The one query that matters — PR-list + rollup enrichment

On entering Step 1, issue **one** GraphQL query that pulls the
page of PRs, the rollup state for each PR's check run, the
mergeable state, the unresolved-thread count, the commits-behind
count, the latest review per reviewer, and the last handful of
comments.

### Template

```graphql
query(
  $searchQuery: String!,
  $batchSize: Int!,
  $cursor: String
) {
  search(query: $searchQuery, type: ISSUE, first: $batchSize, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number
        title
        url
        createdAt
        updatedAt
        id                     # node_id — needed for mutations
        isDraft
        body                   # raw markdown — carries the pr-triage-fold block (see below)
        mergeable              # MERGEABLE / CONFLICTING / UNKNOWN
        baseRefName
        author { login }
        authorAssociation      # OWNER / MEMBER / COLLABORATOR / CONTRIBUTOR / NONE / FIRST_TIME_CONTRIBUTOR / ...
        labels(first: 30) { nodes { name } }
        commits(last: 1) {
          nodes {
            commit {
              oid
              committedDate
              statusCheckRollup {
                state          # SUCCESS / FAILURE / PENDING / ERROR
                contexts(first: 50) {
                  nodes {
                    __typename
                    ... on CheckRun     { name conclusion status }
                    ... on StatusContext { context state }
                  }
                }
              }
            }
          }
        }
        reviewThreads(first: 30) {
          totalCount
          nodes {
            isResolved
            # `first: 5` rather than `first: 1`: the
            # `unresolved_threads_only_likely_addressed` heuristic in
            # [`classify-and-act.md`](classify-and-act.md) needs
            # to see whether the PR author has replied in-thread
            # after the reviewer's first comment. 5 is the smallest
            # window that catches the typical "reviewer comment →
            # author reply" exchange without blowing GraphQL
            # complexity (30 threads × 5 comments × 20 PRs = 3000
            # nodes, well under the ceiling that `first: 10` here
            # would push us toward).
            comments(first: 5) {
              nodes {
                author { login }
                authorAssociation
                url
                bodyText
                createdAt
              }
            }
          }
        }
        latestReviews(first: 20) {
          nodes {
            state
            author { login }
            authorAssociation
            submittedAt
          }
        }
        comments(last: 10) {
          nodes {
            author { login }
            authorAssociation
            createdAt
            bodyText
          }
        }
        baseRef {
          target {
            ... on Commit { history(first: 1) { totalCount } }
          }
        }
      }
    }
  }
}
```

`$searchQuery` is built from the selector — see
[`#search-query-construction`](#search-query-construction)
below. The typical production shape for the default sweep on
`<upstream>` is:

```text
is:pr is:open repo:<upstream>
-label:"ready for maintainer review"
sort:updated-asc
```

The [stale-ready-label sweep](stale-sweeps.md#sweep-4--stale-ready-for-review-label)
is the one exception that *includes* the label, using the same
batch schema with `label:"ready for maintainer review"`
(positive match) instead of the negative match above. All
other selectors flow through the construction table in
[`#search-query-construction`](#search-query-construction).

### Why this shape

Every field above is consumed by Step 2 (filter, classify, and
pick action). Nothing here is speculative:

- `mergeable` → conflict detection
- `statusCheckRollup` → CI pass/fail + failing-check names for
  grace-period and "static-checks-only" logic
- `reviewThreads` (unresolved + reviewer login) → unresolved-
  thread count + ping targets
- `latestReviews` → stale `CHANGES_REQUESTED` detection and
  `has_collaborator_review` flag (extended grace period)
- `body` → the `pr-triage-fold` managed block (the body-fold
  feedback channel, default `triage_feedback_channel: pr-body`).
  Read for "already triaged" detection when the feedback lives in
  the PR description rather than a comment — the
  [`viewer_triage_fold_present`](classify-and-act.md#viewer_triage_fold_present)
  glossary entry parses its `triaged=` / `head=` metadata. Use the
  **raw `body`** (not `bodyText`): `bodyText` strips HTML comments,
  which would erase the markers.
- `comments(last: 10)` → "already triaged" detection (viewer's
  prior triage comment, the `comment` channel / legacy), "author
  responded after triage" detection, and the
  active-maintainer-conversation pre-filter
  (recent collaborator comment + maintainer-to-maintainer
  `@`-ping detection + author-to-maintainer `@`-ping detection —
  see [`classify-and-act.md#pre-filters`](classify-and-act.md),
  F5a/F5b/F5c)
  — which is why the comment node carries `authorAssociation`
  and `bodyText` in addition to author login
- `baseRef.target.history.totalCount` → commits-behind anchor
  (combined with PR head commit count; see
  [`#commits-behind`](#commits-behind))

### Batch size

Default `$batchSize = 20`. Empirically, requesting 50 aliased
`PullRequest` objects — each expanding `contexts(first: 30)` +
`reviewThreads(first: 10)` + `latestReviews(first: 5)` +
`comments(last: 5)` — trips GitHub's GraphQL complexity ceiling
on `<upstream>` and returns a generic error page ("Unicorn")
instead of JSON. 20 reliably comes back with `cost=3` against
the rate-limit budget. The inner `first:` arguments are the
dominant factor; if you need to widen them, *lower* the outer
batch size first — never raise above 25 without measuring.

### `gh` invocation

```bash
gh api graphql -F searchQuery="$SEARCH" -F batchSize=20 -F cursor="$CURSOR" \
  --field query=@fetch-prs.graphql
```

Use `-F` for integers/strings and `--field query=@file` (read
from a file) for the literal query. The `@file` form is less
fragile than `-f query="$(cat file)"` when the query contains
`$variable` references — the shell would otherwise try to
expand them. Capture the JSON output and parse it with `jq` or
`python3 -c 'import json; ...'` rather than re-querying.

---

## Full-pagination loop

Step 1 of [`SKILL.md`](SKILL.md) walks **every page** of the
candidate set before classification or presentation. Run the
loop serially until `pageInfo.hasNextPage` is false, then hand
the accumulated list to Step 2.

```text
all_prs = []
cursor = null
page = 1
loop:
    result = graphql_call(searchQuery, batchSize=20, cursor=cursor)
    all_prs.extend(result.search.nodes)
    print(f"page {page}: fetched {len(result.search.nodes)} PRs (total: {len(all_prs)})")
    if not result.search.pageInfo.hasNextPage:
        break
    cursor = result.search.pageInfo.endCursor
    page += 1
return all_prs
```

Key invariants:

- **Serial, not parallel.** Pages are issued one after the
  other. Parallel page fetches do not reliably win wall-clock
  time (GitHub serialises against the per-account rate-limit
  budget anyway) and they make rate-limit failures harder to
  reason about. The maintainer steps away during the fetch;
  predictability beats sub-second optimisation.
- **One progress line per page.** Emit a `page N: fetched M
  PRs (total: K)` line per iteration so the maintainer can see
  the loop is advancing if they glance over.
- **No classification, no prompts, no presentation inside the
  loop.** Classification runs once in Step 2 over the entire
  `all_prs` set. Presentation runs once in Step 3 over the
  classified set. The fetch loop is uninterrupted.
- **Skip prefetch heuristics.** With pages fetched serially up
  front, there is no per-page maintainer wait to overlap with
  a next-page prefetch — the old prefetch-during-interaction
  pattern was an optimisation for the per-page model that no
  longer applies.
- **Hard cap.** If a run somehow goes past 50 pages, stop and
  surface to the maintainer. The default selector is
  `is:pr is:open` against `<upstream>`; 50 × 20 = 1000 PRs
  comfortably covers any sane queue, and exceeding that signals
  either a mis-targeted selector or an unhealthy backlog
  worth flagging.

Stash the accumulated `all_prs` in the session cache as
`fetched_prs` (see [`#session-cache`](#session-cache)) before
returning to Step 2 — a re-invocation within the same session
window can reuse the set if the maintainer wants to re-run with
a different action override.

### Per-page accounting

GitHub returns `rateLimit` data alongside each search result.
Log it on each page so a rate-limit failure surfaces its
proximate cause:

```graphql
rateLimit {
  cost
  remaining
  resetAt
}
```

A typical page costs `cost=3`. If `remaining` drops below 100
mid-loop, surface a warning and ask the maintainer whether to
continue or pause; do not silently sleep and retry.

---

## Search-query construction

Translate the selector into the GitHub search query:

| Selector | Query fragment |
|---|---|
| default | `is:pr is:open repo:<repo> sort:updated-asc` |
| `pr:<N>` | `repo:<repo> <N>` *(no need for `is:pr` — the number is unique)* — but prefer the non-search `pullRequest(number: N)` field, it's cheaper |
| `label:<LBL>` (exact) | `label:"<LBL>"` |
| `label:<PAT*>` (wildcard) | omit from search; filter client-side against the returned `labels.nodes.name` list |
| `-label:<LBL>` | `-label:"<LBL>"` |
| `author:<LOGIN>` | `author:<LOGIN>` |
| `review-for-me` | `review-requested:@me` (or `user-review-requested:@me`) |
| `created:>=YYYY-MM-DD` | `created:>=YYYY-MM-DD` |
| `updated:>=YYYY-MM-DD` | `updated:>=YYYY-MM-DD` |

GitHub caps `sort:` at the search level and respects
`updated-asc` (oldest-updated first), which is what you want:
stale PRs surface first, hot-changing PRs hit GitHub's own
cache anyway and surface on a later run.

Always include `is:pr is:open` and the target `repo:<repo>`
explicitly. Never rely on implicit repo context — the skill must
behave identically when invoked from outside a checkout.

For a single-PR invocation (`pr:<N>`), skip `search` entirely
and use the direct `repository(owner, name) { pullRequest(number: N) { ... } }`
query with the same selection set — it's one GraphQL call
regardless and doesn't burn a search-API budget slot (search is
rate-limited more tightly: 30 per minute).

---

## Commits-behind

GitHub's GraphQL doesn't expose "commits behind" directly. The
cheapest approximation is `compareCommits` via the REST API,
but that's one call per PR. Instead, fetch the commits-behind
for the entire page in **one** aliased GraphQL call:

```graphql
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    pr123: pullRequest(number: 123) {
      baseRef { target { ... on Commit { oid history(first: 1) { totalCount } } } }
      headRef { target { ... on Commit { oid history(first: 1) { totalCount } } } }
      # ... repeated for every PR on the page
    }
  }
}
```

This returns totals for the base and head branches — subtract
head-merge-base total from base total to get commits-behind.
Group these aliases into chunks of **20 PRs per aliased query**
(GitHub's alias-per-query cap is around 50, but 20 keeps you
well clear of the complexity budget).

Stash the result on each PR record and use it in both grace-
period logic and comment rendering (e.g. "your branch is 73
commits behind `main`"). Do not call `gh pr view` per PR — that
is the anti-pattern this file exists to prevent.

---

## Mandatory: `action_required` run index per page

Before classification runs, fetch one REST call per page:

```bash
gh api "repos/<owner>/<repo>/actions/runs?event=pull_request&per_page=100" \
  --jq '.workflow_runs[] | select(.conclusion == "action_required")'
```

This lists **every** workflow run across the repo that is
awaiting maintainer approval. Index the response by `head_sha`;
any PR on the current page whose head SHA appears in the index
is `pending_workflow_approval` (see
[`classify-and-act.md#decision-table`](classify-and-act.md), row 1).

**Why the post-filter, not `?status=action_required`.** The
GitHub Actions API returns runs awaiting approval as
`status: "completed"` with `conclusion: "action_required"` (the
run has *finished* the queueing phase and is now blocked
pending approval). The query parameter `?status=action_required`
matches no runs in this state and silently returns an empty
result, which lets `pending_workflow_approval` PRs slip through
classification as `passing`. The post-filter on `conclusion`
is the only correct way to enumerate them.

Why this is mandatory, not "fallback":

- `statusCheckRollup.state` aggregates only **completed**
  check-runs. When a first-time-contributor PR has its real CI
  held in `action_required`, the rollup reports SUCCESS based on
  fast bot checks (`Mergeable`, `WIP`, `DCO`, `boring-cyborg`)
  that run unconditionally.
- Empirically on `<upstream>`, 17 first-time-contributor
  PRs in a single sweep reported `rollup.state == SUCCESS` while
  every real CI workflow was in `action_required`. Trusting the
  rollup classified them all as `passing`.
- The REST call returns ≤ 100 runs at a time and paginates
  cheaply — a single extra round-trip per page is well under the
  rate-limit budget and closes the whole class of false-
  positives.

Walk all pages of `actions/runs` (or at least the first 3, which
covers any reasonable repo-level backlog) and keep the union as
a per-page index. Invalidate the index before fetching the next
PR page — approval state changes fast.

The REST call is the primary signal. The rollup + "real CI
pattern" guard from
[`classify-and-act.md#real-ci-guard`](classify-and-act.md) is the
belt-and-braces second check that protects against a rare case
where the REST call misses a freshly-created run.

---

## Optional: failed-job log snippets (deferred)

When a PR is pulled out of a `draft` group for individual
review, and only then, fetch short log snippets from the failed
jobs to help the maintainer decide:

```bash
gh api repos/<owner>/<repo>/commits/<head_sha>/check-runs?status=failed
# pick the failed run IDs, then:
gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs   # plain text
```

Cap the snippet at 30 lines per job and 5 jobs per PR. This is
the only per-PR call the skill makes in the non-batch path, and
it's gated on "the maintainer is actually looking at this one".
Cache the snippet keyed by `(pr_number, head_sha)` in the
session cache.

---

## Lazy per-PR fetches (drill-in only)

The full-pagination loop in [`#full-pagination-loop`](#full-pagination-loop)
deliberately omits per-PR deep data — failed-job log
snippets, full diffs, author profile rollups — because the
typical pass through the interaction loop never asks for any
of it. Defer those fetches to the moment the maintainer pulls
a PR out of a group via `[P]NN`, `[E]`, or `[W]` on the
per-PR drill-in screen.

The per-PR drill-in is the only place this skill makes a
per-PR call. See [`#optional-failed-job-log-snippets-deferred`](#optional-failed-job-log-snippets-deferred)
for the failed-job log recipe and
[`interaction-loop.md#individual-drill-in-presentation`](interaction-loop.md#individual-drill-in-presentation)
for the drill-in shape.

---

## Session cache

`/tmp/pr-management-triage-cache-<repo-slug>.json` stores intermediate
results so that re-invocations inside a working session skip
anything that isn't needed. Schema:

```json
{
  "viewer": {"login": "potiuk", "permission": "MAINTAIN"},
  "label_ids": {
    "ready for maintainer review": "LA_kwDO..==",
    "closed because of multiple quality violations": "LA_kwDO..==",
    "suspicious changes detected": "LA_kwDO..=="
  },
  "prs": {
    "12345": {
      "head_sha": "abc123...",
      "classification": "deterministic_flag",
      "suggested_action": "rebase",
      "action_taken": "rebase",
      "action_at": "2026-04-22T09:17:03Z"
    }
  },
  "recent_main_failures": {
    "fetched_at": "2026-04-22T08:00:00Z",
    "failing_check_names": ["Helm tests (1.29)", "..."]
  },
  "fetched_prs": {
    "selector": "is:pr is:open repo:<upstream> sort:updated-asc",
    "fetched_at": "2026-04-22T09:18:14Z",
    "pages_fetched": 11,
    "total_prs": 217,
    "all_prs": [
      {"number": 65401, "head_sha": "abc123...", "raw": "<full PR record from Step 1>"}
    ],
    "classified": [
      {"number": 65401, "classification": "deterministic_flag", "action": "draft", "reason": "CI failed + 2 unresolved threads past grace window"}
    ]
  }
}
```

### Invalidation

- An entry's `head_sha` must match the head SHA returned by the
  current fetch — if it doesn't, the contributor pushed since
  and the entry is stale. Drop it and re-classify.
- The `recent_main_failures` block is valid for 4 hours; after
  that, re-fetch via the canary/main-branch failure query
  (see below).
- The `fetched_prs` bundle is the output of one full Step 1
  pass; its `classified` list is validated against live head
  SHAs by the optimistic-lock re-check at execute time (see
  [`interaction-loop.md#optimistic-lock-re-check-before-mutate`](interaction-loop.md#optimistic-lock-re-check-before-mutate)).
  A per-PR head-SHA mismatch triggers an inline re-fetch +
  re-classify of just that PR; the rest of the bundle
  survives. Discard the entire bundle on session exit — do not
  persist across sessions.
- The whole cache is discardable — losing it only costs one
  extra full-pagination round.

### Writing discipline

Write the cache once per group completion, not once per PR.
Writing on every single mutation creates burst disk churn and
— more importantly — makes it easy to leave the cache in an
inconsistent state if the session is interrupted mid-group.
On `Ctrl-C`, flush once on the way out.

---

## Recent main-branch failures (for "is this failure systemic?")

The `suggested_action` computation needs to know which checks are
currently failing across main-branch PRs, so that a PR whose
only failures match the main-branch failures gets suggested for
`rerun` rather than `draft`. Fetch this **once** per session
(cache for 4 hours):

```graphql
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    pullRequests(states: MERGED, orderBy: {field: UPDATED_AT, direction: DESC}, first: 10) {
      nodes {
        number
        mergedAt
        commits(last: 1) {
          nodes {
            commit {
              oid
              statusCheckRollup {
                contexts(first: 50) {
                  nodes {
                    __typename
                    ... on CheckRun { name conclusion }
                    ... on StatusContext { context state }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

Collect the set of `CheckRun.name` values where `conclusion` is
`FAILURE` or `TIMED_OUT` across those 10 recently-merged PRs.
Any failure appearing in ≥2 of them is "systemic". Store the
resulting set in the session cache as `recent_main_failures`.

---

## What not to do

- **Do not call `gh pr view <N>`** in a loop. Each invocation is
  a separate API call; 50 of them = 50 round-trips and 50
  rate-limit points. Use the aliased batch query instead.
- **Do not issue a GraphQL query inside a Python generator** or
  other lazy structure that might hide the call count. All PR
  fetches happen in a small set of named calls — count them and
  keep the count down.
- **Do not parallelise the page loop.** Pages are issued
  serially in [`#full-pagination-loop`](#full-pagination-loop).
  Parallel page fetches do not win wall-clock time against
  GitHub's per-account rate-limit and they make failures
  harder to reason about.
- **Do not interleave fetching with classification or
  presentation.** The full-pagination loop runs to completion
  first; classification runs once over the whole set;
  presentation comes last. Mixing the phases recreates the
  per-page context-switching this design was built to remove.
- **Do not sleep after rate-limit errors.** If a query 403s on
  `X-RateLimit-Remaining: 0`, stop immediately, surface the
  budget info to the maintainer, and let them decide whether to
  pause or retry. Sleeping and retrying in-skill just masks the
  root cause (you are almost certainly mis-batching).
