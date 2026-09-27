<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "kept": ["<handle>"],
  "dropped": [ { "handle": "<handle>", "merged_prs": <int>, "reviewed_prs": <int> } ]
}
```

- `kept`: handles kept for full measurement, alphabetical.
- `dropped`: handles dropped, alphabetical, each with the two counts it was dropped on.

Do not include any text outside the JSON object.
