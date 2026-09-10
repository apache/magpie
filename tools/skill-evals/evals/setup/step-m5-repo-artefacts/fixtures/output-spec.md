<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "offer_made": true | false,
  "offer_default": "no" | "yes",
  "artefacts_offered": [...],
  "install_complete_without": true | false
}
```

`offer_made` is a boolean.

`offer_default` is one of `"no"` or `"yes"`.

`artefacts_offered` is a list whose only possible members are
`"settings-block"` and `"config-store"`; when both appear, `"settings-block"`
comes before `"config-store"`.

`install_complete_without` is a boolean.

Do not include any text outside the JSON object.
