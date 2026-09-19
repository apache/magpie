<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "snapshot_drift": "none" | "ref" | "method-url" | "hash",
  "checks": [
    {
      "n": <1-10>,
      "status": "✓" | "✗" | "⚠",
      "evidence": "<one-line summary: file paths, version strings, or command output>"
    }
  ]
}
```

`checks` contains one entry per check the report covers, numbered as the report numbers them (n=1 through n=10 at most), in order. Never add an entry for a check the report does not show.
`snapshot_drift` is `"none"` when the lock files match, otherwise the category of mismatch.
Do not include any text outside the JSON object.
