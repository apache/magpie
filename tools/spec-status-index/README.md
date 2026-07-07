<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [spec-status-index](#spec-status-index)
  - [Prerequisites](#prerequisites)
  - [Usage](#usage)
  - [Statuses](#statuses)
  - [Run tests](#run-tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# spec-status-index

**Capability:** substrate:framework-dev + substrate:analytics

**Harness:** agnostic

A deterministic `uv` tool that reads spec-loop specs from
`tools/spec-loop/specs/` and prints them grouped by status, so build
iterations can choose the next work item mechanically.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; stdlib-only (no runtime
  dependencies). The `dev` group pulls `pytest`.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline; reads spec files from
  `tools/spec-loop/specs/` on the local filesystem.

## Usage

```bash
# All specs, grouped by status
uv run --project tools/spec-status-index spec-status

# Only actionable items (proposed + experimental)
uv run --project tools/spec-status-index spec-status --ready

# Filter to a specific status
uv run --project tools/spec-status-index spec-status --status proposed

# Machine-readable JSON output
uv run --project tools/spec-status-index spec-status --json
uv run --project tools/spec-status-index spec-status --ready --json
```

## Statuses

| Status | Meaning |
|---|---|
| `proposed` | Planned; no implementation yet |
| `experimental` | Partially implemented; may change |
| `stable` | Production quality |
| `off` | Disabled |

`--ready` surfaces `proposed` and `experimental` specs — the ones with
actionable build work remaining.

## Run tests

```bash
uv run --project tools/spec-status-index --group dev pytest
```
