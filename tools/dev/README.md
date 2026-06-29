<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/dev/`](#toolsdev)
  - [Prerequisites](#prerequisites)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/dev/`

**Capability:** capability:setup

Framework dev-loop helpers (placeholder check, agent pre-commit hook). Invoked by prek and CI; not consumed by any skill directly. See the individual scripts in this directory for usage.

## Prerequisites

- **Runtime:** Bash + coreutils; `check-workspace-members.py` runs under `python3`.
- **CLIs:** `uv` (the workspace checks run `uv run`), `git`, and `prek` (or `pre-commit`) — these scripts wire up the framework's hooks.
- **Credentials / auth:** None.
- **Network:** Local checks; `uv` may resolve workspace dependencies from PyPI (`pypi.org`, `files.pythonhosted.org`) on first sync.
