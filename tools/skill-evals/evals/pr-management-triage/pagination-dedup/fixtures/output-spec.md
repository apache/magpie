<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "prs": [
    {
      "number": 123,
      "updatedAt": "<timestamp>",
      "headRefOid": "<commit>"
    }
  ]
}
```

Return the PRs that should be handed to Step 2, in order. Do not include
any text outside the JSON object.
