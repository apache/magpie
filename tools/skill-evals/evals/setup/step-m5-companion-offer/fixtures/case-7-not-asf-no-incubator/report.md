<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Agent detected: Claude Code.
Plugins just installed: magpie-setup, magpie-agent-guard, magpie-release-management.
`claude plugin list`: no other plugins.
Resolved project.md: `organization: independent`.
`~/.cache/apache-magpie/companions-offered`: absent.

Companion registry entries (from docs/setup/companion-skills.md):
- `roborev` — Kenn Software (community, MIT). Pairs with `pr-management`, `pairing`.
  Harnesses: claude-code, codex, copilot, antigravity, cursor (marketplace: none).

ASF catalogue (fetched from raw.githubusercontent.com/apache/magpie/main/organizations/ASF/skill-sources.md):

| Skill | What it does | Install through Magpie | Marketplaces |
|---|---|---|---|
| `releasecheck` | Checks a podling release candidate before or during its vote. | `pinned` | `claude-code`, `codex`, `copilot` |
| `board-report` | Drafts the VP Incubator's quarterly report to the ASF board. | `untagged` | `claude-code`, `codex`, `copilot` |
