<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `trunk-drift` — major

[`stack-review findings`](../../../../../tools/pr-management/README.md) reports it when the trunk changed files the stack also edits, or when a reference to a name the stack removes appeared on the trunk after the stack was cut (only references absent at the merge-base count). Both break on the next rebase.

`behind_trunk_commits` alone is informational, never a finding.
