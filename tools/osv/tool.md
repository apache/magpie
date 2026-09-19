<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: OSV.dev](#tool-osvdev)
  - [What this tool provides](#what-this-tool-provides)
    - [Consuming skills (intended roadmap — not yet wired)](#consuming-skills-intended-roadmap--not-yet-wired)
  - [URLs and Endpoints](#urls-and-endpoints)
  - [Operations](#operations)
    - [1. Retrieve record and aliases by Vulnerability ID — `get-vuln`](#1-retrieve-record-and-aliases-by-vulnerability-id--get-vuln)
    - [2. Query by package and version — `query-package`](#2-query-by-package-and-version--query-package)
    - [3. Query by commit hash — `query-commit`](#3-query-by-commit-hash--query-commit)
    - [4. Batch query dependencies — `query-batch`](#4-batch-query-dependencies--query-batch)
  - [Confidentiality and Embargo Boundaries](#confidentiality-and-embargo-boundaries)
  - [When to replace this tool with another](#when-to-replace-this-tool-with-another)
  - [Per-project configuration](#per-project-configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Tool: OSV.dev

This directory documents the **OSV.dev** tool adapter (`contract:security-cross-ref`).
[OSV.dev](https://osv.dev) is an open, distributed vulnerability database aggregator maintained by the Open Source Security Foundation (OpenSSF) and Google.
It provides an Open Source Vulnerability (OSV) format schema mapping cross-ecosystem vulnerability identifiers across CVE, GitHub Security Advisories (GHSA), PyPI (PYSEC), RustSec, Go vulnerability database (GO), Debian, and Linux kernel advisories.

This tool complements the existing [`tools/cve-org/`](../cve-org/) and [`tools/cve-tool-vulnogram/`](../cve-tool-vulnogram/) adapters by providing OSV's per-ecosystem vulnerability records and machine-readable alias graph.

## What this tool provides

Four primary operations:

1. **Vulnerability ID & Alias Cross-Walk (`get-vuln` / `aliases`)**: Given an advisory identifier (`GHSA-...`, `CVE-...`, `PYSEC-...`, `RUSTSEC-...`), fetch the complete OSV record, summary, CVSS severity, affected package version ranges, and alias cross-references (mapping CVE ↔ GHSA ↔ OSV IDs).
2. **Package Version Query (`query-package`)**: Given a package name and ecosystem (e.g., `PyPI`, `Maven`, `npm`, `Go`, `crates.io`, `NuGet`, `RubyGems`, `Packagist`), retrieve all published advisories affecting that specific version.
3. **Commit Query (`query-commit`)**: Given a public upstream Git commit hash, find any published vulnerabilities associated with or resolved by that commit.
4. **Batch Query (`query-batch`)**: Query multiple package versions or commit hashes in a single HTTP request.

### Consuming skills (intended roadmap — not yet wired)

These skills represent intended consumers for this cross-reference adapter once wired into their triage passes:

- [`security-issue-triage`](../../skills/security-issue-triage/SKILL.md) — early deduplication against the known-vulnerability set.
- [`security-issue-deduplicate`](../../skills/security-issue-deduplicate/SKILL.md) — alias resolution (CVE ↔ GHSA) before merging duplicate trackers.
- [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md) — sanity check that no existing OSV/GHSA already covers the report before allocating a new CVE.
- [`dependency-audit`](../../skills/dependency-audit/SKILL.md) — scan project dependencies against published ecosystem advisories.

## URLs and Endpoints

| Purpose | Endpoint / URL | Method |
|---|---|---|
| Public Web UI | `https://osv.dev/vulnerability/<ID>` | Browser |
| Fetch by Vulnerability ID | `https://api.osv.dev/v1/vulns/<ID>` | `GET` |
| Query Vulnerabilities | `https://api.osv.dev/v1/query` | `POST` |
| Batch Query Vulnerabilities | `https://api.osv.dev/v1/querybatch` | `POST` |

## Operations

All operations are read-only HTTP REST requests.
No authentication headers or API keys are required.

### 1. Retrieve record and aliases by Vulnerability ID — `get-vuln`

Fetch the OSV JSON record by its primary ID (or alias):

```bash
# Read-only, unauthenticated. Returns complete OSV schema JSON.
uv run --project <framework>/tools/vetted-ops vetted-op-read --caller <caller> osv-get-vuln <ID>
```

Extracting alias identifiers (e.g., resolving a GHSA ID to corresponding CVE IDs):

```bash
uv run --project <framework>/tools/vetted-ops vetted-op-read --caller <caller> osv-get-vuln GHSA-7rjr-3q55-vv33 \
  | jq -r '{id: .id, aliases: .aliases, summary: .summary}'
```

Example JSON response:
```json
{
  "id": "GHSA-7rjr-3q55-vv33",
  "aliases": [
    "CVE-2021-45046"
  ],
  "summary": "Incomplete fix for Apache Log4j vulnerability"
}
```

Extracting affected version ranges and fixed versions:

```bash
uv run --project <framework>/tools/vetted-ops vetted-op-read --caller <caller> osv-get-vuln <ID> \
  | jq -r '.affected[] | {package: .package.name, ecosystem: .package.ecosystem, fixed: [.ranges[].events[] | select(.fixed != null) | .fixed]}'
```

### 2. Query by package and version — `query-package`

Check if a given package release is subject to any known advisories:

```bash
uv run --project <framework>/tools/vetted-ops vetted-op-read --caller <caller> osv-query-package jinja2 PyPI 2.11.2 \
  | jq -r '.vulns[]? | {id: .id, aliases: .aliases, summary: .summary}'
```

Common ecosystems: `PyPI`, `Maven`, `npm`, `crates.io`, `Go`, `Packagist`, `NuGet`, `Hex`, `Pub`, `RubyGems`.

### 3. Query by commit hash — `query-commit`

Check if a public upstream commit SHA is indexed in OSV as a fix or vulnerability reference:

```bash
uv run --project <framework>/tools/vetted-ops vetted-op-read --caller <caller> osv-query-commit <COMMIT_HASH> \
  | jq -r '.vulns[]? | {id: .id, aliases: .aliases, summary: .summary}'
```

### 4. Batch query dependencies — `query-batch`

Evaluate multiple dependencies in a single round-trip:

```bash
uv run --project <framework>/tools/vetted-ops vetted-op-read --caller <caller> osv-query-batch /tmp/agent-scratch/batch.json \
  | jq -r '.results | to_entries[] | {query: .key, vuln_count: ((.value.vulns // []) | length)}'
```

## Confidentiality and Embargo Boundaries

OSV.dev is a **public, external third-party service**.
Queries sent to `api.osv.dev` are received by external infrastructure and can be logged.

The following strict confidentiality rules apply per [`AGENTS.md`](../../AGENTS.md) and [`PRINCIPLES.md §16`](../../PRINCIPLES.md#16-tracker-identifiers-are-public-safe-tracker-contents-are-not):

- **Safe to query:**
  - Public upstream release package names and version numbers (e.g. released dependencies).
  - Public commit hashes from the project's public upstream repository branches/tags.
  - Published, public vulnerability identifiers (e.g. existing `CVE-YYYY-NNNN` or public `GHSA-...`).
- **FORBIDDEN (Never send to OSV.dev):**
  - **Never** query private commit hashes from embargoed security forks or private reproducer branches.
  - **Never** send unallocated or private security-tracker issue references, draft CVE summaries, or private vulnerability descriptions.
  - **Never** send private file paths, reporter identities, or embargoed project code snippets in search queries.

## When to replace this tool with another

- **`tools/cve-org/`**: Use `cve-org` for verifying authoritative CVE publication status against MITRE/CVE Services.
  OSV aggregates CVE data, but `cve-org` remains the primary source of truth for CVE Services container states (`RESERVED`, `PUBLISHED`, `REJECTED`).
- **`tools/cve-tool-vulnogram/`**: Use `cve-tool-vulnogram` for allocating CVE IDs and editing draft records within the ASF CNA infrastructure.

## Per-project configuration

Adopters configure cross-referencing in `<project-config>/project.md`
(see [`projects/_template/project.md#security-cross-reference`](../../projects/_template/project.md#security-cross-reference)):

```yaml
security_cross_ref:
  tool: osv
  ecosystem: PyPI  # Default ecosystem for package queries (e.g. Maven, PyPI, npm, Go, crates.io)
```
