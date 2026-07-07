<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step 2a observed state

Return a JSON object summarising the observed tracker state. This is an exact-match assertion.

```json
{
  "process_step": <integer — the process step number the tracker is currently at>,
  "labels": [<string> ...],
  "milestone": <string or null>,
  "has_assignee": <bool>,
  "linked_pr_state": "merged" | "open" | "none",
  "thread_status": "known" | "pr_imported" | "unknown",
  "has_bare_issue_numbers": <bool — summary contains bare #NNN without a full URL — should be false>
}
```

Rules:
- `process_step` matches the step number identified in Step 1f.
- `labels` is the exact list of current labels on the tracker, in the order they appear in the input.
- `milestone` is the exact milestone string, or null if none is set.
- `has_assignee` is true when at least one assignee is set on the tracker.
- `linked_pr_state`: "merged" if the fix PR has merged, "open" if it is still open, "none" if no fix PR is linked.
- `thread_status`: "known" if a Gmail thread ID or mailing list URL is recorded in the body, "pr_imported" if the sentinel "N/A — opened from public PR" is present, "unknown" if the field is blank or `_No response_`.
- `has_bare_issue_numbers` must be false — any `#NNN` in the prose summary not wrapped in a full URL is a violation.
