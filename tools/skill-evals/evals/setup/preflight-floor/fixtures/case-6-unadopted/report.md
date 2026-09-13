<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-issue 0.4.0 installed.

The invoked skill declares `requires_config: [issue-tracker-config.md,
project.md]`. Neither file resolves in either directory.
