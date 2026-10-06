<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "read_fully_layers": [3, 4],
  "exemplar_layers": [2],
  "skipped_layers": [8],
  "tier_a_read_in_full": true,
  "demoted_layers": [],
  "note_for_sampled_layer": "<one per-layer note line for the layer named in the input, or an empty string>",
  "coverage_sentence": "<the one-sentence cut description for the layer named in the input, or an empty string>"
}
```

Rules:
- `read_fully_layers` are every layer planned `full` (Tier B); `exemplar_layers` are every layer planned `exemplar` (Tier C); `skipped_layers` are every layer planned `skip` (Tier D). List all of them whatever the question about a single layer asks.
- `tier_a_read_in_full` is always true: Tier A hunks are read in addition to the budget and are never cut, even when Tier A alone exceeds it.
- `demoted_layers` lists every layer planned `exemplar`, whether the per-layer limit or the budget demoted it (the same set as `exemplar_layers`); `[D]eepen` is offered whenever it is non-empty. The ledger applies the budget — never simulate it yourself.
- `note_for_sampled_layer` follows the Step 4 note format and wording rules for a layer read by exemplar; it must carry the `[C sampled]` tag and must not call the layer reviewed or approved.
- `coverage_sentence`, when asked for, states for a demoted hand-written layer how many outliers of how many were read within the layer's share and how many hunks were not read; it never says the layer was reviewed.
- Do not include any text outside the JSON object.
