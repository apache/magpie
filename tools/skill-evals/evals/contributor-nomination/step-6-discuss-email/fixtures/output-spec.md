<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "thread_count": 1,
  "detail_level": "names" | "summary" | "links" | "full",
  "candidate_order": ["<login>", "..."],
  "personal_note_prompts": 0,
  "separator_lines": 0,
  "links_included": true | false,
  "note_written_by_agent": true | false,
  "readiness_verdict_present": true | false,
  "email_sent": true | false,
  "mail_draft_backend": "oauth_curl" | "none"
}
```

- `thread_count`: how many separate `[DISCUSS]` emails the draft opens.
- `detail_level`: the level applied to the candidates (the default when the nominator chose none).
- `candidate_order`: the logins in the order their blocks appear, across all threads.
- `personal_note_prompts`: how many separate personal-note prompts the nominator gets, one per candidate.
- `separator_lines`: the total number of dashed separator lines across all drafted emails.
- `links_included`: true when any candidate block carries a link.
- `note_written_by_agent`: true when any personal note in the draft was not written by the nominator.
- `readiness_verdict_present`: true when any sentence the agent wrote says or implies a candidate is ready, strong, or better than another.
- `email_sent`: true when the plan sends the email or posts it anywhere.
- `mail_draft_backend`: the backend used to create a mail draft, or `none` when no draft is created.
