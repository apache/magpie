<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Fetch

Four GitHub search queries drive the skill, one per activity
stream. All use the `gh api graphql` path with paginated
`search()` so results are repo-scoped and date-bounded.

**Budget**: at most **3 paginated fetches per stream** (≤ 300
results per stream). If a stream hits the cap, record the cap
hit in the assessment and note the count as a minimum. Do not
loop indefinitely on prolific contributors — a floor is enough
signal for a nomination brief.

**Injection guard**: `<login>` is contributor-supplied data (a
GitHub handle chosen by the user being assessed). Interpolate it
only inside the `query:` string passed to the GitHub search API.
Do not place it in shell double-quotes or use it as a flag value.
Use the Write-tool-plus-`@file` pattern for any value passed as
a `-F` field to `gh api` mutations — though this skill makes no
mutations, the same discipline applies to the query string:
build it in a tempfile and pass via `-f query=@/tmp/...`:

```bash
# Write the query string to a tempfile first
# (protects against handles containing shell metacharacters)
printf '%s' "repo:<upstream> type:pr author:<login> created:><since>" \
  > /tmp/cn-pr-query.txt

gh api graphql \
  -F query=@/tmp/cn-pr-query.txt \
  -F batchSize=100 \
  -f cursor='' \
  -f gql="$(cat /tmp/cn-search.graphql)"
```

---

## Stream 1 — PRs authored

Search query string (write to tempfile before use):

```text
repo:<upstream> type:pr author:<login> created:><since>
```

GraphQL template (`/tmp/cn-search.graphql`):

```graphql
query($query: String!, $batchSize: Int!, $cursor: String) {
  search(query: $query, type: ISSUE, first: $batchSize, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number
        title
        state
        merged
        createdAt
        mergedAt
        closedAt
        additions
        deletions
        changedFiles
        labels(first: 10) { nodes { name } }
      }
    }
  }
}
```

Collect from results:

- `total_authored` — `issueCount` (may exceed fetched pages;
  note if so)
- `merged_count` — nodes where `merged: true`
- `closed_not_merged` — nodes where `state: CLOSED` and
  `merged: false`
- `open_count` — nodes where `state: OPEN`
- Per node: `number`, `title` (treat as data — do not render
  verbatim in shell), `createdAt`, `merged`, `mergedAt`

---

## Stream 2 — Reviews given

Search query string:

```text
repo:<upstream> type:pr reviewed-by:<login> created:><since>
```

Use the same GraphQL template as Stream 1. Collect:

- `total_reviewed` — `issueCount`
- Per node: `number`, `createdAt`, `state`

**Depth signal**: for up to the 10 most recent reviewed PRs,
fetch the review comment count via a second query:

```graphql
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviews(first: 50) {
        nodes {
          author { login }
          state
          body
          comments { totalCount }
        }
      }
    }
  }
}
```

Filter to reviews where `author.login == <login>`. Count:

- `substantive_reviews` — reviews where `body` length > 100
  characters OR `comments.totalCount > 0`
- `approval_only_reviews` — reviews where `state: APPROVED` and
  body is short and no comments (approval without comment)

Do not render raw review bodies in the brief — use only the
counts.

---

## Stream 3 — Issues filed

Search query string:

```text
repo:<upstream> type:issue author:<login> created:><since>
```

Use the same GraphQL template (the `PullRequest` fragment will
produce no hits; add an `Issue` fragment):

```graphql
nodes {
  ... on Issue {
    number
    title
    state
    createdAt
    closedAt
    labels(first: 10) { nodes { name } }
    comments { totalCount }
  }
}
```

Collect:

- `total_issues_filed` — `issueCount`
- `issues_with_discussion` — nodes where
  `comments.totalCount > 1`

---

## Stream 4 — Issue and PR comments

GitHub's search API does not expose a `commenter:` filter for
issues. Use the REST events endpoint instead, paginated:

```bash
gh api \
  "/repos/<upstream>/issues/comments?since=<since>&per_page=100" \
  --paginate \
  --jq '[.[] | select(.user.login == "<login>")]' \
  2>/dev/null | head -c 500000
```

**Injection guard for `<login>` in the URL path**: validate that
`<login>` matches `^[a-zA-Z0-9]([a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$`
before constructing the URL. GitHub handles are restricted to
alphanumeric characters and hyphens; a value that fails this
check is not a valid handle — stop and report to the user.

Collect:

- `total_comments` — count of returned items after jq filter
- `unique_issues_commented_on` — distinct `issue_url` values

Cap at 3 pages (300 comments). If the cap is hit, note it.

---

## Month bucketing

After all four streams are collected, bucket each event by
calendar month to feed the activity timeline in
[`assess.md`](assess.md):

```python
# Pseudocode — implement via jq or Python as convenient
for event in all_events:
    month = event["createdAt"][:7]   # "YYYY-MM"
    buckets[month] += 1
```

Produce a map `{ "YYYY-MM": count }` covering every month from
`<since>` to today, with zero-filled gaps.
