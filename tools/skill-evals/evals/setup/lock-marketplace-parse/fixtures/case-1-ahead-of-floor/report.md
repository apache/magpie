<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          apache/magpie
    min_version:  0.2.0

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard

`claude plugin list --json` reports magpie-setup 0.4.0, magpie-utilities 0.4.0,
magpie-agent-guard 0.4.0, and magpie-security 0.4.0, all from the
`apache-magpie` marketplace.
