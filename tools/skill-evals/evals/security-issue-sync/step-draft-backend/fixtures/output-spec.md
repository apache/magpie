<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "backend": "maildir" | "oauth_curl" | "claude_ai_mcp",
  "decided_by": "user.md" | "project.md" | "default"
}
```

- `backend` — the backend the draft is created with: `maildir` when the
  Gmail-or-Maildir choice resolves to Maildir; otherwise the Gmail backend
  the rest of the rule picks.
- `decided_by` — where the Gmail-or-Maildir choice came from: the person's
  `tools.mail_create.backend` in `user.md`, the project's
  `mail_create.backend` in `project.md`, or neither (`default`, which is
  `gmail`).

Do not include any text outside the JSON object.
