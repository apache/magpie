<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string describing each hard blocker>"],
  "force_close": true | false,
  "mechanism": "dev-list-vote" | "github-discussion" | "pr-approval" | "maintainer-roster",
  "roster_path": "<resolved path to approver roster>"
}
```

Grading rules:
- `verdict` must be `"proceed"` when all hard blockers are resolved.
- `verdict` must be `"blocked"` when any hard blocker remains.
- `blockers` must be an empty array when `verdict` is `"proceed"`.
- `force_close` is `true` only when `--force-close` was passed and accepted.
- `mechanism` must match the value from `release_approval_mechanism` in config.
- `roster_path` must be the resolved path from `release_approver_roster_path`.
- No extra keys are permitted in the response.
