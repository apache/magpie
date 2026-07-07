<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string describing each hard blocker>"],
  "skip_verify_override": true | false,
  "expedited": true | false
}
```

- `verdict` is `"proceed"` only when all hard blockers resolve.
- `blockers` lists each unresolved hard blocker as a human-readable string.
- `skip_verify_override` is `true` when `--skip-verify-check` was passed and accepted.
- `expedited` is `true` when `vote_window_hours` is below 72 and `--expedited` was passed.
- An accepted override resolves its check; it does not appear in `blockers`.

Do not include any text outside the JSON object.
