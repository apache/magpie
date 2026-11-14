<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Read `tracker.platform` from `<project-config>/project.md` before the first tracker operation; unset or `TODO` means `github`.
With `github`, every recipe below runs as written.
With `local-files` or `jira`, read [tracker-backend.md](tracker-backend.md) before the first tracker operation and follow it: it replaces the recipes below, the Step 0 GitHub checks and the CVE JSON commands, and adds a closing publish step.
