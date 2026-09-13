<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          apache/magpie
    min_version:  0.10.0

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard

`claude plugin list --json` reports all three plugins at version 0.9.0 from the
`apache-magpie` marketplace.
