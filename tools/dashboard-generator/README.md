<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Dashboard generator](#dashboard-generator)
  - [Prerequisites](#prerequisites)
  - [Layout](#layout)
  - [Invocation](#invocation)
  - [Contract](#contract)
  - [When to use which](#when-to-use-which)
  - [Parity implementations](#parity-implementations)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Dashboard generator

**Capability:** substrate:analytics

**Harness:** agnostic

Deterministic reference implementations of the dashboard that
[`issue-reassess-stats`](../../skills/issue-reassess-stats/SKILL.md)
produces. Adopters who want CI-rendered dashboards (refreshed on
schedule, published as a build artefact) use one of these
reference scripts instead of invoking the agent.

The agent-emitted version (via the skill) is the **default**; the
reference implementations are a *deterministic* alternative for
adopters who want byte-for-byte reproducibility (CI pipelines,
audit trails).

## Prerequisites

- **Runtime:** Groovy (JVM) for the working `reference.groovy`
  (`MarkupBuilder` + `JsonSlurper`); `reference.py` is a Python 3
  stdlib-only stub.
- **CLIs:** `groovy` to run the Groovy reference. None beyond that.
- **Credentials / auth:** None.
- **Network:** None — reads local `<campaign-dir>/<KEY>/verdict.json`
  files and emits self-contained HTML (inline CSS, no JS, no external
  assets).

## Layout

```text
tools/dashboard-generator/
├── README.md          (this file)
├── reference.groovy   (Groovy implementation — MarkupBuilder + JsonSlurper)
└── reference.py       (Python stub — parity implementation welcome)
```

## Invocation

```bash
groovy tools/dashboard-generator/reference.groovy <campaign-dir> [--output <file>]
```

Reads `<campaign-dir>/<KEY>/verdict.json` files, computes the
dashboard payload per
[`issue-reassess-stats/aggregate.md`](../../skills/issue-reassess-stats/aggregate.md),
and emits the HTML per
[`issue-reassess-stats/render.md`](../../skills/issue-reassess-stats/render.md).

Without `--output`, HTML is written to stdout.

## Contract

The reference implementation matches the agent-emitted output for:

- Section ordering (hero cards → health → action → closure →
  new-issue → tracker-hygiene → per-component → oldest →
  per-issue table → methodology).
- Hero-card values and colour-coding thresholds.
- Health-rating thresholds.
- Recommendation rules (the 7-rule table in `render.md`).

The reference implementation deliberately does **not** match
free-form prose (e.g., the per-issue *"notes"* summary). For prose-
heavy dashboards, the agent-emitted version is better.

## When to use which

| Use case | Choice |
|---|---|
| Interactive maintainer view, one-off | Skill (`/magpie-issue-reassess-stats`) |
| CI pipeline, scheduled refresh | Reference implementation |
| Reproducible audit dashboard | Reference implementation |
| Custom layout for one campaign | Skill (with overrides) |

## Parity implementations

The Groovy reference exists today. A Python reference is a stub —
parity implementation welcome via PR. Other languages also welcome
as long as they:

1. Match the section ordering and threshold values.
2. Accept the same CLI shape (`<campaign-dir> [--output <file>]`).
3. Produce self-contained HTML (inline CSS, no JS, no external
   assets).

## Cross-references

- [`issue-reassess-stats`](../../skills/issue-reassess-stats/SKILL.md) —
  the agent-emitted version of the same dashboard.
- [`issue-reassess-stats/render.md`](../../skills/issue-reassess-stats/render.md) —
  the layout contract the references implement.
- [`<project-config>/reproducer-conventions.md`](../../projects/_template/reproducer-conventions.md) —
  the campaign directory layout.
