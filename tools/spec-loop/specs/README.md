<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Specs

Each file here describes **one functional area of the product** — what it
does, where it lives in the code, the contract it must honour, and its
known gaps. They are modelled on the way a game's specs describe its
battle, magic, and inventory systems: a faithful description of the
intended behaviour that the build loop reconciles the code against.

Filenames are **topics, not ordered identifiers** — there are no number
prefixes, because numbering implies a priority the specs don't have.
Priority lives in [`../IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md).

## Separate from the RFCs

These specs are **not** RFCs. The RFCs in
[`../../../docs/rfcs/`](../../../docs/rfcs/) are the normative governance
layer ("the constitution"); the loop **respects** them as constraints but
never reads or edits them. Specs are the *functional description of the
actual codebase*. A spec may cite a principle as a constraint; it never
restates one and never lives in `docs/rfcs/`.

## The specs

Start with [`overview.md`](overview.md), then:

- Modes: [`triage-mode.md`](triage-mode.md),
  [`mentoring-mode.md`](mentoring-mode.md),
  [`drafting-mode.md`](drafting-mode.md),
  [`pairing-mode.md`](pairing-mode.md).
- Cross-cutting: [`security-issue-lifecycle.md`](security-issue-lifecycle.md),
  [`release-management-lifecycle.md`](release-management-lifecycle.md),
  [`privacy-llm-gate.md`](privacy-llm-gate.md),
  [`agent-isolation-sandbox.md`](agent-isolation-sandbox.md),
  [`cve-tooling.md`](cve-tooling.md),
  [`adoption-and-setup.md`](adoption-and-setup.md),
  [`adapters.md`](adapters.md),
  [`project-agnosticism.md`](project-agnosticism.md),
  [`meta-and-quality-tooling.md`](meta-and-quality-tooling.md),
  [`security-reporting.md`](security-reporting.md),
  [`reviewer-routing.md`](reviewer-routing.md),
  [`skill-reconciler.md`](skill-reconciler.md).

(Agentic Autonomous, the fifth MISSION mode, is deliberately off and has no
spec — see the note in [`overview.md`](overview.md).)

## Spec format

Frontmatter:

```yaml
---
title: <functional area>
status: experimental   # stable | experimental | proposed | off
kind: feature          # feature | fix | docs | chore
mode: Triage           # Triage | Mentoring | Drafting | Pairing | infra
source: <MISSION.md clause / code paths this area is grounded in>
acceptance:
  - <verifiable criterion>
---
```

Body sections: **What it does**, **Where it lives**, **Behaviour &
contract**, **Out of scope**, **Acceptance criteria**, **Validation**,
and (optional) **Known gaps** — the gaps are what the loop's plan pass
turns into work items.

Status mirrors [`docs/modes.md`](../../../docs/modes.md): `stable`,
`experimental`, `proposed` (designed in MISSION, no code yet), `off`
(deliberately not built).

## Adding a spec

1. Name the file for its topic (no number prefix).
2. Fill in the frontmatter and the body sections above.
3. Keep **Acceptance criteria** and **Validation** objective — they are
   the loop's backpressure.
