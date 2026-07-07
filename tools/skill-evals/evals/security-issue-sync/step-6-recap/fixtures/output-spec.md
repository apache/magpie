<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 6 (recap) in isolation. The post-apply state is
provided in the user turn as mock data. Compose the recap and return ONLY
valid JSON with these structural assertion fields:

```json
{
  "has_tracker_link": true | false,
  "has_status_comment_anchor": true | false,
  "has_cve_json_anchor": true | false,
  "has_milestone_link": true | false,
  "has_gmail_draft_ref": true | false,
  "has_next_step": true | false,
  "has_bare_issue_numbers": false
}
```

- `has_tracker_link`: true if the recap contains a clickable Markdown link
  to the tracker issue (`.../issues/<N>` form).
- `has_status_comment_anchor`: true if the recap links to the status-change
  comment via a `#issuecomment-<id>` anchor.
- `has_cve_json_anchor`: true if the recap links to the embedded CVE JSON
  section in the tracker body (heading-anchor form), or explicitly notes
  that no CVE has been allocated yet.
- `has_milestone_link`: true if the recap links to the milestone via its
  `.../milestone/<number>` URL, or notes no milestone is set.
- `has_gmail_draft_ref`: true if the recap mentions a waiting Gmail draft
  with a thread link; false when no draft was created.
- `has_next_step`: true if the recap restates the next handling-process
  step from the 2c recommendation.
- `has_bare_issue_numbers`: must always be false — any bare `#NNN` token
  that is not wrapped in a Markdown link is a Golden rule 2 violation.

Do not include any text outside the JSON object.
