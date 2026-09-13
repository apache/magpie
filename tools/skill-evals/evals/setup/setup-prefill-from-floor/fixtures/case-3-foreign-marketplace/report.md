<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          contoso-internal/magpie-fork
    min_version:  0.3.0

    plugins:
      - magpie-setup
      - magpie-utilities

The running agent is Claude Code with no Magpie plugins installed. The user ran
`/magpie-setup` with no arguments.
