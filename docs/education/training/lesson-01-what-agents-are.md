<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Lesson 1 — What agents are](#lesson-1--what-agents-are)
  - [Learning objectives](#learning-objectives)
  - [Prerequisite knowledge](#prerequisite-knowledge)
  - [Before the lesson](#before-the-lesson)
  - [Exercises](#exercises)
    - [Exercise 1 — Draw the agent loop](#exercise-1--draw-the-agent-loop)
    - [Exercise 2 — Spot the context](#exercise-2--spot-the-context)
    - [Exercise 3 — Deterministic vs probabilistic](#exercise-3--deterministic-vs-probabilistic)
    - [Exercise 4 — What the model cannot do alone](#exercise-4--what-the-model-cannot-do-alone)
  - [Self-check](#self-check)
  - [Summary](#summary)
  - [Next](#next)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Lesson 1 — What agents are

**Source page:** [What agents are](../what-agents-are.md)
**Estimated time:** 30 minutes (15 min reading + 15 min exercises and self-check)
**Lesson in sequence:** 1 of 11

---

## Learning objectives

By the end of this lesson you will be able to:

1. **Define** an AI agent in one sentence using its four components: model,
   tools, loop, and context.
2. **Explain** the difference between deterministic and probabilistic behaviour
   and give one concrete consequence for how you test an agent.
3. **Identify** at least two things a bare language model *cannot* do on its own
   that an agent *can*.
4. **Describe** what "context" means in an agent and why it is finite.
5. **Explain** in your own words why an agent's answer can vary between two
   identical requests and why that is not automatically a defect.

---

## Prerequisite knowledge

None. This is the first lesson in the module. You need only be comfortable
reading English and have a rough idea that "AI" refers to software that
generates text.

---

## Before the lesson

Read the source page **[What agents are](../what-agents-are.md)** from start to
finish. Pay particular attention to:

- The "one-sentence version" at the top.
- The comparison table "In normal code / With an agent."
- The "Check your understanding" block at the bottom.

The exercises below build directly on that page. You do not need to re-read it
during the exercises, but keep it open if you want to look something up.

---

## Exercises

Work through these alone or in pairs. Plan on 10 to 12 minutes for the
exercises and another few minutes for the self-check. There are no computers
needed: use paper, a whiteboard, or a shared document.

### Exercise 1 — Draw the agent loop

On paper or a whiteboard, draw the loop an agent runs. Use boxes and arrows.
Your diagram must include at minimum:

- The user's request arriving.
- The model reading the current context.
- The model choosing an action (either "use a tool" or "I am done").
- One branch where a tool runs and its result is added back to context.
- One branch where the loop ends and the model answers.

Compare your diagram with the text description in the source page (the
"you ask for something → model looks at …" block). What did you miss or
add? The source diagram shows the tool-use path; your diagram should also show
the branch where the model decides it is done and answers.

### Exercise 2 — Spot the context

Read the following short scenario, then list everything that is part of the
agent's context at the moment described.

> A maintainer asks an agent: "Does the new PR add a dependency that we have
> already flagged as risky?" The agent reads the PR body, reads the project's
> known-risky-dependency list, finds a match, and drafts a comment. At the
> moment it drafts the comment, what is in context?

Write your list. Include at least four items. Then ask: what is *not* in
context that a human reviewer might also check? Does that matter?

### Exercise 3 — Deterministic vs probabilistic

A colleague says: "I ran the same PR through the agent twice and got two
slightly different comments. Something must be broken."

Write two to three sentences explaining to them why this is expected, what the
correct mental model is, and what they should do instead of running it once and
checking the exact output.

### Exercise 4 — What the model cannot do alone

You are describing AI agents to a new `<PROJECT>` contributor. They ask: "Why
do we need all this machinery? Can't we just ask the AI model directly?"

If you are reading this outside a project-specific copy, replace `<PROJECT>`
with "your project."

List two things the agent can do that a bare language model called once cannot.
Use the ideas from the source page. Write one sentence per item.

---

## Self-check

Answer each question in a sentence or two before moving to lesson 2. If you
cannot answer one, re-read the matching section of the source page.

**Q1.** What are the four components of an agent? (List them.)

<details>
<summary>Answer</summary>

Model, tools, loop, context. The model reads and writes text. Tools are actions
in the real world (read a file, open a saved comment draft, open an issue
draft). The loop runs the model repeatedly, feeding tool results back in.
Context is everything the model can see at that moment.

</details>

---

**Q2.** A language model on its own is deterministic. True or false?

<details>
<summary>Answer</summary>

False. A language model is probabilistic: the same input can produce slightly
different outputs each time. Deterministic is the property of normal code (two
plus two is always four). Agents inherit this probabilistic nature from their
model.

</details>

---

**Q3.** Why can't a model know the contents of a file it has never been shown?

<details>
<summary>Answer</summary>

Because the model can only reason about what is in its context. If a file has
not been read into context, the model has never seen its contents — it can only
guess what might be in it. An agent may have a tool that can act on a named
file, but the model still cannot know the file's contents until the relevant
content is shown to it.

</details>

---

**Q4.** You run an agent twice on the same input. The wording differs, and one
answer makes a better decision. What does this tell you about how you should
test an agent?

<details>
<summary>Answer</summary>

It tells you two things. Wording variation is expected and is not automatically
a defect. Quality or decision variation is exactly why testing an agent by
running it once and checking the exact output is not reliable. Instead you test
with *evals*: run many examples, look at the results together, and judge the
behaviour across the range of inputs.

</details>

---

**Q5.** Finish this sentence in your own words: "An agent can draft a reply to
a stale issue, but it cannot …"

<details>
<summary>Answer</summary>

Any reasonable completion that captures the human-oversight theme from the
source page, for example: "… post it without a maintainer reviewing and
approving the proposal." The key idea is that the agent proposes; a person
confirms.

</details>

---

## Summary

An agent is a loop. A language model at its centre reads text and picks one
action at a time; tools turn those actions into real effects in the world; the
loop feeds results back so the model can act again; context is everything the
model can see. Because the model is probabilistic, agents are tested with evals
over many examples, not by checking one output once.

These ideas recur in every later lesson. Lesson 2 builds on them directly,
showing how to drive an agent through a conversation and steer it when it
starts off in the wrong direction.

---

## Next

**[Lesson 2 — Working with agents](../working-with-agents.md)**. If the packaged
lesson wrapper is not available in your copy yet, follow the source page
directly.

---

## Licence

Apache License 2.0 (PRINCIPLE 17). Pages written with help from AI carry a
`Generated-by:` note in their commit message following ASF Generative Tooling
Guidance.
