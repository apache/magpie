<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **recap and hand-off** step of the `security-issue-invalidate` skill.

An apply result is provided below. Produce the recap output and then return a JSON object asserting the structural properties of your recap text.

Return a JSON object with exactly these fields:

```json
{
  "has_tracker_link": true | false,
  "has_closed_not_planned_state": true | false,
  "has_labels_applied": true | false,
  "has_labels_removed": true | false,
  "has_rollup_permalink": true | false,
  "has_closing_comment_permalink": true | false,
  "has_board_status": true | false,
  "has_gmail_draft_ref": true | false,
  "has_handoff_line": true | false,
  "has_bare_issue_numbers": true | false
}
```

Field rules:
- `has_tracker_link`: recap contains a clickable URL to the tracker (not just `#312` — a full `https://github.com/...` URL).
- `has_closed_not_planned_state`: recap states the new state as `closed - not planned` (or equivalent phrasing).
- `has_labels_applied`: recap mentions `invalid` was applied.
- `has_labels_removed`: recap mentions which labels were removed.
- `has_rollup_permalink`: recap contains a link to the rollup comment.
- `has_closing_comment_permalink`: recap contains a link to the closing comment.
- `has_board_status`: recap mentions project board status (`archived` or `not on board`).
- `has_gmail_draft_ref`: recap contains a Gmail draft ID or explicit explanation for no draft (required for both paths — security@-imported shows draft ID; PR-imported shows explicit no-draft note).
- `has_handoff_line`: recap contains the terminal-disposition hand-off line (or close paraphrase of it).
- `has_bare_issue_numbers`: `true` if the recap contains bare issue number references like `#312` without being wrapped in a full URL — this should be `false` (bare numbers are a formatting violation).
