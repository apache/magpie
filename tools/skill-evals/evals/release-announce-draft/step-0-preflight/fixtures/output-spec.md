<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string>"],
  "skip_promote_wait_override": true | false,
  "non_asf": true | false,
  "promote_clear_after_utc": "<ISO-8601 or null>"
}
```

Grading rules:
- The fields are the `release-management announce-draft verdict` output, without `read`; blockers are surfaced as written.
- `verdict` must be `"proceed"` when all blockers are resolved.
- `verdict` must be `"blocked"` when any hard blocker remains.
- `blockers` must be an empty array when `verdict` is `"proceed"`.
- `promote_clear_after_utc` must be a valid ISO-8601 string when the
  promote-wait gate is the only remaining blocker; otherwise `null`.
- No extra keys are permitted in the response.
