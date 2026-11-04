<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `git-branch` (pinned snapshot).

The configured skill `security-issue-import` is in scope.
Required configuration and override-anchor checks pass.

Existing stamp hash: `sha256:079bd7106b8b78ef`.
Current skill hash: `sha256:3210ccb4763beb17`.

Tracker backend: `github`.

Existing policy:

    [callers]
    "security-issue-import" = ["issue-list-with-bodies", "rollup-append"]

    [values]
    labels = ["needs triage"]

The new requirements include `issue-create-labeled` and the
`security issue` label.

No policy changes have been approved or applied.
