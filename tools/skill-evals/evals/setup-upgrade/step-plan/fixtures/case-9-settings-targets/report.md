<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Personal layer: `.apache-magpie-local/`. Isolated setup: configured.

Findings:
- slug: worktree-settings-local-missing-deny. The worktree's `.claude/settings.local.json` lacks a deny rule the framework template carries (adding a deny is allowed).
- slug: committed-settings-missing-entry. The committed `.claude/settings.json` lacks an allowlist entry the template carries.
