<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **recap and hand-off** step of the `security-issue-import-from-pr` skill.

An apply result is provided. Produce the recap output, then return a JSON object asserting its structural properties.

```json
{
  "has_tracker_link": true | false,
  "has_pr_url": true | false,
  "has_board_column": true | false,
  "has_labels": true | false,
  "has_milestone": true | false,
  "has_rollup_permalink": true | false,
  "has_handoff_line": true | false,
  "has_bare_issue_numbers": true | false
}
```

Field rules:
- `has_tracker_link`: recap contains a clickable full URL to the new tracker.
- `has_pr_url`: recap includes the PR URL it was imported from.
- `has_board_column`: recap states `Assessed` as the board column.
- `has_labels`: recap lists the labels applied.
- `has_milestone`: recap includes the milestone (or explicit note if none was set).
- `has_rollup_permalink`: recap contains a link to the status-rollup comment.
- `has_handoff_line`: recap contains the next-step hand-off pointing to security-cve-allocate.
- `has_bare_issue_numbers`: `true` if tracker references appear as bare `#NNN` without a surrounding full URL — should be `false`.
