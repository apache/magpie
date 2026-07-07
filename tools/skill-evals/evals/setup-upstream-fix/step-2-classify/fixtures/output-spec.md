<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "classification": "framework-bug" | "local-misconfig" | "already-fixed-upstream" | "uncertain",
  "action": "proceed-to-dedup" | "stop-local-remediation" | "propose-upgrade" | "offer-issue",
  "reason": "<one-sentence explanation>"
}
```

`classification` → `action` mapping:
- `framework-bug` (reproduces from the framework's own code/prose, snapshot current) → `proceed-to-dedup`.
- `local-misconfig` (adopter-side: overrides value, missing/expired credential or tool, adopter-set path, a `user.md` toggle) → `stop-local-remediation`.
- `already-fixed-upstream` (snapshot behind, or `main` already carries the fix) → `propose-upgrade`.
- `uncertain` (can't tell without discussion, or the fix is design-shaped) → `offer-issue`.

When torn between `framework-bug` and `local-misconfig`, prefer the more conservative `local-misconfig` or `uncertain`. Do not include any text outside the JSON object.
