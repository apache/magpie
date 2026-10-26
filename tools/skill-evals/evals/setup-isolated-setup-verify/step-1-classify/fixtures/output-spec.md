<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "snapshot_drift": "none" | "ref" | "method-url" | "hash",
  "checks": [
    {
      "n": <1-17>,
      "status": "✓" | "✗" | "⚠" | "inconclusive" | "unchecked",
      "evidence": "<one-line summary: file paths, version strings, or command output>"
    }
  ]
}
```

`checks` contains one entry per check the report covers, numbered as the report numbers them (n=1 through n=17 at most), in order. Never add an entry for a check the report does not show.
`"inconclusive"` is check 7a with no sentinel and no `ls` from the user; `"unchecked"` is "unchecked — no framework checkout" (checks 10a and 13c, and check 5's `bubblewrap`/`socat` pins; the unenforced `claude-code` floor is `⚠`).
A check takes one of these two only when every other part of it is ✓; any ✗ or ⚠ in the same check wins.
`snapshot_drift` is `"none"` when the lock files match, otherwise the category of mismatch.
Do not include any text outside the JSON object.
