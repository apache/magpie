<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action_candidates": ["<KEY>", ...],
  "new_issue_candidate_keys": ["<KEY>", ...],
  "closure_candidates": ["<KEY>", ...],
  "tracker_hygiene_candidates": ["<KEY>", ...]
}
```

- `action_candidates` — keys that qualify as action candidates under the
  rules above (still-failing bugs, partial-fix surfaces, documentation-gap
  candidates).
- `new_issue_candidate_keys` — keys whose verdict carries a non-empty
  `cross_type_probe.findings`.
- `closure_candidates` — keys that qualify as closure candidates.
- `tracker_hygiene_candidates` — keys that qualify as tracker-hygiene
  candidates.

A key may appear in more than one list when it qualifies for more than
one. Sort every list by key. Use an empty list when nothing qualifies.
Do not include any text outside the JSON object.
