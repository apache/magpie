<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Training module: Building and running AI agents for open-source projects](#apache-training-module-building-and-running-ai-agents-for-open-source-projects)
  - [Who this is for](#who-this-is-for)
  - [Relationship to the source pages](#relationship-to-the-source-pages)
  - [Module map](#module-map)
  - [Delivery formats](#delivery-formats)
  - [Prerequisites](#prerequisites)
  - [Placeholders](#placeholders)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Apache Training module: Building and running AI agents for open-source projects

This directory packages the [maintainer-education stream](../README.md) as a
reusable, LMS-neutral **Apache Training module**. Any project — ASF or not —
can use it to *teach* the material in a structured course, not just circulate
the pages as reading. It is shaped for upstream contribution to
[Apache Training](https://training.apache.org/) so the module can live there
once it is stable.

## Who this is for

Instructors and facilitators running the education stream as a course:
workshops, on-boarding sessions, reading groups, self-paced curricula, or any
environment where learners need per-lesson structure (objectives, exercises,
assessment) in addition to the reference pages.

Learners using the module self-paced do not need an LMS. Every lesson is a
plain Markdown file: read it, work through the exercises, and answer the
self-check questions before moving on.

## Relationship to the source pages

Each lesson in this module is a **wrapper** around one or more
[progression pages](../README.md). The source pages are the canonical
reference; the lessons add LMS-friendly structure on top:

- **Learning objectives** — what a learner will be able to *do* after the
  lesson, written as observable, assessable outcomes.
- **Exercises** — hands-on activities a learner can complete without access
  to a live system (paper/whiteboard activities use the page's own examples).
- **Self-check** — short questions (and answers) the learner uses to gate
  themselves before moving to the next lesson.

Nothing in this directory duplicates the reference material; it only frames it.

## Module map

| Lesson | Source page | Learning time |
|---|---|---|
| [Lesson 1 — What agents are](lesson-01-what-agents-are.md) | [What agents are](../what-agents-are.md) | ~30 min |
| [Lesson 2 — Working with agents](lesson-02-working-with-agents.md) | [Working with agents](../working-with-agents.md) | ~30 min |
| [Lesson 3 — Choosing models](lesson-03-choosing-models.md) | [Choosing models](../choosing-models.md) | ~35 min |
| [Lesson 4 — Your first skill](lesson-04-your-first-skill.md) | [Your first skill](../your-first-skill.md) | ~60 min |
| [Lesson 5 — Writing safe skills](lesson-05-writing-safe-skills.md) | [Writing safe skills](../writing-safe-skills.md) | ~45 min |
| [Lesson 6 — Debugging a skill](lesson-06-debugging-a-skill.md) | [Debugging a skill](../debugging-skills.md) | ~50 min |
| [Lesson 7 — Writing portable skills](lesson-07-writing-portable-skills.md) | [Writing portable skills](../portable-skills.md) | ~35 min |
| [Lesson 8 — Eval-driven development](lesson-08-eval-driven-development.md) | [Eval-driven development](../eval-driven-development.md) | ~60 min |
| [Lesson 9 — Agentic and autonomous work](lesson-09-agentic-and-autonomous-work.md) | [Agentic and autonomous work](../agentic-work.md) | ~45 min |
| [Lesson 10 — English as a programming language](lesson-10-english-as-a-programming-language.md) | [English as a programming language](../english-as-code.md) | ~30 min |
| [Lesson 11 — How to contribute](lesson-11-how-to-contribute.md) | [How to contribute](../contributing.md) | ~30 min |
| [Hands-on lab](lesson-lab-tutorials.md) | [Tutorial: build and evaluate a skill](../tutorials.md) | ~90 min |

## Delivery formats

**Self-paced.** Learners read the source page, then work through the lesson
wrapper (objectives, exercises, self-check) on their own. No instructor or LMS
needed.

**Instructor-led.** An instructor presents the key ideas from the source page,
assigns the exercises to pairs or small groups, and uses the self-check
questions for a brief group debrief before moving on. The facilitator guide
([`instructor-guide.md`](instructor-guide.md)) covers room setup, timing, and group discussion
prompts.

**LMS upload.** Each lesson is a Markdown file that can be converted to SCORM,
xAPI, or any other format a specific LMS supports. The module does not assume
any particular LMS. Learning time estimates above are rough guides for LMS
credit-hour tagging.

## Prerequisites

No prior AI experience. Learners should be comfortable reading and writing
plain text, and familiar with the idea of a software project that uses version
control. Specific technical prerequisites are stated in each lesson.

## Placeholders

Exercises use `<PROJECT>` wherever a real project name would appear.
Substitute your own project name when working through the activities.

## Licence

Apache License 2.0 (PRINCIPLE 17). Contributions carry a `Generated-by:` note
in their commit message following ASF Generative Tooling Guidance.
