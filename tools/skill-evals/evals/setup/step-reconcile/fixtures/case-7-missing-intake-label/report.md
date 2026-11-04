<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `git-branch` (pinned snapshot).

The configured skill `security-issue-import-from-md` is in scope.
All configuration and override-anchor checks pass.
Tracker backend: `github`.

Existing policy:

    [callers]
    "security-issue-import-from-md" = ["rollup-append", "issue-create-labeled"]

    [values]
    labels = ["needs triage"]

All required caller grants exist.
The required `security issue` label is missing.
No policy change has been approved or applied.
