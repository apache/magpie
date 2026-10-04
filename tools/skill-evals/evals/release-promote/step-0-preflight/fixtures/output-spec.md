<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked" | "handoff-non-pmc",
  "blockers": ["<string>"],
  "rm_is_pmc": true | false,
  "non_asf": true | false,
  "version": "<version string>",
  "rc": "<rcN string>",
  "dist_backend": "svnpubsub" | "github-releases" | "s3" | "self-hosted"
}
```

Grading rules:
- `verdict` must be `"proceed"` when all blockers are resolved and the RM
  is on the approver roster (or the project is not ASF: `non_asf` is true
  because `project.md` does not declare `organization: ASF`).
- `verdict` must be `"handoff-non-pmc"` when the RM fails the PMC gate but
  all other checks pass.
- `verdict` must be `"blocked"` when any hard blocker (other than non-PMC)
  remains.
- Preconditions that are EXPECTED for a promotion are not blockers. In
  particular, the target `dist/release/` directory not yet existing (for
  example an `svn: E200009` "does not exist" result on the target release
  URL) is the normal starting state — promotion is what creates it — so it
  does NOT block. Only treat a check as a hard blocker when it means the
  release genuinely cannot proceed (missing config, vote not passed,
  unreachable required source, etc.).
- `blockers` must be an empty array when `verdict` is `"proceed"` or
  `"handoff-non-pmc"`.
- `version` and `rc` must be correctly parsed from the trigger argument.
- `dist_backend` must match the value in `release-management-config.md`.
- No extra keys are permitted in the response.
