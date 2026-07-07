<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "output_format": "html | markdown | tables-only",
  "sections_present": ["context_line", "hero_cards", "recommendations", "age_distribution", "triage_funnel", "area_pressure", "staleness_panel", "detailed_table", "legend"],
  "sections_stubbed": ["<section_name>", ...],
  "sections_missing": []
}
```

`sections_present` lists the required sections that would be rendered with real data.
`sections_stubbed` lists sections that would be rendered as a stub (unavailable data,
one-line explanation, no data to show). `sections_missing` lists any required sections
that would be silently omitted — per Golden rule 8 this should always be empty.
Do not include any text outside the JSON object.
