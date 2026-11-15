<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR: #2101 "perf(setup-upgrade): read only the catalogue sections the gather summary calls for"
mergeStateStatus: BLOCKED (one approval required)
autoMergeRequest: enabled
Files changed: plugins/magpie-setup/skills/setup/setup_preflight/cli.py, plugins/magpie-setup/skills/setup/setup_preflight/installed.py, plugins/magpie-setup/skills/setup/setup_preflight/upgrade.py

Checks:
  prek            fail  7m13s
  pytest (setup-preflight)  pass

prek job log (tail):
  ruff check (workspace)........Failed
  - hook id: workspace-ruff-check
  F401 `json` imported but unused
    --> magpie-setup/skills/setup/setup_preflight/cli.py:35:8
  I001 Import block is un-sorted or un-formatted
    --> magpie-setup/skills/setup/setup_preflight/cli.py:32:1
  ruff format (workspace).......Failed

Inline review comments: none open
