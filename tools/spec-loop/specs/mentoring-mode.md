<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Mentoring mode
status: experimental
kind: feature
mode: Mentoring
source: >
  MISSION.md § Technical scope (Mentoring) — "the highest-value
  project-side mode and the one off-the-shelf agent tooling skips".
  docs/modes.md § Mentoring (experimental, 1 skill). Spec exists at
  docs/mentoring/spec.md ahead of any skill code.
acceptance:
  - The Mentoring spec (tone guide, hand-off protocol, adopter knobs) is
    reviewable independently of any runtime skill (it already is).
  - The first skill ships flagged mode Mentoring + experimental and joins
    threads in a teaching register, never gatekeeps.
  - Hand-off to a human is explicit when scope exceeds the agent.
---

# Mentoring mode

## What it does

Joins issue and PR threads in a deliberately teaching register:
clarifying questions, pointers to project conventions and docs, an
explanation of *why* a change is being asked for, paired examples from
similar prior PRs, and a clean hand-off to a human reviewer when the
question exceeds what an agent should answer. MISSION names this the
contributor-empowerment lever the wider ecosystem most needs.

## Where it lives

- Spec: `docs/mentoring/README.md`, `docs/mentoring/spec.md`.
- Adopter config scaffold: `projects/_template/mentoring-config.md`.
- Skill: `pr-management-mentor` — drafts a teaching-register comment on
  a single GitHub issue or PR thread; waits for explicit maintainer
  confirmation before posting. Ships `mode: Mentoring` + `experimental`.

## Behaviour & contract

- **Teaching register, never gatekeeping.** The most sensitive surface
  in the project (MISSION § Particular care): a condescending agent that
  drives a contributor away is not patchable. Tone is the project's to
  set (`mentoring-config.md`).
- Read-only / drafts replies for human review; never closes or rejects a
  contributor's work on its own.
- Explicit hand-off protocol when the question is out of the agent's
  depth.

## Out of scope

- Implementation-detail review that belongs to Pairing
  ([Pairing](pairing-mode.md)).
- Any contributor-facing message sent without human review.

## Acceptance criteria

1. The Mentoring spec is reviewable without any skill code (it is).
2. The first Mentoring skill validates and carries `mode: Mentoring`.
3. Hand-off-to-human is documented and enforced.

## Validation

```bash
test -f docs/mentoring/spec.md
uv run --project tools/skill-validator --group dev skill-validate
```

## Known gaps

- **`experimental` — no adopter pilot has run.** The first skill
  (`pr-management-mentor`) shipped; shape may change as adopter pilots
  and contributor-sentiment evaluations land.
