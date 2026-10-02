<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Maintainer-education stream
status: experimental
kind: docs
mode: infra
source: >
  MISSION.md § Maintainer education — building agentic projects is a
  different craft; MISSION.md § Initial Goals ("Ship the
  maintainer-education stream alongside v1"); PRINCIPLES.md §19
  (maintainer education ships with the platform, release-blocking).
  Referenced by docs/rfcs/RFC-AI-0004.md (§ "the maintainer-education
  stream"), which still points at MISSION.md. Implemented by
  docs/education/, docs/education/training/, and ai-tutors/.
acceptance:
  - A docs/education/ landing page exists and is linked from docs/index.md.
  - The landing page presents the material as an ordered learning
    progression: what agents are -> working with agents (conversational)
    -> choosing models -> your first skill -> writing safe skills ->
    debugging a skill -> writing portable skills -> eval-driven
    development -> agentic / autonomous work -> English as a programming
    language -> contributing to the framework. Writing and testing a skill
    precede agentic work, so autonomy is taught only after the reader has
    built and evaluated a skill.
  - Each progression stage exists as a page. The skill-writing steps keep
    the pattern catalogue as a supporting reference and the hands-on lab
    as practice; eval-driven development is a numbered stage on the main
    path, not a side reference.
  - The hands-on lab ships as tutorials.md (renamed from workshops.md).
  - The "your first skill" path is beginner-facing onboarding, distinct
    from the write-skill authoring reference.
  - Pages are project-agnostic (placeholders, PRINCIPLE 12) and land
    under Apache-2.0 (PRINCIPLE 17).
  - The dangling RFC-AI-0004 back-reference resolves to the landing page.
---

# Maintainer-education stream

## What it does

Lowers the on-ramp for maintainers who have never built an agentic
application. MISSION treats this as a first-class part of the project,
not an afterthought wiki page, and PRINCIPLE 18 makes it release-blocking:
"a platform without the education stream alongside it is not adoptable,
regardless of code quality." The mental model is genuinely different from
twenty years of writing services and CLIs — behaviour is probabilistic
not deterministic, prompts and skill files *are* code, evaluating output
is harder than testing a function, and the unit of authorship shifts from
"a function in a file" to "a skill the agent invokes." The stream teaches
that shift with worked, copy-pasteable material.

## Where it lives

The stream lives at `docs/education/`. It is the intended target of the
back-reference in `docs/rfcs/RFC-AI-0004.md`, which still points readers
at MISSION "for the maintainer-education stream". The material is organised as an **ordered
learning progression**, so a maintainer with no agentic background can read
it front to back, each page assuming only the ones before it:

- `docs/education/README.md` — landing page: what the stream is, who it
  is for, and the ordered progression index below. Linked from
  `docs/index.md`.
- `docs/education/what-agents-are.md` — **step 1.** The concept: what an
  agent is (model + tools + loop + context) and why probabilistic
  behaviour changes how you build and test.
- `docs/education/working-with-agents.md` — **step 2.** How to drive an
  agent through the conversational interface: anatomy of a good request,
  steering mid-task, and treating outside text as data.
- `docs/education/choosing-models.md` — **step 3.** How to use different
  models: the capability / speed / cost trade-off, judge models, local vs
  hosted, and letting evals decide. Model-neutral (skills call a model
  through a supplied command).
- `docs/education/your-first-skill.md` — **step 4.** A beginner
  "zero-to-merged" path for landing a first working skill, the agentic
  equivalent of a "your first PR" doc. Distinct from the `write-skill`
  skill, which is the authoring *reference* for someone who already knows
  the shape. Its supporting references are:
  - `docs/education/pattern-catalogue.md` — copy-pasteable skill / prompt
    / tool-use patterns with war stories: what worked, what did not, and
    why. Distinct from the PII pattern catalogue at
    `tools/privacy-llm/pii.md`, which is a redaction reference, not a
    teaching artefact.
  - `docs/education/tutorials.md` — the hands-on lab (renamed from
    `workshops.md`): build a small skill, give it an eval suite, and run
    it, self-paced or run for a group.
- `docs/education/writing-safe-skills.md` — **step 5.** Authoring patterns
  that hold the data-not-instructions and sandbox principles in every skill.
- `docs/education/debugging-skills.md` — **step 6.** Reading the audit log,
  reproducing a failure with the eval harness, and isolating prompt, tool,
  and model problems.
- `docs/education/portable-skills.md` — **step 7.** Writing skills that work
  for any project and any model, using placeholders and capability floors.
- `docs/education/eval-driven-development.md` — **step 8.** How to think
  about correctness when "correct" is a distribution, with worked examples
  drawn from real Magpie skills and wired to a shared eval methodology
  (MISSION § Initial Goals) rather than reinvented per page. A numbered
  stage on the main path: a skill is not finished without its eval suite,
  and agentic work depends on that evidence.
- `docs/education/agentic-work.md` — **step 9.** Agentic and autonomous
  work: the supervision spectrum and the guardrails (sandbox,
  propose-confirm-act, data-not-instructions) that make unattended runs
  safe. Placed after skill-writing and evals, because autonomy is what a
  written-and-tested skill unlocks.
- `docs/education/english-as-code.md` — **step 10.** English as a
  programming language: the mental shift that the words in a prompt or
  skill *are* the program — precision, ambiguity as a bug class, and
  reviewing / versioning / testing prose the way you would code.
- `docs/education/contributing.md` — **step 11.** How to contribute to the
  framework: turning what the reader has learned into a merged change,
  through the framework's contribution process.
- `docs/education/training/` — the stream repackaged as a reusable,
  LMS-neutral Apache Training module (the spec earlier named this
  directory `apache-training/`): `README.md` (module map back to the
  source pages), one `lesson-NN-*.md` per progression step (01 to 11, each
  with learning objectives, exercises, and self-check questions),
  `lesson-lab-tutorials.md` for the hands-on lab, `instructor-guide.md`,
  and `upstream-contribution.md`, the process document for handing the
  module to Apache Training.
- `ai-tutors/` (repository root) — one tutor prompt per lesson
  (`lesson-01-…` to `lesson-11-…`) that turns a chat model into an
  interactive tutor for that lesson, plus `inject-knowledge-base.py` and its
  test. The landing page and the training README link it; every lesson
  stands on its own without a model.

## Behaviour & contract

- **Release-blocking, per PRINCIPLE 18.** Every release ships the docs,
  patterns, eval examples, and tutorial material maintainers actually
  need for the skills that release includes. The stream is not a
  follow-up milestone.
- **Ordered progression, not a flat index.** The landing page sequences
  the pages so a reader with no agentic background can go front to back;
  each page states what it assumes and links forward to the next stage.
- **Project-agnostic, per PRINCIPLE 12.** Pages use
  `<PROJECT>` / `<tracker>` / `<upstream>` placeholders and never bake a
  concrete adopter name into the teaching text.
- **Apache-2.0, per PRINCIPLE 17.** Contributions to the stream land
  under the framework licence; AI-authored contributions carry the
  `Generated-by:` token.
- **Teaches the framework's own posture.** Examples inherit the
  data-not-instructions rule (PRINCIPLE 0), the privacy/sandbox posture
  (PRINCIPLE 1), and eval-as-release-discipline (PRINCIPLE 8) — the
  stream shows the safe pattern, never a shortcut around it.
- **Eval methodology is shared, not per-page.** The eval-driven-
  development page references the framework's shared eval methodology
  and the in-repo eval harness (`tools/skill-evals/`) rather than
  describing a parallel approach.

## Out of scope

- Owning the community-development mentoring *function* — that stays with
  ComDev (and, for podlings, the Incubator) for ASF projects. This stream
  ships education *material*, not a governance role (MISSION § Scope
  boundaries).
- Building a standalone contributor-sentiment eval framework. This
  stream consumes a shared eval methodology; it does not define or
  build one.
- Runtime skill behaviour — the education pages are docs, not skills, and
  make no state changes.

## Acceptance criteria

1. `docs/education/README.md` exists, is linked from `docs/index.md`, and
   presents the material as the ordered progression (steps 1–11).
2. Each progression stage exists as a page, in order: `what-agents-are.md`,
   `working-with-agents.md`, `choosing-models.md`, `your-first-skill.md`,
   `writing-safe-skills.md`, `debugging-skills.md`, `portable-skills.md`,
   `eval-driven-development.md`, `agentic-work.md`, `english-as-code.md`,
   and `contributing.md`. Skill-writing (steps 4 to 7) and eval-driven
   development (step 8) precede agentic work (step 9).
3. The skill-writing steps keep their supporting references
   (`pattern-catalogue.md` and the hands-on lab `tutorials.md`, renamed
   from `workshops.md`; no `workshops.md` remains).
4. The "your first skill" path is beginner onboarding, cross-linked to
   but distinct from `write-skill`.
5. Pages carry the SPDX header, use placeholders (no concrete adopter
   name in teaching text), and pass markdownlint / link checks.
6. The RFC-AI-0004 back-reference resolves to the landing page.
7. The Apache Training module (`docs/education/training/`) exists
   with per-lesson learning objectives, exercises, and self-checks, and
   is shaped for upstream contribution to Apache Training.

## Validation

The landing page and every progression stage are present under
`docs/education/` and linked from `docs/index.md`; the hands-on lab ships
as `tutorials.md` and no `workshops.md` remains.

```bash
test -f docs/education/README.md
test -f docs/education/what-agents-are.md
test -f docs/education/working-with-agents.md
test -f docs/education/choosing-models.md
test -f docs/education/agentic-work.md
test -f docs/education/your-first-skill.md
test -f docs/education/writing-safe-skills.md
test -f docs/education/debugging-skills.md
test -f docs/education/portable-skills.md
test -f docs/education/training/README.md
test -f docs/education/training/instructor-guide.md
test -f ai-tutors/README.md
test -f docs/education/pattern-catalogue.md
test -f docs/education/eval-driven-development.md
test -f docs/education/english-as-code.md
test -f docs/education/contributing.md
test -f docs/education/tutorials.md
test ! -f docs/education/workshops.md
grep -q "education" docs/index.md
uv run --project tools/spec-validator --group dev pytest
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **Progression restructure has shipped.** The landing page's table runs
  the eleven stages above in order, with the pattern catalogue and
  `tutorials.md` as supporting references, and no `workshops.md` remains.
  The earlier eight-step plan grew three skill-writing stages
  (safe, debugging, portable) on the way.
- **The RFC-AI-0004 back-reference still points at MISSION.md.** Its
  maintainer-education sentence links `MISSION.md`, not
  `docs/education/README.md`, so acceptance criterion 6 is open. The fix
  is an RFC edit, which this loop does not make.
- **Tutorial cadence undefined.** MISSION commits to "first scheduled
  workshops" but the schedule and hosting belong to the PMC once the
  material lands; `tutorials.md` ships the format, not the calendar.
- **Shared-methodology dependency.** The eval-driven-development page
  can land its worked examples immediately, but the link to the
  framework's shared contributor-sentiment methodology firms up only
  once that methodology is defined.
- **The Apache Training module exists; the upstream hand-off has not
  happened.** `docs/education/training/` carries all eleven lessons, the
  lab lesson, the instructor guide, and `upstream-contribution.md`. Its
  final shape still depends on coordination with the Apache Training
  project, which is outside the repository.
