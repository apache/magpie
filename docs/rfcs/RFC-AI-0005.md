<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [RFC-AI-0005: Framework taxonomy](#rfc-ai-0005-framework-taxonomy)
  - [Abstract](#abstract)
  - [Status of this document](#status-of-this-document)
  - [Motivation](#motivation)
  - [The taxonomies at a glance](#the-taxonomies-at-a-glance)
  - [Capability — the two-axis model](#capability--the-two-axis-model)
    - [Axis 1 — Skill capability (what a workflow *does*)](#axis-1--skill-capability-what-a-workflow-does)
    - [Axis 2 — Tool capability (what a backend *provides*)](#axis-2--tool-capability-what-a-backend-provides)
    - [How the two axes link](#how-the-two-axes-link)
  - [The other taxonomies (unchanged, documented here for completeness)](#the-other-taxonomies-unchanged-documented-here-for-completeness)
    - [`family:*` — subject](#family--subject)
    - [`kind:*` — change type](#kind--change-type)
    - [`mode:*` — agentic mode](#mode--agentic-mode)
    - [`organization:` — organization membership / inheritance](#organization--organization-membership--inheritance)
    - [Standalone labels](#standalone-labels)
  - [Migration](#migration)
  - [Out of scope](#out-of-scope)
  - [References](#references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# RFC-AI-0005: Framework taxonomy

## Abstract

Magpie classifies its issues, skills, and tools with several label
dimensions — `family:`, `capability:`, `kind:`, `mode:`, and the newer
`organization:` scope. This RFC documents the **whole** taxonomy in one
place and fixes the one dimension that has drifted: **`capability:`**.

Today a single capability vocabulary is stamped on two very different
entities — *skills* (where it names a workflow-lifecycle phase) and
*tools* (where it should name a technical interface). The mismatch
collapses ~75% of tools into a meaningless catch-all bucket and
leaves four capabilities with no tool ever using them. This RFC splits
`capability:` into two orthogonal axes — **skill capability** (what a
workflow does) and **tool capability** (what a backend provides, = the
contract it implements) — and specifies the migration.

## Status of this document

**Proposed.** Implemented in the same change set that lands this RFC
(`skill-and-tool-validator`, every `tools/*/README.md`, the
`setup`-capability skills, `docs/labels-and-capabilities.md`, and the
`AGENTS.md` / `tools/AGENTS.md` labeling sections). Supersedes the single
`capability:` vocabulary described in earlier revisions of
`docs/labels-and-capabilities.md`.

## Motivation

`docs/labels-and-capabilities.md` defines nine capabilities — `triage`,
`review`, `fix`, `intake`, `reconciliation`, `resolve`, `reassess`,
`stats`, `setup` — and applies them to both skills and tools. Measured
against the live tree:

- **The `setup` capability is a grab-bag — 24 of 33 tools.** It is stamped
  on entities with nothing in common: API substrate (`github`, `jira`,
  `gmail`, `vcs`), adapter *contracts* (`cve-tool`, `mail-archive`,
  `forwarder-relay`, `scan-format`, `mail-source`), a command guard
  (`agent-guard`), sandbox/isolation (`agent-isolation`,
  `egress-gateway`, `probe-templates`, `sandbox-lint`,
  `permission-audit`), PII redaction (`privacy-llm`), the framework
  dev-loop (`dev`, `spec-loop`, `spec-validator`,
  `skill-and-tool-validator`, `spec-status-index`, `skill-evals`), and
  context-safe helpers (`github-body-field`, `github-rollup`).
- **Four capabilities have zero tools** — `triage`, `review`, `fix`,
  `reassess`. They only ever describe a skill.
- **The surviving tool buckets are too coarse** — `stats` lumps a data
  *source* (`apache-projects`) with HTML *renderers*
  (`dashboard-generator`); `resolve` on a tool means only "CVE
  authority".

**Root cause.** The nine capabilities are *workflow-lifecycle phases* —
the right model for **skills** (orthogonal to `family:`). A lifecycle phase
is the wrong model for a **tool**, which has a *technical interface*, not
a phase. The framework already has the right concept for a tool's
capability: the **capability contract** (`tools/cve-tool/`,
`mail-archive/`, `forwarder-relay/`, `scan-format/`, plus
`source-control` and the tracker interface). A tool's real capability is
*the contract it implements* — but that is not what `**Capability:**`
records.

## The taxonomies at a glance

| Dimension | Applies to | Answers | Source of truth |
|---|---|---|---|
| `family:*` | issues, PRs | *which part of the framework?* | this RFC + `docs/labels-and-capabilities.md` |
| **skill capability** | skills, issues, PRs | *what lifecycle phase does the workflow perform?* | this RFC + `docs/labels-and-capabilities.md` |
| **tool capability** | tools / adapters | *what interface/contract does the backend provide?* | this RFC + the adapter [registry](../adapters/registry.md) |
| `kind:*` | issues, PRs | *what type of change?* | `docs/labels-and-capabilities.md` |
| `mode:*` | skills, issues | *which agentic mode / risk tier?* | `docs/modes.md` |
| `organization:` | skills, families, tools, projects | *which organization does this belong to / inherit from?* | `organizations/README.md` |

The change in this RFC is splitting the third row out of the second.

## Capability — the two-axis model

### Axis 1 — Skill capability (what a workflow *does*)

The lifecycle phase a skill performs, orthogonal to `family:`:

`triage · review · fix · intake · reconciliation · resolve · reassess ·
stats · platform · authoring`

This is the previous list with `setup` **split** into:

- **`platform`** — framework/agent substrate skills: install, verify,
  update, doctor, override-upstream, status, shared-config-sync, the
  `setup` bootstrap.
- **`authoring`** — skills that author or maintain *other* skills:
  `write-skill`, `optimize-skill`.

Splitting `setup` removes the last overloaded skill bucket: "stand up the
agent" (`platform`) and "write a workflow" (`authoring`) are different
jobs and were both `setup`.

### Axis 2 — Tool capability (what a backend *provides*)

A tool's capability is **the contract / interface it implements**, drawn
from a controlled vocabulary that mirrors the capability contracts plus a
small set of substrate kinds:

| Tool capability | Kind | What it provides |
|---|---|---|
| `tracker` | contract | issue / PR / board / label backend |
| `source-control` | contract | branch / commit / diff / push (VCS) |
| `mail-archive` | contract | public mailing-list / forum archive reads |
| `mail-source` | contract | inbound-mail ingestion (mbox / IMAP / …) |
| `mail-create` | contract | outbound mail composition — always an editable draft; sending is a separate human-approved step (draft mode default and only mode implemented; send mode declared, unimplemented) |
| `cve-authority` | contract | CVE allocation / record management / publication |
| `report-relay` | contract | inbound security-report relay detection |
| `scan-format` | contract | security-scanner report parsing |
| `project-metadata` | contract | governance rosters / people / releases |
| `analytics` | substrate | read-only metrics / dashboards / renderers |
| `sandbox` | substrate | agent isolation, egress control, settings audit |
| `action-guard` | substrate | deterministic pre-tool-use command guards |
| `privacy` | substrate | PII redaction / approved-LLM gating |
| `framework-dev` | substrate | build / validate / eval the framework itself |

The *contract* rows are exactly the seams an [adapter](../vendor-neutrality.md#tool-adapters)
plugs into; the tool capability of an adapter is the contract it
fulfils. The *substrate* rows replace the old `setup`
catch-all with meaningful kinds.

### How the two axes link

A **skill consumes** tool capabilities (the contracts it needs); a
**tool provides** one. This is the edge the single vocabulary could not
express:

> `security-issue-import` (skill capability `intake`) consumes the
> `mail-archive` + `mail-source` tool capabilities; `ponymail` provides
> `mail-archive`.

`docs/labels-and-capabilities.md` therefore carries **two** maps: a
*skill → skill-capability* map, and a *contract → adapters* map (the same
table as the adapter [registry](../adapters/registry.md)).

## The other taxonomies (unchanged, documented here for completeness)

### `family:*` — subject

`family:pr-management`, `family:security`, `family:setup`, `family:issue`,
`family:tools`, `family:ci`, `family:docs`. Orthogonal to capability: a
triage-rule change in PR management and one in security are both skill
capability `triage`, in different `family:`s.

### `kind:*` — change type

`kind:dx` (maintainer dev-loop / CLI UX), `kind:policy` (rule changes),
`kind:perf` (token / latency / API-call budget), `kind:adopter-config`
(per-adopter knob).

### `mode:*` — agentic mode

The five modes from `docs/modes.md`: **Agentic Triage**, **Agentic
Mentoring**, **Agentic Drafting**, **Agentic Pairing**, **Agentic
Autonomous** (off by default), plus `mode:cross-cutting` and
`mode:platform` for substrate that is not a mode. `mode:` is the *risk
tier* of an action; skill capability is the *phase*. A skill carries
both (e.g. `pr-management-code-review`: capability `review`, mode
Pairing/Drafting).

### `organization:` — organization membership / inheritance

Per RFC context in `organizations/README.md`: a skill, skill family,
tool, or project may declare the organization it belongs to / inherits
from. Absent = organization-agnostic. Distinct from the dimensions above
— it scopes *which governing body's defaults apply*, not what the entity
does.

### Standalone labels

`marketing`, `dependencies`, `python:uv`, and the default GitHub labels
(`bug`, `enhancement`, `documentation`, `good first issue`, …).

## Migration

1. **Validator** (`skill-and-tool-validator`): replace the single
   `ALLOWED_CAPABILITIES` with `SKILL_CAPABILITIES` (Axis 1) and
   `TOOL_CAPABILITIES` (Axis 2); skill-frontmatter validation checks
   Axis 1, tool-README validation checks Axis 2; the capability-sync
   check splits into the two maps. Tests updated.
2. **Tools**: rewrite every `tools/*/README.md` `**Capability:**` line to
   its Axis-2 value (see the registry / `labels-and-capabilities.md` map).
3. **Skills**: re-label the `setup` skills to `platform` or
   `authoring`.
4. **Docs**: `docs/labels-and-capabilities.md` becomes two maps;
   `AGENTS.md` labeling + `tools/AGENTS.md` updated.
5. **Evals**: any eval fixture asserting a capability value updated.
6. **GitHub labels** (follow-up, optional): the `capability:*` issue
   labels are renamed/added to match; existing issues relabelled.

The change is breaking for the `**Capability:**` declaration format but
mechanical once the vocabulary is fixed; the skill *lifecycle* phases are
unchanged except for the `setup` split.

## Out of scope

- Reworking `family:`, `kind:`, or `mode:` — documented here, unchanged.
- A per-capability *floor* spec for tools (which contract version an
  adapter targets) — a possible future RFC.

## References

- `docs/labels-and-capabilities.md` — the implementing taxonomy doc.
- `docs/vendor-neutrality.md` — tool adapters + capability contracts.
- `docs/adapters/registry.md` — the contract → adapters map.
- `docs/modes.md` — the agentic modes.
- `organizations/README.md` — the organization dimension.
