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

`high_severity_reported_before_medium` is `true` when injection and fork-secret findings appear in the report before excessive-permissions and unpinned-actions findings.
`autopilot_fix_offered` must always be `false` — the skill never offers to apply fixes automatically.
`security_breach_overclaim` must always be `false` — findings are risks, not confirmed exploits or breaches.
Do not include any text outside the JSON object.
