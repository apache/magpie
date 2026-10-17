<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Agent detected: OpenAI Codex CLI.
Plugins just installed: magpie-setup, magpie-release-management.
`command -v roborev`: not found.

Companion registry entries (from docs/setup/companion-skills.md):
- `roborev` — Kenn Software (community, MIT). Pairs with `pr-management`, `pairing`.
  Harnesses: claude-code, codex, copilot, gemini, cursor (marketplace: none).
  Install: `brew install kenn-io/tap/roborev` then `roborev skills install`.
  Note: On Claude Code under Magpie's secure agent setup, roborev cannot read ~/.roborev/ and fails on every call; Step B of setup-isolated-setup-install wires the exclusion and the prompt that keep it safe outside the sandbox, and Step B.2 optionally lets its post-commit hook review the agent's own commits. Without Homebrew, see https://roborev.io/docs/installation/ for the other installers.
- `code-review` — Anthropic. Pairs with `pr-management`, `pairing`.
  Harnesses: claude-code (marketplace: none). Install: `/plugin install code-review`.
- `superpowers` — obra (community). Pairs with `utilities`, `pairing`.
  Harnesses: claude-code and codex (marketplace: obra/superpowers-marketplace), cursor, gemini, copilot, opencode.
