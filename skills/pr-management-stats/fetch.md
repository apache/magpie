<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Fetch

Two GraphQL shapes drive the whole skill: one for the currently-open PRs, one for the closed/merged PRs that were triaged within the cutoff window. Both are paginated with `after: <cursor>` and must follow the "one query per batch" rule from [`SKILL.md`](SKILL.md#golden-rules).

---

## Open PRs

Fetch every open PR on `<repo>` in pages of 50. This feeds Table 2 (Triaged still-open) and also supplies the denominators for the legend/context line.

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
        url
        createdAt
        isDraft
        body                   # raw markdown — carries the pr-triage-fold block (body-fold triage channel)
        author { login }
        authorAssociation
        labels(first: 30) { nodes { name } }
        commits(last: 1) {
          nodes {
            commit {
              oid
              committedDate
            }
          }
        }
        comments(last: 25) {
          nodes {
            author { login }
            authorAssociation
            createdAt
            body
          }
        }
        latestReviews(last: 10) {
          nodes { author { login } state submittedAt }
        }
        reviewThreads(first: 30) {
          nodes {
            isResolved
            comments(first: 3) {
              nodes { author { login } authorAssociation createdAt body }
            }
          }
        }
        timelineItems(last: 50, itemTypes: [LABELED_EVENT, READY_FOR_REVIEW_EVENT, CONVERT_TO_DRAFT_EVENT]) {
          nodes {
            ... on LabeledEvent { createdAt actor { login } label { name } }
            ... on ReadyForReviewEvent { createdAt actor { login } }
            ... on ConvertToDraftEvent { createdAt actor { login } }
          }
        }
      }
    }
  }
}
```

**These engagement fields are not optional.** `latestReviews`,
`reviewThreads`, and `timelineItems` are required by the `is_engaged`
predicate in [`classify.md`](classify.md). Dropping any of them
under-counts engagement and over-counts untriaged PRs — see
[Why no `statusCheckRollup` / `mergeable` — and why `reviewThreads`
IS required](#why-no-statuscheckrollup--mergeable--and-why-reviewthreads-is-required)
below for the rationale. `comments(last: N)` uses **25** here (not 10)
so the marker scan reliably finds the QC-marker comment on chatty PRs.

### `searchQuery`

```text
is:pr is:open repo:<repo> sort:created-asc
```

Sort is `created-asc` (oldest PR first) so the age-bucket counts accumulate deterministically — same PR always lands in the same row in a re-run. `is:pr` filters out issues in the same search.

### `gh` invocation

```bash
gh api graphql \
  -F searchQuery="is:pr is:open repo:<repo> sort:created-asc" \
  -F batchSize=50 \
  -F cursor="$CURSOR" \
  --field query=@/tmp/pr-management-stats-open.graphql
```

### Batch size

**30** is the default. The open-PR selection set now includes the four
engagement signals (`comments(last:25)`, `latestReviews`, `reviewThreads`,
`timelineItems`) the `is_engaged` predicate needs — that costs ~11
complexity points per 30 PRs, well under the budget. Empirically `50`
also works but is borderline; if a response returns
`"errors": [{"type": "MAX_NODE_LIMIT_EXCEEDED", ...}]`, drop to 20.

---

## Closed-merged-triaged PRs

Table 1 needs PRs that were closed or merged since the cutoff date AND had a triage comment posted at some point in their lifetime. Use GitHub's search with an `-is:open` filter plus a `closed:>=<cutoff>` date predicate, then client-side scan the `comments` subfield for the `Pull Request quality criteria` marker.

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
        url
        closedAt
        mergedAt
        state
        merged
        isDraft
        body                   # raw markdown — carries the pr-triage-fold block (body-fold triage channel)
        author { login }
        authorAssociation
        labels(first: 30) { nodes { name } }
        comments(last: 25) {
          nodes {
            author { login }
            authorAssociation
            createdAt
            body
          }
        }
      }
    }
  }
}
```

