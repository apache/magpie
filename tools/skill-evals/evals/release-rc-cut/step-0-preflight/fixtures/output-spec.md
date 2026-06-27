<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string describing each hard blocker>"],
  "rc_tag_exists": true | false,
  "prep_pr_merged": true | false
}
```

Grading rules:
- `verdict` is `"proceed"` only when all hard blockers resolve.
- `blockers` is empty (`[]`) when `verdict` is `"proceed"`.
- `rc_tag_exists` is `true` when the RC tag already exists on the remote.
- `prep_pr_merged` reflects whether the prep PR was confirmed merged.
- No extra keys are permitted in the response.
