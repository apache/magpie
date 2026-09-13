<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "pre_ticked": [...],
  "install_set": [...],
  "prompted": true | false,
  "unremovable": [...]
}
```

`pre_ticked` lists the plugins the picker offers already selected, or is empty
when no picker is shown. The baseline — `magpie-setup`, `magpie-agent-guard`,
`magpie-utilities` — is pre-ticked, alongside any family the user's own words
named.

`install_set` lists every plugin installed once the user has answered, in any
order.

`prompted` is whether a picker was shown at all. An explicit
`skill-families:<list>` argument is used verbatim and skips it.

`unremovable` lists the plugins the step refuses to drop whatever the user
says. `magpie-setup` is the only one: it is the skill doing the installing.
The rest of the baseline is strongly recommended and can be un-ticked.

Do not include any text outside the JSON object.
