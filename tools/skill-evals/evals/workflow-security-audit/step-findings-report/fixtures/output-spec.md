<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "findings_present": true | false,
  "injection_count": <integer>,
  "fork_secrets_count": <integer>,
  "excessive_permissions_count": <integer>,
  "unpinned_actions_count": <integer>,
  "high_severity_reported_before_medium": true | false,
  "remediation_suggestions_present": true | false,
  "autopilot_fix_offered": false,
  "scope_and_command_included": true | false,
  "security_breach_overclaim": false
}
```

`high_severity_reported_before_medium` is `true` when injection and fork-secret findings appear in the report before excessive-permissions and unpinned-actions findings. When there are NO findings at all, the ordering constraint is vacuously satisfied, so `high_severity_reported_before_medium` is `true` (never `false`) in the no-findings case.
`remediation_suggestions_present` is `true` only when the report actually offers remediation guidance. When there are no findings, there is nothing to remediate, so `remediation_suggestions_present` is `false`.
`scope_and_command_included` is `true` when the report states the scan scope and the command used, which it does even in the no-findings case.
`autopilot_fix_offered` must always be `false`: the skill never offers to apply fixes automatically.
`security_breach_overclaim` must always be `false`: findings are risks, not confirmed exploits or breaches.
Do not include any text outside the JSON object.
