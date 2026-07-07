<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "subject": "<final subject line>",
  "body": "<final vote email body>",
  "vote_window_hours": <integer>,
  "expedited": true | false,
  "skip_verify_logged": true | false
}
```

- `subject` is the complete `[VOTE]` subject line.
- `body` is the complete email body, with all metadata placeholders substituted.
- `vote_window_hours` is the integer value from config (or the expedited value if overridden).
- `expedited` is `true` when the vote window is below 72 h (i.e. `--expedited` was accepted).
- `skip_verify_logged` is `true` when `--skip-verify-check` was used and the reason appears in the body.
- When `expedited` is `true`, the body must include an `[EXPEDITED]` block with the reason and a reminder about the board report.
- When `skip_verify_logged` is `true`, the body must include a `[SKIP-VERIFY]` block with the reason.

Do not include any text outside the JSON object.
