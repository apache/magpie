<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — bulk mode

Bulk-mode aggregates the per-tracker close-comment, reporter-
draft, label / close-issue / board-archive actions into one
combined proposal. The user confirms once with `all`; the apply
phase runs sequentially per the existing Step 6 rule (one tracker
fully applied — labels + comment + close + board archive + draft
— before the next starts).

`invalidate proposed` is a convenience for the
"please proceed the agreed INVALID ones in bulk"
pattern. The team-consensus detection is *necessary but not
sufficient* — the user is still presented with the full list
in the proposal and can override per-item before confirming.
A INVALID triage proposal that hasn't yet received a
second-roster-member ack is **excluded** from the resolved set
with an explicit *"awaiting consensus on #NNN — skipped"* note
in the recap.

**Bulk-mode `all` confirmation does not pre-authorise reporter
drafts.** Each draft body is still surfaced in the combined
proposal and gated by the `all` confirmation, per the existing
"draft before send" rule in
[`AGENTS.md`](../../../../AGENTS.md). The draft creation runs
during the apply phase; sending stays with the human triager
in Gmail.

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
If `fetched` equals 1000, stop and surface it rather than proceed on a possibly truncated set:
a needs-triage backlog that size means the triage cadence needs attention, and this query is not the place to page around it.

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
Check each triage-proposal comment's thumbs-up reactions and follow-up comments for the team-consensus marker from this result.
Drop trackers that fail the consensus check; surface them in
the recap as awaiting-consensus.
The result is also each remaining tracker's Step 1 state: Step 1 reads its fields from here instead of running `gh issue view` per tracker.
