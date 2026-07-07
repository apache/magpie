<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "candidate_pairs": [
    {
      "skill_a": "<path/relative/to/skills-dir/SKILL.md>",
      "skill_b": "<path/relative/to/skills-dir/other/SKILL.md>",
      "match_signal": "<capability-value>"
    }
  ],
  "total_pairs_found": 1,
  "confirmation_required": true
}
```

Rules:
- `candidate_pairs` lists every candidate pair up to the 20-pair cap.
  An empty array means no shared-capability pairs were found.
- `total_pairs_found` is the total number of unordered pairs before the
  cap is applied. When not truncated it equals `len(candidate_pairs)`.
- `confirmation_required` is always `true`.
- Within each pair, `skill_a` < `skill_b` lexicographically by path.
- Pairs are ranked alphabetically by `skill_a` within each capability
  group; groups appear in alphabetical order of capability value.
- Do not include any text outside the JSON object.
