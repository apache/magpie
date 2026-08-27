<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "header": "[3/27] #65471 — step: classify → propose comment",
  "position": 3,
  "group_size": 27,
  "stage": "classify → propose comment"
}
```

Use the one-based row index and original group size from the input. The
`stage` value must be `classify → propose <action>` for the suggested action
shown in the input. The `header` value must render the complete first line,
including the PR number, with the exact format shown above. Return no text
outside the JSON object.
