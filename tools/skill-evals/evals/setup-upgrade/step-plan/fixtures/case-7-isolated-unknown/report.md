<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code, running inside the sandbox. Personal layer: `.apache-magpie-local/`.
Findings:
- slug: isolated-configured. Inside the sandbox `python3 -m setup_preflight.isolated configured` printed `{"configured": false}`.
  The personal layer's `reconciled.json` has no `isolated_setup` key. The user-scope settings are read-denied in the sandbox.
No other findings.
