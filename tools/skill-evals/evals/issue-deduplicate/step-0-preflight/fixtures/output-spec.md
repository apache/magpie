<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string describing each hard blocker>"],
  "kept": <integer>,
  "duplicate": <integer>
}
```

- `verdict` is `"proceed"` only when all hard blockers resolve.
- `blockers` lists each unresolved hard blocker as a human-readable string.
- `kept` is the issue number that will remain open. It is the FIRST issue
  number supplied in the invocation.
- `duplicate` is the issue number that will be closed. It is the SECOND
  issue number supplied in the invocation.
- When both issues are open and neither is labelled `duplicate`, all hard
  blockers resolve: `verdict` is `"proceed"` and `blockers` is the empty
  array `[]`.
- When only one issue number was supplied, `verdict` must be `"blocked"` and
  `blockers` must name the missing second argument.
- When either issue is already closed or already labelled `duplicate`,
  `verdict` must be `"blocked"`.

Do not include any text outside the JSON object.
