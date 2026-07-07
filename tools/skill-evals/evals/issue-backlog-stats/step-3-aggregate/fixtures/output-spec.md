<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

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
`health_rating` is computed by applying these thresholds to the TOTAL row and
summing points. **"Untriaged non-stale" means issues that are `UNTRIAGED` AND
have `is_stale_candidate == false` — exclude every stale candidate, even
untriaged ones.**

- Untriaged non-stale issues > 20% of total → 1 pt
- Untriaged non-stale issues > 40% of total → +1 pt
- Issues older than 90 d > 30% of total → 1 pt
- Stale candidates > 10% of total → 1 pt
- Stale candidates > 25% of total → +1 pt

Map total points → `Healthy` (0 pt) / `Needs attention` (1–2 pt) /
`Action needed` (3+ pt).

`top_pressure_area` is the area label with the highest pressure score, or null if
no area labels are present. Use the full label including the `area:` prefix
(e.g., `area:scheduler`).
Do not include any text outside the JSON object.
