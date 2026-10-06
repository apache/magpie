<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "dimensions": {
    "prs_merged":          { "current": <int>, "reference": <int>, "difference": <int or null> },
    "reviews_total":       { "current": <int>, "reference": <int>, "difference": <int or null> },
    "reviews_substantive": { "current": <int>, "reference": <int>, "difference": <int or null> },
    "issues_filed":        { "current": <int>, "reference": <int>, "difference": <int or null> },
    "threads_commented":   { "current": <int>, "reference": <int>, "difference": <int or null> },
    "area_breadth":        { "current": <int>, "reference": <int>, "difference": <int or null> },
    "off_github":          { "current": "present|absent" }
  },
  "verdict_given": <bool>
}
```

- `difference`: `current − reference`, signed; `null` when the reference is 0 or not declared
- `off_github.current`: "present" when the maintainer described any off-GitHub signal or a confirmed community row was collected, else "absent"
- `verdict_given`: true only if your answer assigns a status, band, traffic light, or readiness judgement (ready, approaching, not yet, met, or similar) to the contributor or to any dimension

Do not include any text outside the JSON object.
