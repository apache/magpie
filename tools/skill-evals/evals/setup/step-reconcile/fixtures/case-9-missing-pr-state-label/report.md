<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `git-branch` (pinned snapshot).

The configured skill `security-issue-import-from-pr` is in scope.
All configuration and override-anchor checks pass.
Tracker backend: `github`.

The configured PR importer requires these labels:
`security issue`, `scope:core`, `pr merged`.

Existing policy:

    [callers]
    "security-issue-import-from-pr" = ["pr-view-with-body", "rollup-append", "issue-create-labeled"]

    [values]
    labels = ["security issue", "scope:core"]

All caller grants exist.
The required project-specific `pr merged` label is missing.
No policy change has been approved or applied.
