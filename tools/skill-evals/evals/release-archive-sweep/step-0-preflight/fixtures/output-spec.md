<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string>"],
  "non_asf": true | false,
  "dist_backend": "svnpubsub" | "github-releases" | "s3" | "self-hosted"
}
```

Grading rules:
- `verdict` must be `"proceed"` when all config checks pass.
- `verdict` must be `"blocked"` when any hard blocker remains.
- `blockers` must be an empty array when `verdict` is `"proceed"`.
- `non_asf` must be `true` when `release_dist_backend` is not `svnpubsub`.
- `dist_backend` must reflect the value of `release_dist_backend` in config.
- No extra keys are permitted in the response.
