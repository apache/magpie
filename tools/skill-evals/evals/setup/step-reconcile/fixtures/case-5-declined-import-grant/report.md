<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `git-branch` (pinned snapshot).

Scope: `security-issue-import-from-md` is configured.
Its `requires_config:` entries resolve, and its skill files are readable.
There are no override-anchor or missing-configuration findings.

Tracker backend: `github`.

Existing vetted-ops policy:
`.apache-magpie-overrides/tools/vetted-ops/config.toml`

The policy is valid TOML. Its caller entry is:
    "security-issue-import-from-md" = ["issue-view"]

The vetted-ops README configuration example contains:
    "security-issue-import-from-md" = ["rollup-append"]

During confirmation, the operator declined the proposal
to add `rollup-append` to this caller.
The policy remains unchanged.

The current reconciliation stamp contains no entry for this skill.
