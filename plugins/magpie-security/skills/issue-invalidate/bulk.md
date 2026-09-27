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
  --limit 100 \
  --json number,title,comments \
  --jq '.[] | select(.comments | map(.body) | any(
    startswith("**Triage proposal**") and contains("**Proposed disposition: INVALID.**")
  )) | .number'
```

If the result count equals the limit, note that there may be additional results not shown.

Then, per resolved tracker, check the triage-proposal comment's
reactions and follow-up comments for the team-consensus marker
via `gh api repos/<tracker>/issues/comments/<id>/reactions`.
Drop trackers that fail the consensus check; surface them in
the recap as awaiting-consensus.
