<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Lesson 3 — Choosing models](#lesson-3--choosing-models)
  - [Learning objectives](#learning-objectives)
  - [Prerequisite knowledge](#prerequisite-knowledge)
  - [Before the lesson](#before-the-lesson)
  - [Exercises](#exercises)
    - [Exercise 1 — The three-way tradeoff](#exercise-1--the-three-way-tradeoff)
    - [Exercise 2 — Classify the task](#exercise-2--classify-the-task)
    - [Exercise 3 — The judge-model pattern](#exercise-3--the-judge-model-pattern)
    - [Exercise 4 — Local vs hosted](#exercise-4--local-vs-hosted)
  - [Self-check](#self-check)
  - [Summary](#summary)
  - [Next](#next)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Lesson 3 — Choosing models

**Source page:** [How to use different models](../choosing-models.md)
**Estimated time:** 35 minutes (20 min reading + 15 min exercises and self-check)
**Lesson in sequence:** 3 of 11

---

## Learning objectives

By the end of this lesson you will be able to:

1. **Name** the three things every model trades off and explain why
   maximising all three simultaneously is impossible.
2. **Classify** a maintenance task as low-complexity, mid-complexity, or
   high-complexity and justify the model tier that fits it.
3. **Explain** the judge-model pattern and why the judge does not need to be
   as capable as the model doing the work.
4. **Compare** local and hosted models on at least two dimensions relevant
   to an open-source project.
5. **Describe** the four-step process for choosing between candidate models
   with evals rather than by reputation.

---

## Prerequisite knowledge

**Lesson 2 — Working with agents.** You should be comfortable writing a
four-ingredient request and steering an agent mid-task. If those ideas feel
uncertain, re-read lesson 2 before starting here.

---

## Before the lesson

Read the source page **[How to use different models](../choosing-models.md)**
from start to finish. Pay particular attention to:

- The "There is no single 'best' model" section and its three-way tradeoff.
- The "Match the model to the job" task-complexity ladder.
- The "Local or hosted?" deployment choice.
- The "Bigger context is not automatically better" section.
- The "Let evals decide, not vibes" four-step process.
- The "Check your understanding" block at the bottom.

The exercises below draw directly on those sections. Keep the page open if
you want to check something.

---

## Exercises

Work through these alone or in pairs. The exercise block takes about 10 to 12
minutes. No computers needed: use paper, a whiteboard, or a shared document.

### Exercise 1 — The three-way tradeoff

Below are three model descriptions. For each one, identify which of the
three tradeoff dimensions or deployment factors it has maximised and which it
has compromised.
Then match each model to the task type it fits best.

> **Model A:** Answers in under two seconds, costs less than a cent per
> call, but sometimes misses subtle reasoning steps.

> **Model B:** Takes ten seconds per call, costs ten times more than model A,
> but handles complex multi-step analysis reliably.

> **Model C:** Runs entirely on your own hardware with no network call;
> speed and cost depend on your machine; capability is lower than the
> hosted frontier models.

Task types to assign (one per model):
- Reformatting 500 issue titles into a standard template.
- Triaging an ambiguous bug report that references four interacting components.
- Processing contributor emails on a project with strict data-residency rules.

Write: which model fits which task, and name the tradeoff dimension or
deployment factor that makes it the right fit.

### Exercise 2 — Classify the task

Read the five maintenance tasks below. For each one, classify it as
low-complexity (small/cheap model fine), mid-complexity (mid-tier model), or
high-complexity (capable model worth the cost). Write one sentence justifying
each classification.

1. Extract the issue number from each of 200 pull-request titles.
2. Decide whether a two-paragraph bug report describes a known issue or a
   genuinely new one, given a list of 30 existing issues to compare.
3. Identify issues that should receive the `needs-info` label because they have
   no steps to reproduce.
4. Review a proposed API change across five files and identify whether it
   breaks the public contract documented in `CHANGELOG.md`.
5. Summarise the last seven days of mailing-list activity in three bullet
   points.

### Exercise 3 — The judge-model pattern

A skill drafts a "thank you for your first contribution" comment. The
comment must be warm, name the contributor, mention the specific change,
and not reveal any internal project decisions.

You cannot check this output with an exact string match (every comment is
different). Design a short judge rubric: four criteria the judge model
should check, each a yes/no question. Then answer: does the judge need to
be the same model as the one that drafted the comment? Why or why not?

### Exercise 4 — Local vs hosted

Your `<PROJECT>` processes incoming security-report emails from external
reporters. The emails may contain vulnerability details and reporter contact
information.

1. List two reasons a local model would be preferable here.
2. List one reason you might still consider a hosted model even in this
   scenario, and name the safeguard the source page says is always required
   regardless of which you pick.

---

## Self-check

Answer each question in a sentence or two before moving to lesson 4. If you
cannot answer one, re-read the matching section of the source page.

**Q1.** Name the three things every model trades off.

<details>
<summary>Answer</summary>

Capability (how well it handles hard, multi-step reasoning), speed/latency
(how long you wait for an answer), and cost (what each run costs in money or
local compute). You cannot maximise all three: a more capable model tends to
be slower and more expensive; a fast, cheap model may fail on subtle tasks.

</details>

---

**Q2.** When is choosing a small, cheap model the *right* decision, not a
compromise?

<details>
<summary>Answer</summary>

When the task is simple, high-volume, and well-defined — for example,
reformatting, extracting a field, or first-pass labelling of obvious cases.
Paying for a top-tier model on work a smaller model handles correctly is
waste, not quality.

</details>

---

**Q3.** What is the judge-model pattern and why does the judge not need to be
as capable as the working model?

<details>
<summary>Answer</summary>

When a skill's output is prose, an exact string match cannot tell a good
answer from a bad one (two correct answers can be worded differently). A
judge model reads the output against a short scoring rubric and returns pass
or fail. The judge only has to tell a good answer from a bad one against a
clear rubric, so a smaller, cheaper model is usually sufficient — it does not
have to produce the output, only grade it.

</details>

---

**Q4.** A colleague argues: "Always use the model with the largest context
window — more is better." What is wrong with this reasoning?

<details>
<summary>Answer</summary>

A large window lets the agent *hold* more text, but stuffing it with
irrelevant content makes the important parts harder to find and every call
slower and more expensive. A focused, well-chosen context on a modest model
often outperforms a cluttered one on a large model. Give the agent what the
task needs, not everything available.

</details>

---

**Q5.** Describe the four-step process the source page recommends for
choosing between two candidate models.

<details>
<summary>Answer</summary>

1. Write the eval suite for the skill first (it is required anyway).
2. Run the suite against each candidate model using `--cli`.
3. Compare which ones pass, how fast, and at what cost.
4. Pick the cheapest, fastest model that clears the bar, and re-check when a
   new model appears or an old one is retired.

This turns "which model?" from an argument into a measurement.

</details>

---

## Summary

Every model trades capability, speed, and cost against each other — you
cannot max all three. Match the model to the job: simple high-volume work
fits a small cheap model; hard judgement-heavy work earns the cost of a
capable one; most real tasks land in between. When a skill's output is prose,
a cheap judge model grades the evals rather than an exact-match check. Local
models keep data on your own hardware; hosted models are usually more capable
but your input leaves your machine — either way, Magpie's privacy posture
applies before anything reaches the model. "Bigger context" is not always
better: a focused context on a modest model often wins. Choose models with
evals, not vibes: write, run, compare, pick, and re-check.

---

## Next

**[Lesson 4 — Your first skill](../your-first-skill.md)** (lesson 4 of this
module is not yet packaged; follow the source page directly until it lands).

---

## Licence

Apache License 2.0 (PRINCIPLE 17). Pages written with help from AI carry a
`Generated-by:` note in their commit message following ASF Generative Tooling
Guidance.
