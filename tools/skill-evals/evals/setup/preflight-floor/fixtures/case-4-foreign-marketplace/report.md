<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url:
contoso-internal/magpie-fork`, `min_version: 0.3.0`, and a `plugins` list of
magpie-setup and magpie-repo-health.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Claude Code. `claude plugin list --json` reports
magpie-setup 0.3.0 from the `apache-magpie` marketplace and nothing else.
