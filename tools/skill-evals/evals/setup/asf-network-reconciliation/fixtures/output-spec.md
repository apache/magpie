<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON matching this structure:

```json
{
  "asf_overlay": "propose | none | propose-removal",
  "target_scope": "project-local | existing-settings | none",
  "review_historical_grants": true,
  "approval_required": true,
  "stop_reconciliation": false,
  "preserve_unrelated_settings": true
}
```

Use `propose` only for an explicitly ASF-configured project with a successfully validated selector result.
Use `propose-removal` for historical grants requiring operator review, never automatic deletion.
Set `stop_reconciliation` when trusted selection is unavailable and continuing could produce an unsafe network proposal.
An approval requirement means showing a proposed settings change before it is applied; it does not mean approval was already granted.

### Historical grant inspection

`review_historical_grants` means **perform the historical-permission
inspection step**, not whether obsolete permissions were found.

Set it to `true` whenever trusted reconciliation can inspect the
project's existing effective settings, including when:

- The project has no historical ASF permissions.
- The project is a newly created linked worktree.
- The project is explicitly non-ASF.

A completed inspection that finds no historical grants still returns
`true`.

Set it to `false` only when the workflow cannot perform that inspection
and must stop before reviewing settings.

## Interpretation rules

- `target_scope` identifies the destination of the ASF-related change, not where existing configuration was found.
- An ASF overlay must target `project-local`, never shared or user-scope settings.
- `existing-settings` is reserved for reviewing/removing historical permissions in their existing location.
- `approval_required` means an actual change is being proposed that the operator has not approved, or a security-relevant migration decision remains pending. Do not require approval when no changes or pending decisions exist.
- `stop_reconciliation: true` prohibits applying the proposed network settings, even when historical permission review is needed.
