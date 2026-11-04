<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The configured skill is `security-issue-import-from-md`.
All override anchors and required configuration files resolve.
The tracker backend is `github`.

Existing policy: `.apache-magpie-overrides/tools/vetted-ops/config.toml`.

The original saved caller entry was:

    "security-issue-import-from-md" = ["issue-view"]

The applicable canonical requirements are `rollup-append` and `issue-create-labeled`.
The proposed diff adds only those operations.

The operator confirmed the change and saved the policy. A fresh read of the saved policy shows issue-view, rollup-append, and issue-create-labeled. The saved `[values] labels` also contains both `needs triage` and `security issue`. All other applicable checks passed.

The current stamp has no entry for this skill.
