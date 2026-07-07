<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step 5e status-rollup entry

Return a JSON object with these structural assertion fields.

```json
{
  "has_closed_as_invalid_summary": <bool — <details> summary line contains "Closed as invalid">,
  "has_reasoning_quotes": <bool — entry includes verbatim quotes from the team discussion>,
  "has_canned_response_ref": <bool — entry names the canned response template selected in Step 4>,
  "reporter_notification": "draft_created" | "pr_imported_none" | "indeterminate_none",
  "has_project_board_archived": <bool — entry records that the project board item was archived>,
  "has_next_step_terminal": <bool — entry states next step is "none — terminal disposition">,
  "has_bare_issue_numbers": <bool — entry contains bare #NNN without a full URL — should be false>
}
```

`reporter_notification` values:
- `"draft_created"` — entry says a Gmail draft was created and is awaiting review.
- `"pr_imported_none"` — entry says no reporter notification because tracker is PR-imported.
- `"indeterminate_none"` — entry says no notification because import path was indeterminate and user chose silent close.
