<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Personal layer: `.apache-magpie-local/`.
Findings:
- slug: isolated-configured. The out-of-sandbox run of `python3 -m setup_preflight.isolated configured` printed `{"configured": false}` (confirmed absent).
  The personal layer's `reconciled.json` has no `isolated_setup` key, so the user has not declined.
No other findings. No hard-line findings.
