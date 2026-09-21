<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.2.0`, and a `plugins` list of magpie-setup, magpie-utilities
and magpie-agent-guard. It carries no `reconciled:` block.

`.apache-magpie-overrides/` exists and contains `project.md`.
`.apache-magpie-local/reconciled.json` does not exist, so no `reconciled:`
stamp exists in either store.

The invoked skill's own frontmatter reads `name: magpie-issue-triage` and
`surface_hash: sha256:2edc90a1b7f3440d`.

The running agent is Claude Code. `claude plugin list --json` reports all three
plugins at 0.4.0 from the `apache-magpie` marketplace.
