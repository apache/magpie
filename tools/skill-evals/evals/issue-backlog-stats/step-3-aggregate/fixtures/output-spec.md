## Output format

Return ONLY valid JSON with this structure:

```json
{
  "total_open": <integer>,
  "total_untriaged": <integer>,
  "total_triaged": <integer>,
  "total_in_progress": <integer>,
  "total_stale_candidates": <integer>,
  "health_rating": "Healthy | Needs attention | Action needed",
  "top_pressure_area": "<string>" | null
}
```

`total_open` is the count of all non-SKIP issues in the pool. `total_stale_candidates`
counts issues where `is_stale_candidate` is true (orthogonal to triage class).
`health_rating` is computed from Step 4 thresholds applied to the TOTAL row.
`top_pressure_area` is the area label with the highest pressure score, or null if
no area labels are present. Use the full label including the `area:` prefix
(e.g., `area:scheduler`).
Do not include any text outside the JSON object.
