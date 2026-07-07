<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "drift_severity": "none" | "ref" | "method-url" | "hash",
  "action": "proceed" | "sync-needed" | "reinstall-needed" | "security-flagged",
  "blocking": true | false
}
```

`drift_severity` is `"none"` when the lock files match exactly.
`action` describes what the skill proposes based on the drift severity:
- `"none"` drift → `"proceed"` (continue with the rest of the update check)
- `"ref"` differs → `"sync-needed"` (non-blocking; user may defer)
- `"method-url"` differs → `"reinstall-needed"` (full re-install needed)
- `"hash"` (svn-zip SHA-512 mismatch) → `"security-flagged"` (investigate before upgrading)
`blocking` is `false` only for `"ref"` drift (the user may defer); all other mismatch types are blocking.
Do not include any text outside the JSON object.
