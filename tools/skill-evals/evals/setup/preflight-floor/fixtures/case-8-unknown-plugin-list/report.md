<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-agent-guard. It carries no `reconciled:` block.

`.apache-magpie-overrides/` exists and contains `project.md`.
`.apache-magpie-local/reconciled.json` does not exist, so no `reconciled:`
stamp exists in either store.

The invoked skill's own frontmatter reads `name: magpie-issue-triage` and
`surface_hash: sha256:2edc90a1b7f3440d`.

The running agent is Claude Code, inside its sandboxed secure-agent-setup.
`claude plugin list --json` returns `[]`. The plugin cache directory
(`~/.claude/plugins/`) is on the sandbox's read-deny list, so this is not
a real listing of what is installed — the call could not read the state
it was asked for.
