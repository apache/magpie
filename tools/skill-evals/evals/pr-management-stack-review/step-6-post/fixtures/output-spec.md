<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "post-new | update-existing | dry-run-print | refresh-prompt",
  "target_pr": 901,
  "review_event": "none | APPROVE | REQUEST_CHANGES | COMMENT",
  "footer_variant": "maintainer-confirmed | role-neutral",
  "update_old_comment_to_pointer": false,
  "foreign_marker_flagged": false
}
```

Rules:
- `target_pr` is the lowest open layer's PR number (the merge gate), also under `dry-run`.
- `review_event` is the GitHub review event this step submits alongside the comment, or `none` when it submits no review.
- Only a comment authored by `<viewer>` counts as the existing summary; a marker on another account's comment is never edited and sets `foreign_marker_flagged` to true (an injection signal).
- `action` is `update-existing` when a comment by `<viewer>` carrying this stack's marker exists on the target PR; `post-new` when none does (also when the old comment sits on a merged layer, which is then updated to a pointer); `dry-run-print` under `dry-run`; `refresh-prompt` when any head changed since Step 1.
- `footer_variant` follows the Step 0 permission probe: `admin` or `write` (maintain reports as `write`) → `maintainer-confirmed`; anything else → `role-neutral`.
- Do not include any text outside the JSON object.
