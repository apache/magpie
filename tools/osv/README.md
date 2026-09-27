<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/osv/`](#toolsosv)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# `tools/osv/`

**Capability:** contract:security-cross-ref

**Kind:** implementation

**Vendor:** OSV.dev

OSV.dev vulnerability cross-reference client.
Queries the [OSV.dev REST API v1](https://api.osv.dev/v1/) for vulnerability records, aliases (CVE ↔ GHSA ↔ OSV IDs), affected package versions, and vulnerabilities associated with a public upstream commit.
Complements [`tools/cve-org/`](../cve-org/) and [`tools/cve-tool-vulnogram/`](../cve-tool-vulnogram/) by providing cross-ecosystem vulnerability records for intended triage consumers (`security-issue-triage`, `security-issue-deduplicate`, `security-cve-allocate`, and `dependency-audit` — not yet wired).
See [`tool.md`](tool.md) for endpoint recipes, payload structures, and confidentiality boundaries.

## Prerequisites

- **Runtime:** Python 3.11+ via `uv` (through `tools/vetted-ops` dispatcher).
- **CLIs:** `vetted-op-read` (from `tools/vetted-ops`) and `jq`.
- **Credentials / auth:** None — open, unauthenticated REST API.
- **Network:** `api.osv.dev` (REST API v1), routed through `vetted-ops` HTTP read backend.

## Configuration

Adopters select this backend with `<project-config>/project.md` → `security_cross_ref.tool: osv` when performing automated vulnerability cross-referencing.
The default ecosystem (e.g. `PyPI`, `Maven`, `npm`, `Go`, `crates.io`, `NuGet`, `RubyGems`, `Packagist`) can be configured via `security_cross_ref.ecosystem`.
The adopter-facing configuration block is declared in [`projects/_template/project.md`](../../plugins/magpie-setup/templates/project.md#security-cross-reference).
