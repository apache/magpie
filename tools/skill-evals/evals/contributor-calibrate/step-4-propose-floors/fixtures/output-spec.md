<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "floors": { "committer": { "<metric>": <int> }, "pmc": { "<metric>": <int> } },
  "evidence_only": { "committer": ["<metric>"], "pmc": ["<metric>"] },
  "no_floors_for": ["committer" | "pmc"],
  "diff_contains_names": true | false
}
```

- `floors`: the floor per metric and target that the skill proposes for the config diff.
- `evidence_only`: metrics the skill proposes as evidence only, per target, alphabetical; empty when none.
- `no_floors_for`: targets the skill proposes no floors for; empty when none.
- `diff_contains_names`: whether the proposed config diff contains any nominee name or handle.

Do not include any text outside the JSON object.
