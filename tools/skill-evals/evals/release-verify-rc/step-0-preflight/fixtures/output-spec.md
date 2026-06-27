<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string>"],
  "rc_tag": "<version>-rcN",
  "staging_url": "<derived staging URL or null>",
  "post_to": "<planning-issue-url or null>"
}
```

Grading rules:
- `verdict` must be `"proceed"` when all blockers are resolved.
- `verdict` must be `"blocked"` when any hard blocker remains.
- `blockers` must be an empty array when `verdict` is `"proceed"`.
- `staging_url` must be a well-formed URL when the RC tag is parseable
  and the config template is present; otherwise `null`.
- `post_to` must be the planning issue URL when `--post-to` was
  passed; otherwise `null`.
- No extra keys are permitted in the response.
