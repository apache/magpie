<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [How to use different models](#how-to-use-different-models)
  - [Words used on this page](#words-used-on-this-page)
  - [There is no single "best" model](#there-is-no-single-best-model)
  - [Match the model to the job](#match-the-model-to-the-job)
  - [The judge-model pattern](#the-judge-model-pattern)
  - [Local or hosted?](#local-or-hosted)
  - [Bigger context is not automatically better](#bigger-context-is-not-automatically-better)
  - [Let evals decide, not vibes](#let-evals-decide-not-vibes)
  - [Check your understanding](#check-your-understanding)
  - [How this connects to the other guides](#how-this-connects-to-the-other-guides)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# How to use different models

The same agent, the same skill, and the same prompt can run on top of different
underlying **models**, and the model you pick changes the result, the speed,
and the cost. This page is about making that choice on purpose instead of by
accident.

Magpie is deliberately **model-neutral**. Its skills and its eval harness talk to
a model through a command you supply (`--cli "<agent-command>"`), so the same
skill runs against a hosted model, a local one, or whatever your project has
settled on. This page teaches the *dimensions* of the choice, not a ranking of
brands, because the brands change faster than this page can.

## Words used on this page

New to some of these words? Here is what they mean here. The
[landing page](README.md) has a fuller list.

- **Model**: the language model behind the agent, the "brain" that reads and
  writes text. Different models have different strengths, speeds, and prices.
- **Capability**: how well a model handles hard, multi-step reasoning. More
  capable models cope with harder tasks but usually cost more and run slower.
- **Context window**: how much text a model can take in at once. A bigger window
  holds more files and a longer conversation before older detail must be dropped.
- **Latency**: how long you wait for an answer.
- **Token**: the unit models read and bill in, roughly a word-piece. Cost and
  context limits are both measured in tokens.
- **Local vs hosted**: a *local* model runs on your own machine or servers; a
  *hosted* model runs on a provider's servers and you call it over the network.

---

## There is no single "best" model

Every model trades three things against each other:

- **Capability**: can it actually do the task well?
- **Speed** (latency): how long do you wait?
- **Cost**: what does each run cost, in money or in local compute?

You cannot max out all three. A more capable model tends to be slower and dearer;
a fast, cheap model may fumble a subtle task. The right choice is the cheapest,
fastest model that still does the job well enough, and "well enough" is something
you measure with evals, not something you guess.

## Match the model to the job

A useful habit is to sort your tasks by how much reasoning they really need.

- **Simple, high-volume, well-defined work**, such as reformatting, extracting a
  field, or a first-pass label on an obvious case. A smaller, faster, cheaper
  model is often plenty. Paying for a top-tier model here is waste.
- **Hard, judgement-heavy, multi-step work**, such as untangling an ambiguous bug
  report, reasoning across several files, or weighing a tricky trade-off. This is
  where a more capable model earns its cost, because a wrong cheap answer costs
  you more than the price difference.
- **In between**, which is most real work. Start with a mid-tier model and let
  your evals tell you whether you need to move up.

You do not have to use one model for everything. A common pattern is a capable
model for the hard step and a cheap one for the bulk mechanical steps around it.

## The judge-model pattern

There is a second, quieter place models show up in Magpie: **grading evals**.
When a skill's output is prose, such as a drafted comment or a rationale, you
cannot check it with an exact string match, because two correct answers can be
worded differently. Instead a cheap **judge model** reads the output against a
short scoring guide and returns pass or fail.

The judge does not need to be as capable as the model doing the work; it only has
to tell a good answer from a bad one against a clear rubric. So it is usually a
smaller, cheaper model. You wire it up with `--grader-cli` in the eval harness.
The [eval-driven-development](eval-driven-development.md) page shows this in
detail. It is worth knowing here only so that "which model?" includes "which
model *grades*?", not just "which model *works*?".

## Local or hosted?

Where the model runs is a real decision, not just a detail:

- **Hosted models** are usually the most capable and need no local hardware, but
  your input text leaves your machine and travels to a provider. That has cost,
  privacy, and sometimes policy implications for an open-source project.
- **Local models** keep everything on your own hardware, which is good for
  privacy and for offline or air-gapped work, but they need compute you provide
  and are often less capable at the hard end.

Magpie's design makes this switchable rather than baked in. Because skills and
evals call a model through a command, moving from a hosted CLI to a local one
(for example `ollama run …`) is a change of that command, not a rewrite of your
skills. And whichever you pick, the privacy posture still holds: text that may
carry personal data is cleaned *before* it reaches any model, local or hosted
(PRINCIPLE 1). See the
[privacy routing pattern](pattern-catalogue.md#pattern-5--privacy-routing-clean-the-text-before-the-model-sees-it).

## Bigger context is not automatically better

It is tempting to reach for the model with the largest context window and pour
everything in. Resist it. A large window lets the agent *hold* more, but stuffing
it with irrelevant text makes the important parts harder to find and every call
slower and dearer. A focused, well-chosen context on a modest model often beats a
cluttered one on a large model. Give the agent what the task needs, not
everything you have.

## Let evals decide, not vibes

The reason this page refuses to name a "best" model is that the honest answer is
*measure it*. Because model behaviour is probabilistic and models change often,
the reliable way to choose is:

1. Write the eval suite for your skill first (it is required anyway, per
   PRINCIPLE 8).
2. Run it against two or three candidate models with `--cli`.
3. Compare: which ones pass, how fast, at what cost.
4. Pick the cheapest, fastest model that clears your bar, and re-check when a
   new model appears or an old one is retired.

This turns "which model?" from an argument into a measurement. When someone
upgrades the model behind a skill, the same eval suite tells you whether the
change helped or quietly broke a case.

## Check your understanding

- What three things does every model trade off, and why can't you max all three?
- When is a small, cheap model the *right* choice, not a compromise?
- Why does Magpie choose models with evals rather than by reputation?

## How this connects to the other guides

- **[How to work with agents](working-with-agents.md)** is the conversation this
  model sits underneath; a less capable model simply needs more steering.
- **[How to write your first skill](your-first-skill.md)** comes next. Once you
  can write a skill, the model choice attaches to a concrete piece of work.
- **[Eval-driven development](eval-driven-development.md)** is how you actually
  compare models, including the judge model that grades prose output.
- **[PRINCIPLES.md](../../PRINCIPLES.md)**: PRINCIPLE 1 (privacy and sandbox by
  default) governs what any model, local or hosted, is allowed to see.

## Licence

Everything in `docs/education/` is under the Apache License 2.0 (PRINCIPLE 17).
Pages written with help from AI carry a `Generated-by:` note in their commit
message, following ASF Generative Tooling Guidance.
