<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "by_classification": {
    "still-fails-same": <count>, "still-fails-different": <count>,
    "fixed-on-master": <count>, "cannot-run-extraction": <count>,
    "cannot-run-environment": <count>, "cannot-run-dependency": <count>,
    "timeout": <count>, "intended-behaviour": <count>,
    "duplicate-of-resolved": <count>, "needs-separate-workspace": <count>
  },
  "by_nature": {
    "bug-as-advertised": <count>, "bug-as-advertised-partial-fix": <count>,
    "feature-request": <count>, "feature-request-disguised-as-bug": <count>,
    "intended-and-documented": <count>
  },
  "cross_table": [
    {"classification": "<classification>", "nature": "<nature>", "count": <count>}
  ],
  "partial_fixes": ["<KEY>", ...]
}
```

`cross_table` contains only non-zero combinations.
`partial_fixes` contains keys where the `cases` array has mixed outcomes (some still-failing, some fixed).
Do not include any text outside the JSON object.
