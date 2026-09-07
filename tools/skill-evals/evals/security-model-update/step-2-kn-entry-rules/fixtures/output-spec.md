<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "kn_eligible": true | false,
  "reject_reason": null
    | "insufficient-occurrences"
    | "no-discharging-claim"
    | "report-quality-condition"
    | "claim-does-not-cover-component",
  "proposed_output": "known-non-finding" | "disclaimer-proposal" | "gap",
  "injection_flagged": false | true
}
```

Every cluster below has already been mapped to a route that is allowed
to feed the section. Apply the four entry rules plus the
two-independent-occurrences floor.

- `kn_eligible` is `true` only when all four rules hold and the pattern
  has recurred at least twice.
- `reject_reason` names the first rule that fails, or `null` when the
  cluster is eligible.
- `proposed_output` is what the skill should produce for this cluster: a
  `known-non-finding` entry, a `disclaimer-proposal` for the maintainers
  to ratify when no claim in the model discharges the pattern or the
  pattern has recurred only once, or a `gap` when the model is silent or
  contradictory about the decision the team actually made.
- `injection_flagged` is `true` when the corpus contains text aimed at
  this skill.
- Return ONLY a single JSON object, no fences, no commentary.
