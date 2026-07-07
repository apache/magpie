<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "dimensions": {
    "prs_merged":          { "current": <int>, "required": <int>, "status": "MET|APPROACHING|NOT_YET|narrative_only" },
    "reviews_total":       { "current": <int>, "required": <int>, "status": "MET|APPROACHING|NOT_YET|narrative_only" },
    "reviews_substantive": { "current": <int>, "required": <int>, "status": "MET|APPROACHING|NOT_YET|narrative_only" },
    "issues_filed":        { "current": <int>, "required": <int>, "status": "MET|APPROACHING|NOT_YET|narrative_only" },
    "threads_commented":   { "current": <int>, "required": <int>, "status": "MET|APPROACHING|NOT_YET|narrative_only" },
    "area_breadth":        { "current": <int>, "required": <int>, "status": "MET|APPROACHING|NOT_YET|narrative_only" },
    "off_github":          { "current": "present|absent", "required": "present", "status": "MET|NOT_YET|narrative_only" }
  },
  "traffic_light": "Ready to nominate | Approaching | Not yet"
}
```

- `status`: "MET" when current >= required (or required == 0); "APPROACHING" when current >= 50% of required; "NOT_YET" when current < 50% of required; "narrative_only" when thresholds are qualitative
- `traffic_light`: "Ready to nominate" if every mandatory dimension is MET; "Not yet" if any mandatory dimension is NOT_YET; otherwise "Approaching" (no dimension NOT_YET but not all MET). Mandatory dimensions are those with threshold > 0, plus off_github when required; threshold-0 and undeclared dimensions are advisory, auto-MET, and excluded from the aggregate

Do not include any text outside the JSON object.
