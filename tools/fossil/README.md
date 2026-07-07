<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Fossil Forge Bridge](#fossil-forge-bridge)
  - [Prerequisites](#prerequisites)
  - [Features](#features)
  - [Invocation](#invocation)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Fossil Forge Bridge

**Capability:** contract:tracker + contract:source-control
**Kind:** implementation
**Vendor:** Fossil

Fossil SCM forge and tracker bridge implementation for the Apache Magpie framework. It integrates version-control checks, ticket tracking, wiki reads, and forum thread reads.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (stdlib-only, no third-party dependencies).
- **CLIs:** `fossil` (for repository interactions).
- **Credentials / auth:** None (local-only; reads are direct SQL queries on the repository database).
- **Network:** Mostly offline. Requires the repository to be cloned locally, and reads/writes locally before syncs.

## Features

1. **VCS Repositories:** Standard version control operations via the `magpie-vcs` backend shim.
2. **Issue Tracker:** Read/write operations (create ticket, comment, update status, change fields) on the Fossil ticket subsystem.
3. **Wiki:** Read/list operations for wiki pages.
4. **Forum:** Read/list operations for forum posts and threads.

## Invocation

```bash
# Get ticket details
uv run --project tools/fossil magpie-fossil ticket get TICKET_UUID

# Create comment on a ticket
uv run --project tools/fossil magpie-fossil ticket comment TICKET_UUID --body "Nice fix!"

# List wiki pages
uv run --project tools/fossil magpie-fossil wiki list
```

## Configuration

The bridge resolves the Fossil repository from the checkout directories (`.fslckg` or `_FOSSIL_`) or via the `-R/--repository` argument.