Notice `comments(last: 25)` — higher than the 10 used for open PRs because a triaged PR that was then closed will often have extra follow-up comments; we still need to find the original triage marker. If the marker isn't in the last 25 comments for a given PR, drop that PR from Table 1 (it wasn't triaged by the bot/viewer convention).

### Why `body`, not `bodyText`, for the comment fetch

GitHub's GraphQL exposes two fields for a comment:

- `bodyText` — plain-text rendering; HTML comments (`<!-- … -->`) are **stripped**.
- `body` — raw Markdown as stored; HTML comments are preserved.

The now-removed `breeze pr auto-triage` command posted *staleness-close* comments with the marker embedded as an HTML comment, and those comments are still present on PRs that were triaged before the command was removed:

```markdown
This pull request has had no activity from the author for over 4 weeks.
@<author>, you are welcome to reopen this PR when you are ready to continue working on it. Thank you for your contribution!

<!-- Pull Request quality criteria -->
```

In this case the visible body contains no "Pull Request quality criteria" text at all — the only marker is the HTML comment at the bottom. Running the same marker match against `bodyText` misses these entirely. A spot-check on a 40-PR sample from `<upstream>` found ~10% of triaged-marker comments were HTML-comment-only: invisible to a `bodyText`-based search.

**Always use `body`, not `bodyText`.** The marker detection is a simple substring search for `Pull Request quality criteria` against the raw body — it matches both:

- the visible `[Pull Request quality criteria](https://…)` link that the `pr-management-triage` skill (and the removed breeze violations-triage) emits, and
- the `<!-- Pull Request quality criteria -->` HTML comment that the removed breeze staleness-triage embedded as a hidden marker (still present on legacy triaged PRs).

Raw bodies are slightly noisier (Markdown formatting characters) but the marker string is distinctive enough that false positives are not a concern on `<upstream>`.

**The marker can now also live in the PR's own `body`, not just a comment.** Under the default `triage_feedback_channel: pr-body`, the `pr-management-triage` skill folds violations feedback into the PR description (a `pr-triage-fold` block) rather than posting a comment — the denoise change (see [`pr-management-triage/rationale.md`](../pr-management-triage/rationale.md#why-fold-feedback-into-the-pr-body-denoise)). The folded block still contains the `Pull Request quality criteria` link, so the PR-level `body` field (added to the fetch queries above) must be scanned with the same substring match as the comment bodies. A PR is triaged if the marker appears in **any** comment body **or** the PR body.

### Known limitation

Two GitHub-search behaviours conspire to make Table 1 hard to get right:

1. **`issueCount` for closed/merged searches is heavily under-reported.**
   Empirically on `<upstream>` (2026-04), the GraphQL `search` query
   `is:pr is:merged repo:<upstream> merged:>=2026-04-01` returns
   `issueCount: 37` while the REST `/pulls?state=closed` endpoint shows
   ~30 PRs merged in the last 24 hours alone. The search index appears to
   rebuild slowly (daily-ish) and results are capped in a way that
   `issueCount` doesn't reflect. **Never use the search `issueCount` as a
   denominator** — it's a biased sample.
2. **Full-text search for `"Pull Request quality criteria"` is even worse.**
   The same `<upstream>` repo shows only 164 PRs when searched by the
   marker string, despite that exact phrase being posted on dozens of PRs
   per day by the triage skill. Free-text indexing clearly lags.

The **default Table 1 path is the hybrid REST + aliased-GraphQL fetch**, not the free-text search. The search variant is kept only as a `fast-closed` opt-in for maintainers who want a quick approximation and accept the undercount.

### Hybrid path (default)

Two stages:

1. **Enumerate** the closed / merged set since cutoff using the REST `/pulls?state=closed&sort=updated&direction=desc` endpoint. Paginate until the oldest PR on a page has `closed_at < cutoff`, then stop. Filter out bot authors (`*[bot]`, `dependabot`, `github-actions`) at this stage — bots never carry the triage marker. Budget: about one REST call per 100 PRs (~20 calls for a 6-week `<upstream>` window yielding ~2000 closed-since PRs, ~1600 after bot filter).

