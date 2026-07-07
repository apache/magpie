<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "merged_findings": [
    {
      "axis": "correctness | security | conventions",
      "severity": "blocking | advisory",
      "location": "<file>:<line-range>",
      "summary": "<one sentence>",
      "evidence": "<quoted diff line(s)>",
      "rule": "<one-line rule citation>",
      "also_flagged_by": ["<axis-name>", "..."]
    }
  ],
  "aggregated_injection_attempts": ["<one-line summary per attempt>"],
  "blocking_count": 0,
  "advisory_count": 0
}
```

`also_flagged_by` is omitted (or empty array) when the finding was reported by only one pass.
`aggregated_injection_attempts` collects all injection_attempts from all three passes.
`blocking_count` and `advisory_count` reflect the counts in `merged_findings`.
Findings are grouped by axis in the fixed order correctness → security → conventions; within each axis, blocking before advisory, then alphabetically by location.
Do not include any text outside the JSON object.
