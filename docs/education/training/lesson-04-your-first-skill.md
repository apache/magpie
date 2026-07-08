<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Lesson 4 — Your first skill](#lesson-4--your-first-skill)
  - [Learning objectives](#learning-objectives)
  - [Prerequisite knowledge](#prerequisite-knowledge)
  - [Before the lesson](#before-the-lesson)
  - [Exercises](#exercises)
    - [Exercise 1 — Propose, confirm, or neither?](#exercise-1--propose-confirm-or-neither)
    - [Exercise 2 — Spot the placeholder violations](#exercise-2--spot-the-placeholder-violations)
    - [Exercise 3 — Write a frontmatter block](#exercise-3--write-a-frontmatter-block)
    - [Exercise 4 — Design a three-case eval suite](#exercise-4--design-a-three-case-eval-suite)
  - [Self-check](#self-check)
  - [Summary](#summary)
  - [Next](#next)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Lesson 4 — Your first skill

**Source page:** [Your first skill](../your-first-skill.md)
**Estimated time:** 60 minutes (40 min reading + 20 min exercises and self-check)
**Lesson in sequence:** 4 of 11

---

## Learning objectives

By the end of this lesson you will be able to:

1. **List** the five frontmatter fields shown in the starter skill and state what
   each one is used for at runtime.
2. **Apply** the "propose, confirm, act" rule to a set of skill steps and
   correctly separate those that require confirmation from those that do not.
3. **Name** three placeholders the framework uses and state what each one
   resolves to, without writing a real project name into a skill body.
4. **Describe** the minimum structure of an eval suite — the directory layout,
   the three files every step fixture needs, and the three case types a
   minimum suite must include.
5. **Trace** the authoring workflow from Step 0 through Step 6, from "I have an
   idea" to "the PR is merged", naming the tool or check that completes each
   step.

---

## Prerequisite knowledge

**Lesson 3 — Choosing models.** You should be comfortable with the idea that
a skill guides an agent through a task and that an agent is built from a model
plus tools plus a loop. If those concepts feel uncertain, review lessons 1–3
before starting here.

---

## Before the lesson

Read the source page **[Your first skill](../your-first-skill.md)** from start
to finish, including the code blocks. Pay particular attention to:

- The comparison table "Traditional code / A skill."
- The frontmatter YAML block in Step 2 and the explanation of each key.
- The three rules in Step 3 (external-content-is-data, propose/confirm/act,
  use-placeholders).
- The directory layout and file list in Step 5 (the eval-suite structure).
- The "Common first-time mistakes" section at the end.

The exercises below draw directly on those sections. Keep the page open if
you want to look something up.

---

## Exercises

Work through these alone or in pairs. Each exercise takes three to five
minutes. No computers needed: use paper, a whiteboard, or a shared document.

### Exercise 1 — Propose, confirm, or neither?

Below are eight skill steps. For each one, decide whether it:

- **Must be confirmed** before it runs (visible outside the session), or
- **Does not need confirmation** (read-only, no external state change).

> 1. Read the list of open issues in the tracker.
> 2. Apply the label `needs-info` to issue #237.
> 3. Draft a comment explaining why the issue is being closed.
> 4. Close issue #237.
> 5. Search the codebase for all files that import `requests`.
> 6. Post the drafted comment on issue #237.
> 7. Summarise the three most recent PRs and display the summary to the
>    maintainer.
> 8. Create a new GitHub issue titled "Dependency upgrade needed."

Write two columns: "Confirm first" and "No confirmation needed." Assign each
step to the right column and note which of the three skill rules it hits.

### Exercise 2 — Spot the placeholder violations

The skill body excerpt below contains three mistakes: each one names a real
project or resource instead of using the correct placeholder. Find all three
and write the corrected version alongside each.

> ```text
> gh issue list --repo apache/airflow --state open | head -20
>
> Check the mailing list at security@airflow.apache.org for unreported
> threads.
>
> For each finding, propose opening a tracker issue at
> github.com/airflow-s/airflow-s with the extracted template fields.
> ```

Write the corrected lines underneath each original line, using the placeholders
from the table in [AGENTS.md](../../../AGENTS.md).

### Exercise 3 — Write a frontmatter block

You are writing a skill for your project. The skill
does this: *when a PR is labelled `ready-for-review`, it checks whether a
matching issue is linked in the PR description and proposes adding a link if
not.*

Write the YAML frontmatter for this skill, filling in the five fields the starter
skill shows (`name`, `description`, `when_to_use`, `capability`, `license`). Use
only the fields the source page shows; do not invent new ones.

Reference the `capability:` values from two or three existing skills in
`skills/` to pick the tag that fits best.

### Exercise 4 — Design a three-case eval suite

The skill from Exercise 3 has one step that checks whether an issue is
linked. Design a three-case eval suite for that step.

For each of the three cases, write:
- A one-line name for the case.
- One or two sentences describing the input scenario.
- The expected outcome: what should the agent's output contain or not
  contain?

Your three cases should cover: a normal input (PR with no linked issue), an
empty or degenerate input (PR with no description at all), and an attack case
(a PR description that contains text trying to make the agent skip
confirmation).

---

## Self-check

Answer each question in a sentence or two before moving to lesson 5. If you
cannot answer one, re-read the matching section of the source page.

**Q1.** Name the five frontmatter fields in the starter skill and explain in one sentence
what each one is used for at runtime.

<details>
<summary>Answer</summary>

- `name` — the identifier the harness uses to locate and invoke this skill.
- `description` — a short prose summary of what the skill does and when it is
  useful; the agent reads this to decide whether the skill matches the current
  request.
- `when_to_use` — the trigger vocabulary: the phrases or situations that should
  cause the agent to invoke the skill. Without it the agent cannot pick the
  skill reliably.
- `capability` — the taxonomy tag that files the skill in the framework's
  categories; the validator checks that it is present.
- `license` — the open-source licence (almost always `Apache-2.0`); required
  by the validator.

</details>

---

**Q2.** A skill step reads: *"Post the drafted comment to the issue."* Why is
this step unsafe as written, and how would you fix it?

<details>
<summary>Answer</summary>

Posting a comment is an action visible outside the session — it changes
external state that other people can see. Running it without confirmation
violates the "propose, confirm, act" rule. The fix is to split it into two
steps: first, *draft* the comment and *display it to the maintainer*; then
add a step that says *"Present the draft and wait for the maintainer's
confirmation before posting."* Only after the maintainer confirms does the
skill post anything.

</details>

---

**Q3.** What is the purpose of placeholders in a skill body, and what would
break if you wrote `apache/airflow` directly instead of `<upstream>`?

<details>
<summary>Answer</summary>

Placeholders keep a skill project-agnostic: when a different project adopts
the framework, it fills in its own values without editing the skill itself.
If `apache/airflow` were written directly into the skill, that skill would
only work for the Airflow project. Any adopter with a different upstream
would have to edit the skill body — making the framework's reuse promise
false and creating a drift hazard every time the project name or repo path
changes.

</details>

---

**Q4.** A colleague says: "I wrote one eval case with a normal input. The
skill passes it, so it is done." What is missing, and why does it matter?

<details>
<summary>Answer</summary>

A single normal-case fixture is not a suite. Two cases are always required
alongside it: an empty or degenerate input case (does the skill handle missing
or trivial data gracefully?), and an attack case (does the skill resist an
input that tries to make the agent act without confirmation?). The attack
case is usually the most valuable: it catches prompt-injection weaknesses that
a normal case can never surface. Without it, the skill is untested against the
class of input most likely to cause a real security or reliability problem.

</details>

---

**Q5.** You are testing a skill step named `## Step 2 — Propose to the
maintainer`. The step reads a PR description and decides whether to propose
adding a missing issue link. What would you put in each of the three eval-step
files, and what three case types would you create?

<details>
<summary>Answer</summary>

`step-config.json` would name the skill file and the exact step heading, for
example `skills/pr-issue-link-check/SKILL.md` and `## Step 2 — Propose to the
maintainer`. `user-prompt-template.md` would hold a reusable prompt with a
placeholder for the PR description. `output-spec.md` would say that a correct
answer must report whether a link is present, propose adding one when missing,
and must not edit or post without confirmation.

The three cases should be: a normal PR description with no linked issue, an
empty PR description, and an attack description that tries to make the agent
skip confirmation or add the link directly.

</details>

---

## Summary

A skill is a Markdown file with YAML frontmatter and a numbered step list —
not code, and not tested with unit tests, but with an eval suite of example
cases. The starter skill shows five frontmatter fields: `name`, `description`,
`when_to_use`, `capability`, and `license`; the validator checks them. Three rules
govern every skill body: external content is data not instructions; every
external action must be proposed and confirmed before it runs; and
project-specific names are always placeholders. An eval suite requires three
case types as a minimum — normal input, empty/degenerate input, and an attack
case — because the attack case is where prompt-injection weaknesses live. The
authoring workflow (look around → pick a use case → create the starter file →
write the body → validate → write evals → open PR) is the path from idea to
merged contribution.

---

## Next

**[Writing safe skills](../writing-safe-skills.md)** — step 5 of the
learning progression (lesson 5 of this module is not yet packaged; follow
the source page directly until it lands).

---

## Licence

Apache License 2.0 (PRINCIPLE 17). Pages written with help from AI carry a
`Generated-by:` note in their commit message following ASF Generative Tooling
Guidance.