2. **Fetch comments in aliased batches** of **30 PRs per GraphQL call**. Each alias queries one PR with `comments(last: 25) { nodes { author { login } authorAssociation createdAt body } }`. A single query with 30 aliases stays well inside GitHub's complexity budget; larger batch sizes occasionally hit `MAX_NODE_LIMIT_EXCEEDED`. Budget: ~54 GraphQL calls for 1600 PRs; end-to-end around 60 seconds on a warm token.

```graphql
query {
  repository(owner:"apache",name:"airflow") {
    pr63407: pullRequest(number:63407) {
      number author{login} authorAssociation closedAt mergedAt state merged
      labels(first:30){nodes{name}}
      comments(last:25){nodes{author{login} authorAssociation createdAt body}}
    }
    pr63914: pullRequest(number:63914) { … }
    # … 30 aliases per query
  }
}
```

For each returned PR, apply the same marker check as [`classify.md`](classify.md) — the `Pull Request quality criteria` substring in a comment's raw `body` (author in `OWNER/MEMBER/COLLABORATOR`), **or** a `pr-triage-fold` block in the PR's own `body` (the default body-fold channel). Record `responded_before_close` when the author has a comment after the triage marker and on or before `closedAt`.

Empirical delta on `<upstream>`, cutoff 2026-03-11:

| Path | Triaged+closed PRs found |
|---|---|
| Free-text search (`fast-closed`) | 28 — heavily under-reported |
| Hybrid (default) | **204** — 7.3× higher, actual count |

### `fast-closed` opt-in

When the maintainer explicitly asks for a quick approximation (`fast-closed` flag, or in a low-budget context), fall back to the search-based path:

```text
is:pr -is:open repo:<repo> closed:>=<cutoff> sort:updated-desc
```

The fast path must print a clear caveat above Table 1: *"fast-closed mode: Table 1 uses the free-text search index which currently undercounts older triaged+merged PRs on `<upstream>`. Re-run without `fast-closed` for accurate numbers."*

### `searchQuery`

```text
is:pr -is:open repo:<repo> closed:>=<cutoff> sort:updated-desc
```

`-is:open` matches both `closed` and `merged` states. `closed:>=` is GitHub's search qualifier for closed/merged date. `sort:updated-desc` keeps the most recent final actions at the top (so Ctrl-C'ing a long pagination returns the freshest portion).

### `gh` invocation

```bash
gh api graphql \
  -F searchQuery="is:pr -is:open repo:<repo> closed:>=2026-03-11 sort:updated-desc" \
  -F batchSize=50 \
  -F cursor="$CURSOR" \
  --field query=@/tmp/pr-management-stats-closed.graphql
```

### Cutoff default

If the maintainer doesn't pass `since:<date>`, default to six weeks ago:

```bash
cutoff=$(date -u -d "-42 days" +%Y-%m-%d)
```

Six weeks covers ~a sprint-and-a-half, which is long enough to smooth out day-to-day variation in closures without being so far back that the numbers lose meaning.

---

## Paginating

Both queries follow the same pattern:

```bash
cursor=null
while : ; do
  out=$(gh api graphql -F cursor="$cursor" …)
  # append out.data.search.nodes to the accumulator
  hasNext=$(echo "$out" | jq -r '.data.search.pageInfo.hasNextPage')
  cursor=$(echo  "$out" | jq -r '.data.search.pageInfo.endCursor')
  [ "$hasNext" = "true" ] || break
done
```

Two safety valves:

- Cap the accumulator at 2000 PRs per query. If the repo really has that many open PRs, the maintainer needs a narrower selector (`label:area:scheduler`, for example) — surface the cap and stop.
- If a single page returns fewer nodes than `batchSize` *and* `hasNextPage == true`, keep going — GitHub sometimes returns short pages legitimately. Never break on a short page alone.

---

