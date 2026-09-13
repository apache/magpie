<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          apache/magpie
    min_version:  0.3.0

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard
      - magpie-pr-management

The running agent is Claude Code. `claude plugin list --json` reports
magpie-setup 0.3.0 only. The user ran `/magpie-setup` with no arguments.
