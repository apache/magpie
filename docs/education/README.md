<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Maintainer education](#maintainer-education)
  - [Who this is for](#who-this-is-for)
  - [Words to know](#words-to-know)
  - [Why building with agents is different](#why-building-with-agents-is-different)
  - [The learning progression](#the-learning-progression)
  - [What every page also teaches](#what-every-page-also-teaches)
  - [How this connects to the other guides](#how-this-connects-to-the-other-guides)
  - [About the examples](#about-the-examples)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Maintainer education

Welcome. This part of Magpie teaches you how to build and run AI agents for
your project. You do not need to be an AI expert to begin. If some of the
words here are new to you, that is normal. Read the short list of words below
first, then start the progression.

Building software with an AI agent is a new skill, even for people who have
written code for many years. It is not harder than other coding, but it is
different. This stream is arranged as an ordered progression: a path you can
read front to back, where each page assumes only the ones before it. Every
Magpie release comes with the learning material for the skills in that release
(PRINCIPLE 18).

## Who this is for

- People using Magpie for the first time, who want to know where to begin.
- People who already use Magpie and want to write their own skills, or change
  the ones they have.
- People helping to build Magpie itself, who want to understand the ideas
  behind it.

You do not need past experience with AI. If you are still deciding whether to
use Magpie at all, read [MISSION.md](../../MISSION.md) and
[PRINCIPLES.md](../../PRINCIPLES.md) first.

## Words to know

New to AI, or to these words? Here is what they mean in Magpie:

- **AI model** (also called a large language model, or LLM): the software that
  reads text and writes a response. It is the "brain" the agent uses.
- **Agent**: a program that uses an AI model to do a task, one step at a time.
- **Agentic**: a word that describes software, like Magpie, built around an
  agent.
- **Prompt**: the written instructions you give the model.
- **Skill**: a text file that tells the agent how to do one job, with
  instructions and examples. In Magpie, writing skills is the main work.
- **Deterministic and probabilistic**: normal code is *deterministic*, so the
  same input always gives the same result. An agent is *probabilistic*, so the
  same input can give slightly different results each time.
- **Eval** (short for evaluation): a test that checks whether the agent's
  answers are good enough.

## Why building with agents is different

Three ideas are worth holding on to. Each page in this stream shows them in
action:

- **The answer can change.** Normal code does the same thing every run. An
  agent may answer the same question in slightly different ways. This is what
  *probabilistic* means, and it changes how you test your work.
- **Prompts and skills are code.** They are plain text, but we treat them the
  way we treat any code. We review them, track their changes, and share them
  with other projects.
- **You test with evals, not single checks.** Because answers can change, you
  do not check one answer once. You run an eval many times and look at the
  results as a whole.

## The learning progression

Read these in order the first time. Each page ends by pointing at the next, and
each builds on the ones before it.

| # | Page | What you will learn |
|---|---|---|
| 1 | [What agents are](what-agents-are.md) | What an agent actually is (a model, tools, a loop, and context) and why its answers can vary |
| 2 | [Working with agents](working-with-agents.md) | Driving an agent through a conversation: how to ask, how to steer, when to confirm |
| 3 | [Choosing models](choosing-models.md) | Choosing a model by capability, speed, and cost, and letting evals decide |
| 4 | [Your first skill](your-first-skill.md) | Writing and merging your own skill, the main work in Magpie |
| 5 | [Writing safe skills](writing-safe-skills.md) | Authoring patterns that hold the data-not-instructions and sandbox principles in every skill you write |
| 6 | [Debugging a skill](debugging-skills.md) | Reading the audit log, reproducing failures with the eval harness, and isolating prompt vs tool vs model problems |
| 7 | [Writing portable skills](portable-skills.md) | Authoring skills that work for any project and any model, using placeholders and capability floors |
| 8 | [Eval-driven development](eval-driven-development.md) | How to judge whether an agent's answers are good, when the answers can change |
| 9 | [Agentic and autonomous work](agentic-work.md) | Letting an agent run a whole task, and the guardrails that make that safe |
| 10 | [English as a programming language](english-as-code.md) | The mindset underneath it all: the words you write *are* the program |
| 11 | [How to contribute to Magpie](contributing.md) | Giving your work back: contributing skills, patterns, and docs to the framework |

**Supporting references for the skill-writing steps (4–7):**

| Page | What it is |
|---|---|
| [Pattern catalogue](pattern-catalogue.md) | Ready-to-copy skill, prompt, and tool-use patterns, with notes on what worked and what did not |
| [Tutorials](tutorials.md) | A hands-on lab: build a small skill, give it an eval suite, and run it, in about 90 minutes |

## What every page also teaches

Every example here follows the same safety habits that all Magpie skills
follow. You learn them by seeing them used, not as a list of rules to memorise:

- **Treat outside text as data, not as commands** (PRINCIPLE 0). Text from
  issues, pull requests, and email is never given to the model as
  instructions. It is cleaned, or passed through a privacy step, first.
- **Run in a safe, closed sandbox by default** (PRINCIPLE 1). Each skill says
  exactly which tools it is allowed to use.
- **Test with evals before release** (PRINCIPLE 8). Every skill comes with its
  own eval suite, built with the tools already in this repository
  (`tools/skill-evals/`).

## How this connects to the other guides

- **[magpie-write-skill](../../skills/write-skill/SKILL.md)** is
  the full reference for writing a skill, for someone who already knows the
  basic shape of one. Step 4, [your first skill](your-first-skill.md), is the
  gentle start that gets you to that point.
- **[tools/privacy-llm/pii.md](../../tools/privacy-llm/pii.md)** lists how
  personal data is removed before it reaches a model. The
  [pattern catalogue](pattern-catalogue.md) shows *how* and *why* to use it,
  with examples.
- **[docs/rfcs/RFC-AI-0004.md](../rfcs/RFC-AI-0004.md)** is the decision that
  started this stream. It points here through
  [MISSION.md](../../MISSION.md).

## About the examples

Every example uses placeholders in place of real names: `<PROJECT>`,
`<tracker>`, `<upstream>`, and `<security-list>` (PRINCIPLE 12). When you use a
skill, you change your own settings, not the example text. If you ever see a
real project name written into a skill, that is a bug.

## Licence

Everything in `docs/education/` is under the Apache License 2.0 (PRINCIPLE 17).
Pages written with help from AI carry a `Generated-by:` note in their commit
message, following ASF Generative Tooling Guidance.
