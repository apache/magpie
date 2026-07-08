<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [ai-tutors](#ai-tutors)
  - [How to use one](#how-to-use-one)
  - [Notes](#notes)
  - [Files](#files)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# ai-tutors

Interactive AI tutor prompts, one per lesson in the training module. Each file
turns a capable chat model into a tutor for a single lesson: it teaches the
material one idea at a time, runs the exercises and self-check, and grades the
learner's answers against the lesson's answer keys.

These are companions to the readable lessons, not replacements for them. The
canonical, no-AI-required lessons live under `docs/education/`. A tutor prompt
only does anything when loaded into a model; the lesson stands on its own.

## How to use one

Each file has two parts split by a `---` line:

- Everything **above** the line is notes to you (what it is, how to load it). It
  is not sent to the model.
- Everything **below** the line is the tutor. Send it as the system prompt.

So the one rule is: **paste everything below the `---` into a model as the system
prompt, then chat normally.** The learner answers the tutor's opening questions
and it takes over from there.

Where "system prompt" goes, by tool:

- **claude.ai / ChatGPT:** paste the below-the-line content as your
  first message in a new chat. Not a true system prompt, but it behaves the same
  for one session.
- **claude.ai Projects:** paste it into the Project's custom instructions. Every
  chat in that Project is then the tutor, and learners never see the prompt.
- **Open WebUI:** Workspace > Models > new model, pick a base, paste it into the
  System Prompt field, save. It appears in the model dropdown with the prompt
  already loaded and out of the learner's reach.
- **API:** pass it as the `system` parameter; the learner's turns are `messages`.

## Notes

- **Model choice matters.** These prompts ask the model to hold a multi-step
  teaching flow, withhold answers until the learner attempts them, and grade.
  Hosted models (Claude, GPT) follow that reliably. Small local models are fine
  for testing but less dependable for real students.
- **Self-contained.** Each prompt embeds the full source text of its lesson, so
  it needs no web access and refers to no external paths.
- **Refreshing.** Because the lesson text is embedded, updating a lesson upstream
  means updating the matching tutor prompt here too.

Refresh the embedded teaching content with:

```bash
python3 ai-tutors/inject-knowledge-base.py
```

The script scans `ai-tutors/lesson-*.md`, finds the same-named lesson under
`docs/education/training/`, follows that lesson's `Source page` link, and
rewrites the generated part of the tutor's `KNOWLEDGE BASE`. Use `--check` in
CI to fail when a tutor prompt is stale.

## Files

| Tutor prompt                                     | Lesson                                         |
| ------------------------------------------------ | ---------------------------------------------- |
| `lesson-01-what-agents-are.md`                   | Lesson 1 - What agents are                     |
| `lesson-02-working-with-agents.md`               | Lesson 2 - Working with agents                 |
| `lesson-03-choosing-models.md`                   | Lesson 3 - Choosing models                     |
| `lesson-04-your-first-skill.md`                  | Lesson 4 - Your first skill                    |
| `lesson-05-writing-safe-skills.md`               | Lesson 5 - Writing safe skills                 |
| `lesson-06-debugging-a-skill.md`                 | Lesson 6 - Debugging a skill                   |
| `lesson-07-writing-portable-skills.md`           | Lesson 7 - Writing portable skills             |
| `lesson-08-eval-driven-development.md`           | Lesson 8 - Eval-driven development             |
| `lesson-09-agentic-and-autonomous-work.md`       | Lesson 9 - Agentic and autonomous work         |
| `lesson-10-english-as-a-programming-language.md` | Lesson 10 - English as a programming language  |
| `lesson-11-how-to-contribute.md`                 | Lesson 11 - How to contribute                  |
