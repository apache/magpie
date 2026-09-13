<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "outcome": "pass" | "finding",
  "edits_config": true | false,
  "widens_stack": true | false,
  "unapproved": [...],
  "blocks": true | false
}
```

`outcome` is `pass` when the gate exits 0 and the redactor round-trip
replaced both values, and `finding` otherwise. A non-zero gate is a finding
about the stack, not a failure of the skill.

`edits_config` is whether the step changes `privacy-llm.md`. It does not:
the file is written in Step 3 and Step 4 only exercises it.

`widens_stack` is whether the step adds an endpoint, relaxes the variant, or
otherwise changes the configuration so the gate passes. Never true — the gate
failing is the answer.

`unapproved` lists the stack members the gate rejected, empty on a pass.

`blocks` is whether the step stops and waits for the user rather than
continuing. True on a finding, false on a pass.

Do not include any text outside the JSON object.
