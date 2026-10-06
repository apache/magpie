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
  docs/modes.md § Mentoring (experimental, 7 skills). Spec exists at
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
- Skills ship across three plugins, each reachable through a
  `skills/<dir>` symlink: `plugins/magpie-mentoring/skills/`
  (`welcome` as `mentoring-welcome`, `good-first-issue-author`,
  `good-first-issue-sweep`, `newcomer-issue-explainer`),
  `plugins/magpie-contributor-growth/skills/`
  (`contributor-to-committer`, `onboarding-concierge`), and
  `plugins/magpie-pr-management/skills/mentor/`
  (`pr-management-mentor`).
- Adopter config scaffolds in `plugins/magpie-setup/templates/`
  (`projects/_template` is a symlink to it): `mentoring-config.md`
  (`pr-management-mentor`; its `out_of_scope_topics` also gates
  `mentoring-welcome`), `mentoring-welcome-config.md`,
  `good-first-issue-config.md`, `onboarding-concierge-config.md`,
  `newcomer-issue-explainer-config.md`, and `committer-readiness.md`.
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
- Skill: `contributor-to-committer` — read-only activity brief that
  shows a contributor's GitHub activity next to the adopter's committer
  or PMC reference levels as plain numbers; no status, band, ranking, or
  readiness verdict — the PMC decides. Counts come from `tools/contributor-metrics`, discounted for
  automated and low-signal work, and community signals are collected in
  Step 3 (see [contributor-growth.md](contributor-growth.md)).
  Ships `mode: Mentoring` + `experimental`, with an eval suite
  under `tools/skill-evals/evals/contributor-to-committer/`.
- Skill: `good-first-issue-sweep` — sweeps the open issue backlog for
  existing issues that could be labelled as good first issues. Scores each
  candidate against the G1–G7 suitability rubric and classifies it as
  READY (propose the GFI label), NEAR-MISS (surface specific edits to make
  it GFI-ready), or SKIP. Applies labels only after explicit maintainer
  confirmation; never edits issue bodies. Ships `mode: Mentoring` +
  `experimental`, with an eval suite under
  `tools/skill-evals/evals/good-first-issue-sweep/`.
- Skill: `onboarding-concierge` — answers a newcomer's "how do I
  contribute here" question by grounding the reply in
  `CONTRIBUTING.md` and the project's own docs. Classifies the question
  (setup / workflow / first-issue / out-of-scope), retrieves the
  relevant excerpt, and drafts a concise answer in the teaching
  register; design, security, deprecation, and architectural-taste
  questions are handed to a human maintainer. Produces draft text only.
  Ships `mode: Mentoring` + `experimental`, with an eval suite under
  `tools/skill-evals/evals/onboarding-concierge/`.
- Skill: `newcomer-issue-explainer` — given an open good first issue,
  explains it in beginner terms and sketches an approach (files to read
  first, what "done" looks like, where to ask) without writing any code.
  An issue-assessment gate declines closed, security-sensitive, or
  scope-unclear issues. Nothing is posted without maintainer
  confirmation. Ships `mode: Mentoring` + `experimental`, with an eval
  suite under `tools/skill-evals/evals/newcomer-issue-explainer/`.

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
test -f .agents/skills/magpie-good-first-issue-author/SKILL.md
test -f .agents/skills/magpie-mentoring-welcome/SKILL.md
test -f .agents/skills/magpie-contributor-to-committer/SKILL.md
test -f .agents/skills/magpie-good-first-issue-sweep/SKILL.md
test -f .agents/skills/magpie-onboarding-concierge/SKILL.md
test -f .agents/skills/magpie-newcomer-issue-explainer/SKILL.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/good-first-issue-author/
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/mentoring-welcome/
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/good-first-issue-sweep/
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/onboarding-concierge/
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/newcomer-issue-explainer/
```

## Known gaps

- **The family now covers the newcomer journey end to end.**
  All seven skills ship: `pr-management-mentor`, `good-first-issue-author`,
  `mentoring-welcome` (first-contribution welcome / orientation),
  `onboarding-concierge` (how-to-contribute answers),
  `newcomer-issue-explainer` (beginner explanation of a filed issue),
  `contributor-to-committer` (readiness path tracker), and
  `good-first-issue-sweep` (backlog curation / labelling). The on-ramp
  supply chain is complete from both the authoring side
  (`good-first-issue-author`) and the curation side (`good-first-issue-sweep`).
- **Mode and plugin do not line up.** The seven `mode: Mentoring` skills
  ship in three plugins (`magpie-mentoring`, `magpie-contributor-growth`,
  `magpie-pr-management`); see
  [contributor-growth.md](contributor-growth.md) § Known gaps.
- **`experimental` — no adopter pilot has run.** All seven shipped skills
  may change shape as adopter pilots and contributor-sentiment evaluations
  land.
- **`good-first-issue-author` and `good-first-issue-sweep` shipped
  `experimental`; no adopter pilot has run live good first issue
  workflows yet.** The G1–G7 suitability thresholds and the R1–R9
  readiness checklist may shift once real backlog candidates flow through
  the skills.
- **`mentoring-welcome` shipped `experimental`; no adopter pilot run.**
  The welcome tone, detecting first-timer vs. repeat contributor, and
  the content of the orientation template may shift once live threads run
  through it.
