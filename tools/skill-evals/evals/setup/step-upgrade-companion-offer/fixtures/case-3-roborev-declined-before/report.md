<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Agent detected: Claude Code.
Plugin update: every installed Magpie plugin already at 0.9.0.dev202610140816 (nothing moved).
Installed Magpie plugins: magpie-setup, magpie-agent-guard, magpie-pr-management.
`command -v roborev`: not found.
`claude plugin list`: code-review@claude-plugins-official installed.
.apache-magpie.lock: method marketplace, min_version 0.9.0.dev202610140816.
`~/.cache/apache-magpie/companions-offered`:
  roborev claude-code

Companion registry entries (from docs/setup/companion-skills.md):
- `roborev` — Kenn Software (community, MIT). Pairs with `pr-management`, `pairing`.
  Harnesses: claude-code, codex, copilot, antigravity, cursor (marketplace: none).
  Install: `brew install kenn-io/tap/roborev` then `roborev skills install`.
  Note: On Claude Code under Magpie's secure agent setup, roborev cannot read ~/.roborev/ and fails on every call; Step B of setup-isolated-setup-install wires the exclusion and the prompt that keep it safe outside the sandbox, and Step B.2 optionally lets its post-commit hook review the agent's own commits. Without Homebrew, see https://roborev.io/docs/installation/ for the other installers.
- `code-review` — Anthropic. Pairs with `pr-management`, `pairing`.
  Harnesses: claude-code (marketplace: none). Install: `/plugin install code-review`.
- `superpowers` — obra (community). Pairs with `utilities`, `pairing`.
  Harnesses: claude-code and codex (marketplace: obra/superpowers-marketplace), cursor, antigravity, copilot, opencode.
