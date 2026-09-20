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
- The body must always include the `How to verify this candidate before voting`
  section: the agentic one-liner (`/<verification_skill> <version>-rcN`), the
  `verification_doc_url` and `reproducibility_doc_url` links, and the
  voter-obligation sentence linking `release-policy.html#release-approval`.
- The reproducibility record lines (`source commit`, `SOURCE_DATE_EPOCH`,
  `sha512`) appear only when the report carries a `repro_record`; when the
  report says there is none, the lines are omitted — never invented.

Do not include any text outside the JSON object.
