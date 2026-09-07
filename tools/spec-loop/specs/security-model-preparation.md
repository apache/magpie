<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Security-model preparation (produce, verify, update)
status: experimental
kind: feature
mode: Drafting
source: >
  docs/security/security-model-preparation.md. The three
  security-model-* skills. The external rubric at
  https://github.com/alpha-omega-security/threat-model. Transplanted and
  generalised from the ASF security team's own model-preparation
  workflow.
acceptance:
  - A project with no model can reach a published, discoverable one via
    prepare → verify, with maintainer consent before the first repo write.
  - Discoverability is the only hard gate; completeness gaps are proposals.
  - The update loop never produces a model that closes a report the
    project historically fixed.
---

# Security-model preparation

## What it does

Gets a project's security model **written**, **findable**, and **current**
— the document the security-issue lifecycle routes findings against. Three
skills: produce a first model in draft-first mode and land it; pre-flight
an existing one for discoverability and completeness; and read the accrued
triage decisions back into it.

The rubric for *what a model contains* is maintained externally by
Alpha-Omega and referenced by URL. The framework keeps no local copy — a
second copy of a specification is a second specification. What the
framework owns is everything around it: consent, the discoverability
chain, PR mechanics, confidentiality scrubbing, and the feedback loop from
triage history back into the document.

## Where it lives

- Skills: `security-model-prepare` (Drafting), `security-model-verify`
  (Triage), `security-model-update` (Drafting).
- Helper: `skills/security-model-verify/scripts/model_pr.py` — the
  create-or-append `AGENTS.md` / `SECURITY.md` scaffold plus the PR
  mechanics, with the pure file-merge core unit-tested in
  `skills/security-model-verify/tests/`.
- Deep doc: `docs/security/security-model-preparation.md`.
- Adopter config: `<project-config>/security-model.md` § *Model
  preparation, verification, and update*.
- Threat model: skill family F in `docs/security/threat-model.md`
  (F.1–F.7, mitigations M.30–M.36).

## Behaviour & contract

- **Consent before the first repository write.** An unsolicited PR against
  a project that never asked costs a maintainer a review cycle they did
  not budget. The conversation goes to the private governance list first.
- **Discoverability (`AGENTS.md` → `SECURITY.md` → model) is the only hard
  gate.** A model an agent cannot reach is an absent one. Completeness is
  graded: every gap is a proposal the maintainer decides on, never a
  precondition.
- **Mechanical gap → PR; substantive gap → private mail; never a public
  issue.** A public list of a project's threat-model gaps is an inventory
  a hostile researcher would mine, many projects have no usable public
  tracker, and maintainers who read mail may never see a tracker
  notification.
- **Provenance on every non-trivial claim** (documented / maintainer /
  assumption / inferred). An inferred claim resolves to a numbered open
  question and never licenses a closing disposition — that is what makes a
  draft written by a non-maintainer safe to publish in the project's
  voice.
- **The asymmetry governs every judgement call.** Wrongly escalating a
  non-finding wastes an afternoon; wrongly closing a real vulnerability
  answers a live issue with "not a bug". Narrow a claim to resolve a
  conflict; never widen one.
- **Known non-findings are fenced.** Only a recurring
  `BY-DESIGN: property-disclaimed` close feeds the section; no
  `OUT-OF-MODEL:*` route is ever promoted (it sits below the section in
  the precedence order, so promoting it lifts it above the checks that
  decided it); report quality is never a match condition; two independent
  occurrences minimum.
- **Private in, public out.** The update loop's input is the tracker and
  its output is a public document, so it scrubs before *display*, not
  before send.
- **No programme, vendor, or engagement identity on a public surface** —
  PR titles, bodies, commit messages, branch names.

## Out of scope

- Writing the model rubric. That is the external Alpha-Omega
  specification; the framework cites section numbers as coordinates into
  it and does not vendor, mirror, or fork it.
- Routing an individual inbound report — that is
  [`security-issue-triage`](security-issue-lifecycle.md).
- Bug hunting. A model describes the project as it is, not its defects; a
  vulnerability found while modelling goes to the security process.
- Installing the external skill set. The rubric is referenced by URL; no
  skill-source descriptor or pinned fetch is wired in.

## Acceptance criteria

1. Each skill is confirm-before-apply: no PR pushed and no mail drafted
   into an outbox before the artefact has been shown and approved.
2. Verify reports a per-repository grid, never a collapsed verdict, and
   fails hard only on discoverability.
3. The update loop's regression check is blocking: a proposal that would
   close a historically fixed report does not ship, and is resolved only
   by narrowing.
4. No proposed model diff contains reporter identity, tracker contents, an
   unpublished CVE ID, or detail of an unfixed issue.
5. The PR scaffold is idempotent and never edits existing prose.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --directory skills --project . python -m pytest security-model-verify/tests/
```

## Known gaps

- The eval suites (35 cases across 7 steps) cover the decision points —
  discoverability remediation split, completeness grading,
  disposition mapping, the known-non-finding entry rules, the regression
  gate, the consent gate, and provenance tagging. They do not cover the
  composition steps (PR body, mail body), which are prose and would need
  structural fixtures.
- Delegation to the external Alpha-Omega skill set is by reference, so a
  session without those skills installed follows the published rubric by
  URL rather than invoking its specialists. Wiring it as a pinned skill
  source is a deliberate non-goal today, not an oversight.
