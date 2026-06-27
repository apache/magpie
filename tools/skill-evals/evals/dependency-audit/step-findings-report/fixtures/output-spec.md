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
findings before medium findings.
`patchable_listed` is `true` when each patchable finding includes the
package name, current version, CVE/advisory identifier, and fixed version.
`unpatchable_section_present` is `true` when there are unpatchable
findings AND they are listed in a separate section from the patchable ones.
`autopilot_fix_offered` MUST always be `false` — the skill never offers to
apply upgrades automatically.
`findings_as_risk_not_confirmed_exploit` is `true` when the report
characterises findings as vulnerability matches or risks rather than
confirmed active exploits.
Do not include any text outside the JSON object.
