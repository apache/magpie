<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Personal layer: `.apache-magpie-local/`.
Findings:
- slug: isolated-configured. The approved out-of-sandbox read of `~/.claude/settings.json` and `~/.claude/settings.local.json` (harness file-read tool) shows no `sandbox.enabled` (confirmed absent).
  The personal layer's `reconciled.json` has no `isolated_setup` key, so the user has not declined.
No other findings. No hard-line findings.
