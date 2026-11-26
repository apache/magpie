<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Agent detected: Claude Code.
Plugins just installed: magpie-setup, magpie-agent-guard, magpie-release-management.
`claude plugin list`: releasecheck@apache-incubator installed.
Resolved project.md: `organization: ASF`.
`~/.cache/apache-magpie/companions-offered`: absent.

Companion registry entries (from docs/setup/companion-skills.md):
- `roborev` — Kenn Software (community, MIT). Pairs with `pr-management`, `pairing`.
  Harnesses: claude-code, codex, copilot, antigravity, cursor (marketplace: none).

ASF catalogue (fetched from raw.githubusercontent.com/apache/magpie/main/organizations/ASF/skill-sources.md):

| Marketplace | Add it |
|---|---|
| `claude-code` | `/plugin marketplace add apache/incubator` |
| `codex` | `codex plugin marketplace add apache/incubator` |
| `copilot` | add `apache/incubator` as a VS Code / GitHub Copilot plugin marketplace |

| Skill | What it does | Install through Magpie | Marketplaces |
|---|---|---|---|
| `releasecheck` | Checks a podling release candidate before or during its vote. | `pinned` | `claude-code`, `codex`, `copilot` |
| `release-vote-reviewer` | Walks a release vote thread on general@ and drafts the +1 or the -1 with reasons. | `untagged` | `claude-code`, `codex`, `copilot` |
| `board-report` | Drafts the VP Incubator's quarterly report to the ASF board. | `untagged` | `claude-code`, `codex`, `copilot` |
| `asf-list-archaeology` | Not yet published. | `draft` | — |

Descriptor: `id: apache-incubator-releasecheck`, `marketplace: apache-incubator`.
