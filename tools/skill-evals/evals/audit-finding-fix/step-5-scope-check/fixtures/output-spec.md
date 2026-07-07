<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "in_scope": true | false,
  "violations": [
    {"type": "drive-by-reformat | stray-import | speculative-refactor | unrelated-file | new-api-surface", "description": "<one sentence>"}
  ]
}
```

`in_scope` is false when `violations` is non-empty.
Do not include any text outside the JSON object.
