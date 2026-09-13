<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.2.0`, and a `plugins` list of magpie-setup, magpie-utilities
and magpie-agent-guard.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Claude Code. `claude plugin list --json` reports all three
plugins at 0.4.0 from the `apache-magpie` marketplace.
