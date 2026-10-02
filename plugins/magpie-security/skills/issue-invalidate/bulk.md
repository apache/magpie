<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — bulk mode

Bulk mode aggregates each tracker's closing comment, reporter draft, labels, close and board archive into one combined proposal.
The user confirms once with `all`; Step 6 then applies one tracker fully before the next starts.

`invalidate proposed` serves the "please proceed the agreed INVALID ones in bulk" pattern.
Team consensus is *necessary but not sufficient*: the user still sees the full list in the proposal and can override per item before confirming.
An INVALID triage proposal without a second roster member's ack is **excluded** from the resolved set, with an explicit *"awaiting consensus on #NNN — skipped"* note in the recap.

**Bulk-mode `all` confirmation does not pre-authorise reporter drafts.** Each draft body is still surfaced in the combined proposal, per the "draft before send" rule in
[`AGENTS.md`](../../../../AGENTS.md).
Drafts are created during apply; sending stays with the triager in Gmail.

**Resolution recipe for `invalidate proposed`:**

```bash
# Find open trackers with a INVALID triage proposal
gh issue list --repo <tracker> --state open --label "needs triage" \
  --limit 1000 \
  --json number,title,comments \
  --jq '{fetched: length, matches: [.[] | select(.comments | map(.body) | any(
    startswith("**Triage proposal**") and contains("**Proposed disposition: INVALID.**")
  )) | .number]}'
```

The `--limit 1000` matches [`security-issue-triage`](../issue-triage/SKILL.md) Step 1's full-set fetch.
If `fetched` equals 1000, stop and surface it rather than proceed on a possibly truncated set: a backlog that size is a triage-cadence problem.

Then fetch the consensus inputs and the Step 1 state for every match in one batched read — one aliased GraphQL query per chunk of up to 20 trackers (⌈M/20⌉ round-trips for M matches), not a reactions call and a `gh issue view` per tracker.
Write the query with the Write tool to a scratch file — it holds only issue numbers and the `<tracker>` owner/name — and run it as a plain `gh api graphql -F query=@<file>`:

```graphql
query {
  repository(owner: "<owner>", name: "<repo>") {
    i<N1>: issue(number: <N1>) {
      number title body state url
      labels(first: 30) { nodes { name } }
      milestone { title }
      assignees(first: 10) { nodes { login } }
      comments(first: 100) {
        nodes {
          databaseId author { login } createdAt body
          reactions(first: 50, content: THUMBS_UP) { nodes { user { login } } }
        }
      }
    }
    # repeat one aliased block per matched tracker in the chunk
  }
}
```

The same query serves an explicit-list selector (`invalidate #N1, #N2, …`), minus the consensus check.
Check each triage-proposal comment's thumbs-up reactions and follow-up comments in this result for the team-consensus marker.
Drop trackers that fail the consensus check, and surface them in the recap as awaiting consensus.
The result is also each remaining tracker's Step 1 state: Step 1 reads its fields from here instead of running `gh issue view` per tracker.
