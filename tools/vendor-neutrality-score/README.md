<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [vendor-neutrality-score](#vendor-neutrality-score)
  - [Prerequisites](#prerequisites)
  - [What it reads](#what-it-reads)
  - [The scoring rule](#the-scoring-rule)
  - [Usage](#usage)
  - [Run tests](#run-tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# vendor-neutrality-score

**Capability:** substrate:framework-dev + substrate:analytics

A deterministic `uv` tool that scores Magpie's vendor neutrality from
repository metadata alone — no network, no judgement at runtime. It
answers the question raised in
[apache/magpie-site#17](https://github.com/apache/magpie-site/issues/17):
*for each capability contract, does Magpie already work across more than
one vendor, and is any skill locked to a vendor with no alternative?*

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; stdlib-only (no runtime
  dependencies). The `dev` group pulls `pytest`.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline; reads `tools/*/README.md` and
  `skills/*/SKILL.md` from the local checkout.

## What it reads

Three machine-readable inputs, so the same tree always yields the same
score:

1. **`tools/*/README.md`** — each contract tool declares `**Capability:**`
   (the `contract:<name>` it fulfils), `**Kind:**` (`interface` for a pure
   spec, `implementation` for a concrete backend), and `**Vendor:**` (the
   backend identity, or `agnostic` for an interface).
2. **`skills/*/SKILL.md`** — the `organization:` frontmatter field plus the
   skill body, scanned for the concrete backends it names.
3. **The policy** in `src/vendor_neutrality_score/__init__.py`
   (`CONTRACT_POLICY`) — which of three neutrality *classes* each contract
   belongs to. This is the only hand-maintained input.

## The scoring rule

Substrate tools are Magpie's own machinery and never count. Each
capability **contract** is scored by its class:

| Class | GREEN when | Examples |
|---|---|---|
| `vendor-backed` | ≥ 2 distinct backend vendors implement it | tracker (GitHub + Jira), source-control (Git + Subversion) |
| `agnostic` | always — one vendor-neutral spec serves every backend | report-relay, scan-format |
| `single-org` | always — bound to one organisation's data model; no vendor choice | project-metadata |

Overall score = `green_contracts / total_contracts`.

Each **skill** is then classified as *capability-pure* (names no
backend), *portable* (every backend it names has an alternative), or
*vendor-coupled* (reaches for the sole implementation of a capability).
Declared `organization:` scope is reported as an orthogonal dimension.

## Usage

```bash
# Human-readable report (per-contract + per-skill summary)
uv run --project tools/vendor-neutrality-score vendor-neutrality-score

# Machine-readable JSON
uv run --project tools/vendor-neutrality-score vendor-neutrality-score --json

# Regenerate the block embedded in docs/vendor-neutrality.md
uv run --project tools/vendor-neutrality-score vendor-neutrality-score --markdown

# CI gate: fail if neutrality drops below a threshold
uv run --project tools/vendor-neutrality-score vendor-neutrality-score --fail-under 80
```

## Run tests

```bash
uv run --project tools/vendor-neutrality-score --group dev pytest
```
