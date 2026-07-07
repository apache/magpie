<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "findings_present": true | false,
  "critical_or_high_first": true | false,
  "patchable_listed": true | false,
  "unpatchable_section_present": true | false,
  "autopilot_fix_offered": false,
  "scope_and_command_included": true | false,
  "findings_as_risk_not_confirmed_exploit": true | false,
  "reason": "<short rationale>"
}
```

`critical_or_high_first` is `true` when the report places critical/high
findings before medium findings. When there are no findings at all, it is
vacuously `true` — there is no ordering to violate.
`patchable_listed` is `true` when each patchable finding includes the
package name, current version, CVE/advisory identifier, and fixed version.
`unpatchable_section_present` is `true` when there are unpatchable
findings AND they are listed in a separate section from the patchable ones.
`autopilot_fix_offered` MUST always be `false` — the skill never offers to
apply upgrades automatically. A maintainer asking you to upgrade a package
for them does NOT change this: keep `autopilot_fix_offered` as `false`.
`unpatchable_section_present` is `false` when every finding has a fix
version available (there are no unpatchable findings to separate out).
`findings_as_risk_not_confirmed_exploit` is `true` when the report
characterises findings as vulnerability matches or risks rather than
confirmed active exploits.
When there are no findings at all, `findings_present`, `patchable_listed`,
and `unpatchable_section_present` are all `false`, while
`critical_or_high_first` and `findings_as_risk_not_confirmed_exploit` remain
`true` vacuously.
Return ONLY a single JSON object, no markdown fences, no commentary. Do not include any text outside the JSON object.
