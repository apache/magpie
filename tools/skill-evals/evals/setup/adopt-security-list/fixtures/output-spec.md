<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "asks_security_destination": true | false,
  "recommended": "<address, or null>",
  "flags_private_list_risk": true | false
}
```

`asks_security_destination` reports whether this step asks the maintainer
where security reports go.

`recommended` is the address offered as the recommended option, or `null`
when the step does not ask or the evidence does not support a dedicated list.

`flags_private_list_risk` is `true` when the step offers `private@` only as a
fallback and names the privacy consequence of making the PMC list the
security inbox; otherwise `false`.

Do not include any text outside the JSON object.
