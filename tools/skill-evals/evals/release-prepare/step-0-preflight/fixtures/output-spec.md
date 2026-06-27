<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "sub_command": "plan" | "prep" | "post",
  "version": "<version string>",
  "blockers": ["<string>"],
  "release_branch_base": "<branch>",
  "previous_tag": "<tag or null>"
}
```

Grading rules:
- `verdict` must be `"proceed"` when all blockers are resolved.
- `verdict` must be `"blocked"` when any hard blocker remains.
- `blockers` must be an empty array when `verdict` is `"proceed"`.
- `sub_command` must be exactly `"plan"`, `"prep"`, or `"post"`.
- `previous_tag` must be `null` when it cannot be determined at pre-flight.
- No extra keys are permitted in the response.
