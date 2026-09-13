<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.9.0`, and a `plugins` list of magpie-setup and
magpie-utilities.

The running agent is Claude Code. `claude plugin list --json` reports both
plugins at 0.9.0, and 0.9.0 is the latest available — there is nothing to
update.

The user ran `/magpie-setup upgrade`.