## Parsing the response — Python 3.14 strict mode

Python 3.14's `json` module raises `JSONDecodeError: Invalid control
character` on strings containing raw control characters (tabs,
newlines, `\xHH` escapes that don't map to valid JSON escapes).
GitHub's API returns comment `bodyText` fields that routinely contain
such characters, so a naive `json.load(stdin)` fails.

Use one of the following, whichever matches the pipeline:

- `json.load(fp, strict=False)` — relaxes the control-character check;
  the parser accepts raw tabs / newlines inside strings.
- `gh api ... --jq '.'` — `gh` piping through its built-in `jq` handles
  the data without going through Python's strict JSON parser.
- Save the response to a file first and re-read: `gh api ... > /tmp/x.json && python3 -c "import json; d=json.load(open('/tmp/x.json'), strict=False)"`. Avoids shell-escape interactions that can mangle the stream.

Do **not** try to clean the JSON by replacing `\n` → `\\n` before
parsing — the replacement misses genuine escape sequences elsewhere
in the payload and silently corrupts bodies. Use `strict=False`.

On REST responses that contain a PR body with an invalid JSON escape
sequence (e.g. `\z`, `\e`), even `strict=False` fails with
`Invalid \escape`. These are rare but possible — fall through to
`gh api --jq` for those calls.

---

## Ready-label timeline

Needed for the dashboard's "Ready-for-review trend" chart (see [`aggregate.md#ready-for-review-trend-by-top-areas`](aggregate.md#ready-for-review-trend-by-top-areas)). The open-PRs query above tells us *which* PRs currently carry the `ready for maintainer review` label, but not *when* the label was added. Without that timestamp the trend chart can't show growth.

Run an aliased GraphQL query, **30 PRs per call**, that fetches each PR's `LabeledEvent` timeline filtered to the relevant label:

```graphql
query {
  repository(owner:"<owner>",name:"<name>") {
    pr12345: pullRequest(number:12345) {
      number
      timelineItems(last:50, itemTypes:[LABELED_EVENT]) {
        nodes {
          ... on LabeledEvent {
            createdAt
            label { name }
          }
        }
      }
    }
    # … repeated for the other 29 PRs in the batch
  }
}
```

Per-PR processing: pick the most recent `LabeledEvent` whose `label.name == "ready for maintainer review"`. That `createdAt` is the PR's `ready_at` timestamp. PRs that never had the label (shouldn't happen — input set is filtered to currently-labelled PRs) are dropped silently.

`itemTypes:[LABELED_EVENT]` is critical — without it the timeline returns every event (commits, comments, reviews) and blows the complexity budget. With the filter, the per-PR cost is tiny.

Budget: ~7 GraphQL calls for ~200 currently-ready PRs on `<upstream>`. Well under the per-session ceiling.

