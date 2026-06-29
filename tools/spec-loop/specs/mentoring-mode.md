<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Agentic Mentoring mode
status: experimental
kind: feature
mode: Mentoring
source: >
  MISSION.md § Technical scope (Mentoring) — "the highest-value
  project-side mode and the one off-the-shelf agent tooling skips".
  docs/modes.md § Mentoring (experimental, 3 skills). Spec exists at
  docs/mentoring/spec.md ahead of any skill code. MISSION.md names
  onboarding latency as one of the two loudest ecosystem complaints;
  authoring newcomer-ready good first issues targets it directly.
acceptance:
  - The Agentic Mentoring spec (tone guide, hand-off protocol, adopter knobs) is
    reviewable independently of any runtime skill (it already is).
  - The first skill ships flagged mode Mentoring + experimental and joins
    threads in a teaching register, never gatekeeps.
  - Hand-off to a human is explicit when scope exceeds the agent.
  - The good-first-issue authoring skill drafts net-new, newcomer-ready
    issues (scope, code pointers, contributing-doc links, effort estimate)
    and never files them without maintainer confirmation.
  - The first-contact welcome skill greets first-time contributors with
    project-convention pointers, never posts without confirmation, and
    skips repeat contributors.
---

# Agentic Mentoring mode

## What it does

Joins issue and PR threads in a deliberately teaching register:
clarifying questions, pointers to project conventions and docs, an
explanation of *why* a change is being asked for, paired examples from
similar prior PRs, and a clean hand-off to a human reviewer when the
question exceeds what an agent should answer. MISSION names this the
contributor-empowerment lever the wider ecosystem most needs.

A second capability turns small, well-bounded tasks into
net-new *good first issues*. It takes a known gap or a maintainer-supplied
small task and drafts a self-contained issue a newcomer can pick up
without prior repo context: the draft states the scope, links the relevant
code and the project's contributing docs, lists acceptance criteria, and
gives a rough effort estimate. Lowering onboarding latency is the point. A
good first issue that is genuinely self-contained is the cheapest on-ramp
a project can offer a first-time contributor.

## Where it lives

- Spec: `docs/mentoring/README.md`, `docs/mentoring/spec.md`.
- Adopter config scaffold: `projects/_template/mentoring-config.md`.
- Skill: `pr-management-mentor` — drafts a teaching-register comment on
  a single GitHub issue or PR thread; waits for explicit maintainer
  confirmation before posting. Ships `mode: Mentoring` + `experimental`.
- Skill: `good-first-issue-author`. Drafts one net-new good first issue
  from a supplied known gap or small task, carrying scope, code pointers,
  contributing-doc links, acceptance criteria, and an effort estimate. A
  suitability gate declines candidates that are too large,
  security-sensitive, or need a design or deprecation decision; a
  readiness checklist (R1-R9) gates the draft. Waits for maintainer
  confirmation before any issue is filed via `gh`. Ships `mode: Mentoring`
  + `experimental`, with an eval suite under
  `tools/skill-evals/evals/good-first-issue-author/`.
- Skill: `mentoring-welcome` — drafts a first-contact orientation comment
  for a first-time contributor on a newly opened issue or PR. Detects
  first-time authorship via the GitHub `author_association` field and
  drafts a welcome with contributing-guide link, community-norm pointers,
  and expected next steps. Does not post for repeat contributors; waits
  for explicit maintainer confirmation before posting. Ships `mode:
  Mentoring` + `experimental`, with an eval suite under
  `tools/skill-evals/evals/mentoring-welcome/`.

## Behaviour & contract

- **Teaching register, never gatekeeping.** The most sensitive surface
  in the project (MISSION § Particular care): a condescending agent that
  drives a contributor away is not patchable. Tone is the project's to
  set (`mentoring-config.md`).
- Read-only / drafts replies for human review; never closes or rejects a
  contributor's work on its own.
- Explicit hand-off protocol when the question is out of the agent's
  depth.
- **Good first issues are drafted, never filed.** The authoring skill
  emits one issue draft for maintainer review and only files it (via `gh`)
  after explicit confirmation. It sources candidates from supplied known
  gaps or maintainer-named small tasks; it does not invent work or scope a
  task beyond what a newcomer can finish unaided.

## Out of scope

- Implementation-detail review that belongs to Agentic Pairing
  ([Pairing](pairing-mode.md)).
- Any contributor-facing message sent without human review.
- Curating or bulk-labeling the *existing* backlog as good first issues:
  this skill authors net-new drafts only. Backlog curation and labeling is
  a separate capability that is not specced yet.

## Acceptance criteria

1. The Agentic Mentoring spec is reviewable without any skill code (it is).
2. The first Agentic Mentoring skill validates and carries `mode: Mentoring`.
3. Hand-off-to-human is documented and enforced.
4. The `good-first-issue-author` skill validates, carries
   `mode: Mentoring`, and produces a single newcomer-ready issue draft
   (scope, code pointers, contributing-doc links, acceptance criteria,
   effort estimate) that is never filed without maintainer confirmation.

## Validation

```bash
test -f docs/mentoring/spec.md
test -f .claude/skills/magpie-good-first-issue-author/SKILL.md
test -f .claude/skills/magpie-mentoring-welcome/SKILL.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/good-first-issue-author/
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/mentoring-welcome/
```

## Known gaps

- **The family now covers the newcomer journey end to end.**
  `pr-management-mentor`, `good-first-issue-author`, `mentoring-welcome`
  (first-contribution welcome / orientation), and `contributor-to-committer`
  (readiness path tracker) all ship. `docs/mentoring/README.md` reflects all
  four shipped skills. The two newcomer-facing capabilities this spec
  previously flagged as undesigned are both built; the open item that remains
  is the backlog-curation counterpart noted above (relabeling the existing
  backlog as good-first-issue candidates).
- **`experimental` — no adopter pilot has run.** All four shipped skills
  (`pr-management-mentor`, `good-first-issue-author`, `mentoring-welcome`)
  and `contributor-to-committer` may change shape as adopter pilots and
  contributor-sentiment evaluations land.
- **`good-first-issue-author` shipped `experimental`; no adopter pilot
  has authored a live good first issue through it yet.** The suitability
  and readiness thresholds may shift once real backlog candidates run
  through it. The curation counterpart (relabeling the *existing* backlog
  as good-first-issue candidates) is still unspecced.
- **`mentoring-welcome` shipped `experimental`; no adopter pilot run.**
  The welcome tone, detecting first-timer vs. repeat contributor, and
  the content of the orientation template may shift once live threads run
  through it.
