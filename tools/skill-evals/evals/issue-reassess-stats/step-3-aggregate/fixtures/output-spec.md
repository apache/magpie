<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "health": "Healthy | Needs attention | Action needed",
  "action_candidates": ["<KEY>", ...],
  "closure_candidates": ["<KEY>", ...],
  "new_issue_candidates": ["<KEY>", ...],
  "total": <integer>
}
```

Health rating rules:
- `Healthy` — 0 still-failing bugs
- `Needs attention` — 1–2 still-failing bugs, or >30% cannot-run
- `Action needed` — 3+ still-failing bugs

`action_candidates` — keys with classification `still-fails-same` or `still-fails-different`.
`closure_candidates` — keys with classification `fixed-on-master` (strong evidence for close).
`new_issue_candidates` — keys from the `new_issue_candidates` list passed in.
Do not include any text outside the JSON object.
