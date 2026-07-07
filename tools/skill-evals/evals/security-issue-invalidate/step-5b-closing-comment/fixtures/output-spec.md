<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **closing comment construction** step of the `security-issue-invalidate` skill.

The tracker state is provided. Write the closing comment and then return a JSON object asserting its structural properties.

```json
{
  "has_invalid_label_reference": true | false,
  "has_discussion_link": true | false,
  "has_rollup_link": true | false,
  "has_gmail_draft_mention": true | false,
  "is_brief": true | false,
  "has_detailed_reasoning": true | false
}
```

Field rules:
- `has_invalid_label_reference`: comment mentions closing as `invalid`.
- `has_discussion_link`: comment links to the specific discussion comment that decided invalidity (not just the issue URL).
- `has_rollup_link`: comment links to the status rollup comment.
- `has_gmail_draft_mention`: comment mentions the Gmail draft (security@-imported trackers only; `false` for PR-imported).
- `is_brief`: comment is short and process-shaped (1–3 sentences). `true` when brief, `false` when it includes detailed team reasoning (which belongs in the email draft, not here).
- `has_detailed_reasoning`: `true` if the comment re-packages the team's detailed invalidity reasoning — this should be `false` (detailed reasoning belongs in the email draft, not the public-facing closing comment).
