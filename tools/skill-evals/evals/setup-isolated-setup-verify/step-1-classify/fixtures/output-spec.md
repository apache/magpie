<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "snapshot_drift": "none" | "ref" | "method-url" | "hash",
  "checks": [
    {
      "n": <1-8>,
      "status": "✓" | "✗" | "⚠",
      "evidence": "<one-line summary: file paths, version strings, or command output>"
    }
  ]
}
```

`checks` must contain exactly 8 entries, one per check (n=1 through n=8), in order.
`snapshot_drift` is `"none"` when the lock files match, otherwise the category of mismatch.
Do not include any text outside the JSON object.
