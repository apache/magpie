<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "sub_command": "plan" | "prep" | "post" | "automated-signing",
  "version": "<version string, or null for automated-signing>",
  "blockers": ["<string>"],
  "release_branch_base": "<branch>",
  "previous_tag": "<tag or null>"
}
```

Grading rules:
- `verdict` must be `"proceed"` when all blockers are resolved.
- `verdict` must be `"blocked"` when any hard blocker remains.
- `blockers` must be an empty array when `verdict` is `"proceed"`.
- `sub_command` must be exactly `"plan"`, `"prep"`, `"post"`, or `"automated-signing"`.
- `version` is `null` for the version-less `automated-signing` sub-command.
- `automated-signing` is 🪶 ASF-specific: it proceeds only when `project.md`
  declares `organization: ASF` (the organization manifest's
  `release_process.automated_signing` is non-null); for any other
  organization the verdict is `"blocked"` and the flow is not described.
- `previous_tag` must carry the previous release tag whenever it is available at pre-flight — for example when the report states a previous release tag was detected, echo that exact tag string (do not null it out just because this is the pre-flight step). Use `null` ONLY when no previous tag can be determined at all (none reported, none detectable).
- No extra keys are permitted in the response.
