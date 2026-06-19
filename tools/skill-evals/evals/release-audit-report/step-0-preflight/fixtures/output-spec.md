<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string>"],
  "planning_issue_url": "<url or null>",
  "audit_log_path": "<path or null>"
}
```

Grading rules:
- `verdict` must be `"proceed"` when all config checks pass.
- `verdict` must be `"blocked"` when any hard blocker remains.
- `blockers` must be an empty array when `verdict` is `"proceed"`.
- `planning_issue_url` must be non-null when the planning issue is found.
- `audit_log_path` must be non-null when the config key is present.
- No extra keys are permitted in the response.
