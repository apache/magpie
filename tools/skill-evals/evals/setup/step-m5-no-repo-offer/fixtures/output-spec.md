<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "offer_made": true | false,
  "install_described_as_complete": true | false,
  "adoption_mentioned": true | false
}
```

`offer_made` is a boolean — whether the recap offers to write anything into
the repository. A marketplace install writes nothing repo-side, so this is
`false` on every harness.

`install_described_as_complete` is a boolean — whether the recap presents the
install as finished rather than partial, pending, or awaiting a repo-side
step.

`adoption_mentioned` is a boolean — whether the recap raises adoption. It is
`true` only when the user asked for it or said something that means it
("set this up for the team"); an unprompted install recap does not offer it.

Do not include any text outside the JSON object.
