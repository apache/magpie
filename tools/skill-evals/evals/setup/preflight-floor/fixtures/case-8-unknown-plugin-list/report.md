<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-agent-guard.

The running agent is Claude Code, inside its sandboxed secure-agent-setup.
`claude plugin list --json` returns `[]`. The plugin cache directory
(`~/.claude/plugins/`) is on the sandbox's read-deny list, so this is not
a real listing of what is installed — the call could not read the state
it was asked for.
