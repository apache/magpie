<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Upstream contribution guide — Apache Training module](#upstream-contribution-guide--apache-training-module)
  - [Who this guide is for](#who-this-guide-is-for)
  - [What we are contributing](#what-we-are-contributing)
  - [Prerequisites before submitting](#prerequisites-before-submitting)
  - [Licensing](#licensing)
  - [Placeholder convention](#placeholder-convention)
  - [Submission process](#submission-process)
    - [1. Open a thread on the Apache Training dev list](#1-open-a-thread-on-the-apache-training-dev-list)
    - [2. Align on format](#2-align-on-format)
    - [3. Prepare the submission branch](#3-prepare-the-submission-branch)
    - [4. Open a pull request](#4-open-a-pull-request)
    - [5. Coordinate ongoing maintenance](#5-coordinate-ongoing-maintenance)
  - [Pilot record](#pilot-record)
    - [Entry format](#entry-format)
    - [Where the record lives](#where-the-record-lives)
  - [Contact points](#contact-points)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Upstream contribution guide — Apache Training module

This guide is for coordinators and `<governance-body>` members who want to
submit the `docs/education/training/` module to
[Apache Training](https://training.apache.org/) so it can be taught beyond
the projects that adopted this framework.

It is not a lesson and not part of the module itself — it is a process
document for the people doing the hand-off.

---

## Who this guide is for

Anyone coordinating the upstream submission:

- A `<governance-body>` member who ran the module as a pilot and wants to
  contribute the improvements back.
- A framework maintainer preparing a stable snapshot for upstream.
- A community manager representing the project at Apache Training.

Learners and facilitators using the module as-is do not need this guide — the
`README.md` and `instructor-guide.md` in this directory are the operational
documents.

---

## What we are contributing

The module consists of:

| File | Content |
|---|---|
| `README.md` | Module index and delivery-format overview |
| `lesson-01-what-agents-are.md` | Lesson 1 — What agents are |
| `lesson-02-working-with-agents.md` | Lesson 2 — Working with agents |
| `lesson-03-choosing-models.md` | Lesson 3 — Choosing models |
| `lesson-04-your-first-skill.md` | Lesson 4 — Your first skill |
| `lesson-05-writing-safe-skills.md` | Lesson 5 — Writing safe skills |
| `lesson-06-debugging-a-skill.md` | Lesson 6 — Debugging a skill |
| `lesson-07-writing-portable-skills.md` | Lesson 7 — Writing portable skills |
| `lesson-08-eval-driven-development.md` | Lesson 8 — Eval-driven development |
| `lesson-09-agentic-and-autonomous-work.md` | Lesson 9 — Agentic and autonomous work |
| `lesson-10-english-as-a-programming-language.md` | Lesson 10 — English as a programming language |
| `lesson-11-how-to-contribute.md` | Lesson 11 — How to contribute |
| `lesson-lab-tutorials.md` | Hands-on lab — Build and evaluate a skill |
| `instructor-guide.md` | Facilitator guide |

Every file is Markdown and carries an SPDX `Apache-2.0` licence header.

---

## Prerequisites before submitting

Do not submit upstream before:

1. **At least one pilot run has completed.** The module should have been
   delivered — in any format (self-paced, workshop, LMS-based) — for at least
   one real cohort, and the pilot record below should capture the outcome.
2. **Known gaps are fixed.** Any lesson that generated persistent confusion or
   exercises that consistently fell flat should be revised before the upstream
   submission creates a stable reference.
3. **Placeholders are documented.** The upstream submission must clearly explain
   which tokens are project-specific substitution placeholders (see below).

---

## Licensing

All files in this directory are Apache License 2.0 (SPDX identifier
`Apache-2.0`). Apache Training accepts contributions under this licence;
no relicensing is needed.

Commits that include AI-generated content carry a `Generated-by:` trailer
following [ASF Generative Tooling
Guidance](https://www.apache.org/legal/generative-tooling-guidance.html).
The upstream submission inherits these trailers; Apache Training's
contribution guidelines apply from the first upstream commit onward.

---

## Placeholder convention

The module uses `<PROJECT>` wherever a concrete project name would appear in
an exercise or self-check. This is the framework's project-agnosticism
convention (PRINCIPLE 13): substituting `<PROJECT>` with a real name is a
learner or facilitator step, not a file-editing step.

When submitting upstream, leave `<PROJECT>` as-is — it is the upstream
module's own placeholder convention. Apache Training materials routinely use
similar `<project-name>` tokens for the same purpose; confirm the exact token
form with the Apache Training project before the first commit so the module
matches their convention.

Other placeholders that appear in some exercises:

| Placeholder | Meaning |
|---|---|
| `<PROJECT>` | The adopting project's name |
| `<governance-body>` | The project's governing body (PMC, steering committee, etc.) |
| `<tracker>` | The project's issue tracker |

---

## Submission process

### 1. Open a thread on the Apache Training dev list

Send an introduction email to the Apache Training developers list
(`dev@training.apache.org`) with:

- A one-paragraph description of the module (topic, audience, lesson count,
  approximate total learning time).
- A link to this repository or a rendered preview of the module.
- A note that the module is Apache-2.0 and project-agnostic.
- A request to discuss format alignment before submitting a PR.

### 2. Align on format

Apache Training may have specific requirements for:

- File layout and naming conventions.
- Learning-objective wording style (ABCD objectives, Bloom's taxonomy level).
- Exercise format (structured vs. free-form).
- Self-check format (hidden answers, separate answer key, LMS quiz YAML).
- LMS metadata (SCORM, xAPI statements, estimated credit hours).

Review those requirements against the module's current shape and note any
changes needed. Small formatting changes (heading levels, front-matter fields,
answer-key placement) can be applied in the upstream submission PR. Substantive
changes to lesson content should be made first in this repository, then
back-ported to the submission.

### 3. Prepare the submission branch

In the Apache Training repository (or whichever contribution path they
specify):

1. Create a feature branch (e.g.
   `add-agentic-framework-maintainer-module`).
2. Copy the module files into the appropriate directory as discussed with
   Apache Training.
3. Apply any format-alignment changes agreed in step 2.
4. Update the module README to reflect the Apache Training context
   (remove framework-specific links; add the Apache Training module path;
   update any cross-links that pointed at this repository's source pages).
5. Add or update the `NOTICE` file as Apache Training requires.

### 4. Open a pull request

Open a PR against the Apache Training repository. Include:

- A summary of what the module teaches and why it belongs in Apache Training.
- A reference to the pilot record (see below) showing the module has been run.
- A note on the `Generated-by:` convention used in this module's commits.
- A link back to this framework repository as the canonical upstream for
  ongoing maintenance.

### 5. Coordinate ongoing maintenance

After the first upstream PR merges, agree on a maintenance model:

- **Framework-authoritative.** Changes originate here; the Apache Training
  copy is periodically refreshed. Preferred: keeps lesson quality improvements
  in one place and flowing downstream.
- **Bi-directional.** Apache Training improvements are ported back here.
  Appropriate once a stable community of facilitators forms around the upstream
  copy.

Document the chosen model in the Apache Training PR description so both
communities know where to open issues.

---

## Pilot record

The pilot record captures outcomes from runs of the module before — and after —
upstream submission. It is a lightweight structured log, not a formal
assessment framework. Add one entry per run.

### Entry format

```markdown
## Pilot run — <project name> — <month YYYY>

**Format:** self-paced | instructor-led | two-session | LMS
**Cohort size:** <number of learners>
**Lessons covered:** all | lessons <X>–<Y> | [list exceptions]
**Lab completed:** yes | no | partially

### What worked well

- <one finding per bullet>

### What confused learners

- <one finding per bullet — tie each to the specific lesson or exercise>

### Changes made as a result

- <PR or commit reference, or "pending">

### Facilitator notes

<free text — timing observations, discussion prompts that landed, materials
that needed supplementing>
```

### Where the record lives

Keep the pilot record in a file adjacent to this one:
`docs/education/training/pilot-record.md`. It is an ongoing append-only
log; do not edit past entries.

Include a summary (cohort count, format, key findings) in the upstream
submission PR so Apache Training reviewers can calibrate the module's maturity.

---

## Contact points

| Channel | Purpose |
|---|---|
| `dev@training.apache.org` | Apache Training developers — format questions, PR review |
| Apache Training GitHub | Pull requests and issue tracking |
| This repository's issue tracker | Framework-level improvements to lesson content |

When asking a format question on the Apache Training list, link to the module
README rather than pasting content — it is easier for list members to review
in context.

---

## Licence

Apache License 2.0. Every file in this directory carries an SPDX
`Apache-2.0` header.
