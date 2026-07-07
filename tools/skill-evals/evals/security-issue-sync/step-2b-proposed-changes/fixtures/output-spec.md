<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **proposed changes** step of the `security-issue-sync` skill.

The observed state (current tracker) vs. gathered state (PR, milestone, assignee signals) is provided. Produce the numbered proposal and return a JSON object asserting its structure.

```json
{
  "items": [
    {
      "number": 1,
      "category": "labels" | "milestone" | "assignee" | "body_field" | "status_comment",
      "action": "<string>",
      "reason": "<string>"
    }
  ],
  "labels_to_add": ["<string>"],
  "labels_to_remove": ["<string>"],
  "milestone_create_needed": true | false,
  "assignee_proposed": "<string or null>",
  "has_bare_issue_numbers": true | false
}
```

Field rules:
- `items`: every proposed change as a numbered item with category, action, and reason. Propose an item ONLY when the target state differs from the observed tracker state — never restate something already correct (a label already present, a milestone already set to the target, an assignee already set). Specifically:
  - **Labels:** only add/remove labels that actually change the current set. Do not re-add a scope label (`airflow` / `providers` / `chart`) that is already present. Do not remove `needs triage` until triage is complete (a CVE has been allocated or the fix PR has merged). Only flip `pr created` ↔ `pr merged` when the PR's state has actually changed.
  - **Milestone:** if the required milestone already exists on the tracker repo, set `milestone_create_needed` to `false` and only propose *assigning* it when the tracker currently has none.
  - **Assignee:** propose an assignee only at the PR-merged hand-off step, and only when the tracker currently has no assignee. While the fix PR is still open, propose no assignee (`assignee_proposed` is `null`).
  - **`status_comment` items** fire only on specific triggers, never to narrate routine progress. At the `pr created` → `pr merged` transition (process step 11), propose a fill-fields status comment ONLY if one of the six mandatory body fields — CWE, Affected versions, Severity, Reporter credited as, Short public summary for publish, PR with the fix — is empty or `_No response_`. If all six are populated (or the gathered state does not flag any missing), propose no status comment for the transition. (Disclosure-overdue and distributor pre-announcement status comments keep their own separate triggers.)
  - **No speculative labels.** Add `cve allocated` only once a CVE has actually been allocated; do not add `pr created` / `pr merged` before the process reaches those transitions. At an assessed / pre-CVE tracker (process step ~6), the usual sole change is the milestone — propose no label add or remove.
- `labels_to_add` / `labels_to_remove`: flat lists of all label changes across all items.
- `milestone_create_needed`: `true` when the required milestone does not yet exist on the tracker and a `gh api` create call is included in the proposal.
- `assignee_proposed`: the GitHub handle proposed for assignee, or `null`. Only propose a security-team collaborator, never an external reporter.
- `has_bare_issue_numbers`: `true` if any item contains a bare `#NNN` without a full URL — should be `false`.
- `overdue_for_disclosure_proposed`: `true` when `items` contains an escalation item due to the CVD window expiring. Optional field — omit (or set `false`) when the tracker is not overdue.
- `distributor_notify_proposed`: `true` when `items` contains a distributor pre-announcement draft proposal. Optional field — omit (or set `false`) when `pre_announce_distributors` is `false` or the fix is not yet in a pending release.
