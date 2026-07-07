<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [tools/scan-format/ — adapter contract](#toolsscan-format--adapter-contract)
  - [Prerequisites](#prerequisites)
  - [What "a scan" means](#what-a-scan-means)
  - [Today's adapters](#todays-adapters)
  - [Interface](#interface)
    - [`detect(folder) -> adapter_name | null`](#detectfolder---adapter_name--null)
    - [`finding_index(folder) -> [finding]`](#finding_indexfolder---finding)
    - [`evidence(folder, finding_id) -> {detail, code_refs, reachability, remediation}`](#evidencefolder-finding_id---detail-code_refs-reachability-remediation)
    - [Finding schema (normalised)](#finding-schema-normalised)
  - [Configuration](#configuration)
  - [What this contract does NOT cover](#what-this-contract-does-not-cover)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# tools/scan-format/ — adapter contract

**Capability:** contract:scan-format

**Kind:** interface

**Vendor:** agnostic

A **scan-format adapter** teaches
[`security-issue-import-from-scan`](../../skills/security-issue-import-from-scan/SKILL.md)
how to read one security scanner's report layout. The skill is
scanner-agnostic; everything format-specific — how to recognise a scan
folder, how to enumerate findings, how to pull a finding's evidence, and
how to normalise the fields — lives behind this contract so the triage
flow is identical across scanners.

## Prerequisites

- **Runtime:** None — this directory is a documented adapter *contract* (specification), not executable code; an adapter is implemented as documented behaviour inside the consuming skill.
- **CLIs:** None.
- **Credentials / auth:** None.
- **Network:** None — the contract reaches no hosts; locating scan folders and issues is the consuming skill's job.

## What "a scan" means

A **scan** is a set of findings produced by one run of a security
scanner against a target at a specific commit. It is materialised as a
**scan folder** (in the reference adopter, a directory under
`apache/tooling-agents/ASVS/reports/.../<commit>/`) and/or referenced
from a tracking **GitHub issue**. A scan folder always carries two
things the contract below maps to:

- a **finding index** — a machine-readable per-finding list (cheap to
  parse, used to enumerate the finding set);
- **per-finding evidence** — the full analysis: code excerpt, line
  references, proof-of-concept / reachability reasoning, proposed
  remediation. **The importer bases every disposition on the evidence,
  never on the index alone.**

## Today's adapters

| Adapter | Recognises | Index file | Evidence file |
|---|---|---|---|
| `asvs` (reference) | a dir holding both files below | `issues.md` (`## Issue: FINDING-NNN - <title>` blocks) | `consolidated.md` (`#### FINDING-NNN: <title>` sections with an attribute table + Description + Remediation) |

## Interface

An adapter implements (as documented behaviour, not a code API):

### `detect(folder) -> adapter_name | null`

Return the adapter name if *folder* is a scan folder this adapter
understands (for `asvs`: it contains both `issues.md` and
`consolidated.md`), else `null`. Used for **recursive discovery**: the
skill walks a parent folder / git tree and calls `detect` on each
directory, processing every match.

### `finding_index(folder) -> [finding]`

Parse the index file into a list of findings, each normalised to the
**finding schema** below. This is the enumeration pass; it does not need
the deep evidence.

### `evidence(folder, finding_id) -> {detail, code_refs, reachability, remediation}`

Parse the evidence file for one finding: the full description, the cited
file paths + lines, the reachability / PoC reasoning, and the proposed
fix. This is the **load-bearing** read — the skill's Step B classifies
from this, not from the index summary.

### Finding schema (normalised)

Every adapter normalises a finding to:

| Field | Meaning |
|---|---|
| `id` | stable per-scan identifier (e.g. `FINDING-001`) |
| `title` | one-line description |
| `severity` | the scanner's severity label (treated as a *hypothesis*, not a verdict) |
| `level` | scanner rigor level, if any (e.g. ASVS `L1`/`L2`/`L3`) |
| `cwe` | CWE id(s), if cited |
| `files` | affected file paths (+ lines where given) |
| `attacker_capability` | what the attacker must already have — the load-bearing input for the trust-boundary mapping |
| `impact` | claimed impact |
| `remediation` | the scanner's proposed fix |

The skill treats `severity`/`level` as starting hypotheses and re-derives
the real disposition from the project's Security Model + precedents.

## Configuration

The adopter declares, in
[`<project-config>/project.md`](../../projects/_template/project.md):

- **scan sources** — the GitHub issues and/or report-tree roots the
  scanner publishes to (reference: `apache/tooling-agents`);
- **enabled formats** — which adapters under this directory are active
  (reference: `asvs`).

## What this contract does NOT cover

- **Classification.** Disposition is the triage skill's job
  ([`security-issue-triage`](../../skills/security-issue-triage/SKILL.md));
  the adapter only *reads* findings, it never decides them.
- **Where the report lands.** Gist / per-source comment / report-back PR
  routing is the skill's Step F, not the adapter's.

## Cross-references

- [`security-issue-import-from-scan`](../../skills/security-issue-import-from-scan/SKILL.md) — the consumer.
- [`tools/forwarder-relay/README.md`](../forwarder-relay/README.md) — a sibling pluggable-adapter contract this one mirrors.