Cache the per-PR `ready_at` in `/tmp/pr-management-stats-cache-<repo-slug>.json` keyed by `(pr_number, head_sha)` — same convention as the rest of the cache. The label-add timestamp is stable across head SHAs (it's a label event, not a commit event), so the cache hit rate is high.

---

## PR changed files (CODEOWNERS panel)

For the [`#ready-for-review-queue-by-codeowner`](aggregate.md#ready-for-review-queue-by-codeowner) panel, fetch each currently-ready PR's changed file paths. Aliased GraphQL, **20 PRs per call** (the `files` connection on each PR returns up to 100 paths — `files(first:100)`).

```graphql
query {
  repository(owner:"<owner>",name:"<name>") {
    pr12345: pullRequest(number:12345) {
      number
      files(first:100) {
        nodes { path }
        pageInfo { hasNextPage }
      }
    }
    # … repeated for the other 19 PRs in the batch
  }
}
```

Per-PR processing: collect the `path` list. If `pageInfo.hasNextPage == true` the PR has > 100 changed files — record it in the truncation log and proceed with the first 100 (overwhelmingly enough for CODEOWNERS matching). For most projects 100 is far above the median changed-file count.

Cache per `(pr_number, head_sha)` — file lists rarely change without a new commit so the cache hit rate is high on re-runs.

Budget: ~8 GraphQL calls for ~150 currently-ready PRs on a busy project. Skip the panel entirely if `.github/CODEOWNERS` is absent (no fetch necessary).

### Reading `.github/CODEOWNERS`

The CODEOWNERS file is read from the local checkout — same `<adopter-repo>` the skill is running in. Look at:

1. `.github/CODEOWNERS` (most common — GitHub's default location)
2. `CODEOWNERS` (repo root — also recognised by GitHub)
3. `docs/CODEOWNERS` (last GitHub-recognised location)

The first existing path wins. If none exist, skip the panel.

Parse line-by-line: a non-comment, non-blank line is `<pattern> <owner1> <owner2> ...`. Strip inline `#`-comments before splitting. Owners start with `@` (individual logins) or `@<org>/<team>` (team handles). Rules apply in declaration order; matching is **last-match-wins** per GitHub semantics. See
[`aggregate.md#ready-for-review-queue-by-codeowner`](aggregate.md#ready-for-review-queue-by-codeowner) for the glob-to-regex translation.

---

## Why no `statusCheckRollup` / `mergeable` — and why `reviewThreads` IS required

`statusCheckRollup` and `mergeable` are not needed for stats — those drive
per-PR classification in `pr-management-triage` but aggregate counts don't use
them. Dropping them keeps the query lighter, which is how we can run a larger
`batchSize` here (30–50) than in `pr-management-triage` (20).

`reviewThreads`, `latestReviews`, and `timelineItems` (for
`LABELED_EVENT`/`READY_FOR_REVIEW_EVENT`/`CONVERT_TO_DRAFT_EVENT`), **on the
other hand, ARE required** for stats — the `is_engaged` predicate in
[`classify.md`](classify.md) counts maintainer engagement across:

- issue comments (`comments`) — already included
- submitted reviews (`latestReviews`) — required
- line-level review comments (`reviewThreads`) — required
- label adds + draft conversions by maintainers (`timelineItems`) — required

A maintainer who left only a line-level review comment (no issue comment, no
submitted review) would otherwise look like "no engagement" and the PR would
be misclassified as untriaged. On a large queue the under-count is material —
on `<upstream>` (~530 open PRs at the time of writing) it inflates the untriaged count by ~10×.

(An earlier iteration of this doc claimed `reviewThreads` was not needed for
stats; that was a documentation bug. The current schema in the OPEN_PRS_QUERY
template above includes all four engagement signals. The same fix is encoded
in the reference implementation at
[`tools/pr-management-stats/reference.py`](../../tools/pr-management-stats/reference.py).)

If a future stats column ever needs `statusCheckRollup` or `mergeable`, raise
only that query's complexity — don't pull them into the default shape "just
in case".

---

## Scratch cache

`/tmp/pr-management-stats-cache-<repo-slug>.json` (where slug is `<owner>__<name>`):

```json
{
  "viewer": {"login": "potiuk"},
  "fetched_at": "2026-04-23T10:00:00Z",
  "open_prs": { "12345": {"head_sha": "…", "classification": "triaged_waiting"} },
  "closed_since_cutoff": {
    "cutoff": "2026-03-11",
    "fetched_at": "2026-04-23T10:00:00Z",
    "prs": { "12300": {"state": "MERGED", "responded_before_close": true, "areas": ["scheduler"]} }
  }
}
```

### Invalidation

- The open-PRs block is valid while `fetched_at` is within the last 15 minutes. After that it's re-fetched (queue state changes fast — a sweep in the other window could have moved 50 PRs).
- The closed-since block is keyed by `cutoff` — if the maintainer supplies a different cutoff, fetch fresh.
- `clear-cache` on invocation drops the whole file.

### Writing discipline

Write once at the end of the full run, not after each page. A half-written cache from a Ctrl-C mid-paginate is harder to reason about than a missing cache.
