<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "in_scope": true | false,
  "violations": [
    {"type": "drive-by-reformat | stray-import | speculative-refactor | new-api-surface | unrelated-file", "description": "<one sentence>"}
  ]
}
```

`in_scope` is false when `violations` is non-empty.
Grouping is not significant: related problems may be reported as one entry or as one entry per problem, and each entry takes whichever `type` best describes it.
Do not include any text outside the JSON object.
