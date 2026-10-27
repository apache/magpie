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
when no picker is shown. The baseline — `magpie-setup`, `magpie-vetted-ops`,
`magpie-agent-guard`, `magpie-utilities` — is pre-ticked, alongside any family the user's own words
named.

`install_set` lists every plugin installed once the user has answered: the
baseline plugins first, in baseline order, then the families in the order the
user named them, each directly followed by any companion plugin it brings
(`magpie-security` brings `magpie-security-tools`).

`prompted` is whether a picker was shown at all. An explicit
`skill-families:<list>` argument is used verbatim and skips it.

`unremovable` lists the plugins the step refuses to drop whatever the user
says, in baseline order. The rest of the baseline is strongly recommended and
can be un-ticked.

Do not include any text outside the JSON object.
