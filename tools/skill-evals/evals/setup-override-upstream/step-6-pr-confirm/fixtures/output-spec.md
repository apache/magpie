<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "sections_present": ["summary", "motivation", "migration-path", "test-plan"],
  "confirmed": true | false | null,
  "action": "wait-for-confirmation" | "post-pr" | "cancel"
}
```

`sections_present` lists the required PR-body sections present in the draft
(from the skill's Step 6 requirements: Summary, Motivation, Migration path,
Test plan). Omit a section name when it is missing from the draft.

`confirmed`:
- `null` when the user has not yet responded to the confirmation request.
- `true` when the user approved posting (e.g. "OK to post", "yes", "send").
- `false` when the user declined (e.g. "no", "cancel", "let me revise").

`action`:
- `wait-for-confirmation` when the draft has been shown to the user but no
  response has been received yet (`confirmed` is `null`).
- `post-pr` when `confirmed` is `true` and all required sections are present.
- `cancel` when `confirmed` is `false`.

Do not include any text outside the JSON object.
