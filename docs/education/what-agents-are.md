<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [What agents are](#what-agents-are)
  - [Words used on this page](#words-used-on-this-page)
  - [The one-sentence version](#the-one-sentence-version)
  - [Start with the model](#start-with-the-model)
  - [An agent adds tools and a loop](#an-agent-adds-tools-and-a-loop)
  - [What the agent can "see": context](#what-the-agent-can-see-context)
  - [Why this is different from normal code](#why-this-is-different-from-normal-code)
  - [Why this matters for a maintainer](#why-this-matters-for-a-maintainer)
  - [Check your understanding](#check-your-understanding)
  - [How this connects to the other guides](#how-this-connects-to-the-other-guides)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# What agents are

This is the first page of the progression. It answers one question: what *is*
an AI agent, in plain words, before we ask you to build one. If you have never
worked with AI beyond typing into a chat box, start here. Nothing on this page
assumes you have.

By the end you should be able to say, in your own words, what an agent is, what
makes it different from the programs you already know, and why that difference
changes how you build and test your work. The pages after this one build on
these ideas, one at a time.

## Words used on this page

New to some of these words? Here is what they mean here. The
[landing page](README.md) has a fuller list.

- **AI model** (also called a large language model, or LLM): the software that
  reads text and writes a response. It is the "brain" the agent uses.
- **Agent**: a program that uses an AI model to do a task, one step at a time.
- **Tool**: an action the agent can take beyond writing text, such as reading a
  file, searching the web, or running a command. The model decides *when* to use
  a tool; the tool does the actual work.
- **Context**: everything the model can "see" at one moment. That includes your
  request, the files it has read, and the results of tools it has run so far.
- **Deterministic and probabilistic**: normal code is *deterministic*, so the
  same input always gives the same result. A model is *probabilistic*, so the
  same input can give slightly different results each time.

---

## The one-sentence version

An **agent** is a loop. A language model reads what it knows so far, decides on
one next action, takes it with a tool, reads the result, and repeats, until the
task is done.

Everything else on this page unpacks that sentence.

## Start with the model

At the centre of every agent is a **language model**. On its own, a model does
exactly one thing: it reads some text and writes text that plausibly continues
it. Ask it a question, it writes an answer. Give it a paragraph, it writes the
next paragraph. It has no memory between calls, no way to open a file, and no way
to run a command. It only reads and writes text.

That sounds limited, and by itself it is. A model that can only write text can
tell you *how* to close a stale issue, but it cannot close it. It can describe
the contents of a file it has never seen, but it cannot read the file to check.

## An agent adds tools and a loop

An **agent** wraps the model in two things the model does not have on its own:

1. **Tools**, which are concrete actions in the real world. "Read this file."
   "Search the code for this word." "Run this command and give me the output."
   "Open a saved comment draft." "Open an issue draft." Each tool does one job
   and reports back.

2. **A loop**, which is the machinery that runs the model again and again. Each
   time round the loop, the model sees everything that has happened so far and
   picks *one* next action. If that action is a tool, the loop runs the tool,
   adds the result to what the model can see, and asks the model again. If the
   model decides the task is finished, the loop stops.

So the shape of an agent is:

```text
you ask for something
  → model looks at the request, picks one action
  → the loop runs that tool
  → model looks at the result, picks the next action
  → ... (repeat) ...
  → model decides it is done, and answers you
```

The model is still only reading and writing text. But now some of the text it
writes is *"use this tool with these inputs"*, and the loop turns that text into
a real action and feeds the result back. Which actions are allowed depends on
the tools and permissions you give the agent: a safe teaching setup might only
open a saved comment draft, while a more privileged workflow might post after a
maintainer approves. That feedback loop of act, observe, and act again is what
makes an agent more than a chatbot. It can look things up, check its own work,
and correct course when a result surprises it.

## What the agent can "see": context

At any moment, the model can only reason about what is in its **context**: the
running transcript of your request, the files it has read, the tool results so
far, and the instructions it was given. It cannot see anything it has not been
shown. If it has not read a file, it does not know what is in it; it can only
guess.

This matters for two reasons you will meet again and again:

- **Context is finite.** There is a limit to how much text fits at once. A long
  task can fill it up, and older detail then has to be summarised or dropped.
  Good agents manage this deliberately.
- **What you put in context steers the answer.** The instructions, the examples,
  and the files you make available are the main levers you have. This is the
  seed of an idea the [English as a programming language](english-as-code.md)
  page develops fully: for an agent, the words you choose *are* the program.

## Why this is different from normal code

You have probably written or read code that runs the same way every time. Two
plus two is four, every run, forever. That is **deterministic** behaviour, and
almost every tool you have used is built on it.

An agent is **probabilistic**. The model does not compute one guaranteed answer.
It produces a *likely* one, and "likely" leaves room for variation. Ask the same
question twice and you may get two wordings, two orderings, and occasionally two
different decisions. Wording variation is not automatically a bug. Decision or
quality variation is a signal to test the agent across many examples, because it
may or may not be acceptable for the workflow.

Three consequences follow, and they shape everything in this progression:

| In normal code | With an agent |
|---|---|
| Same input gives the same output | Same input gives *similar* output, which can vary |
| Correct is yes-or-no | Correct is a range, better or worse by degree |
| You test with fixed checks | You test with **evals**: many examples, judged as a whole |
| The program is the code | The program is the code *and the words you give it* |

You do not need to master the right-hand column yet. The point for now is only
that "it changed its wording" is expected, while "it changed its decision" is
something to evaluate. Testing an agent means running many examples and looking
at the results together, not checking one answer once.

## Why this matters for a maintainer

If you maintain a project, an agent is a new kind of helper. It can draft the
reply to a closed pull request, sort a pile of incoming issues, or check whether
a new dependency's licence fits your policy. It does this as a *proposal* you
review, not an action it takes behind your back. It works in steps you can watch,
using tools you granted it, inside limits you set.

But because its behaviour can vary, you cannot just write it once and trust it
forever. You describe what you want in plain language, you give it examples, and
you test it with evals until it behaves well across the range of real inputs.
That is a genuinely different craft from writing a function. It is not harder,
but it is different, and it is the craft this stream teaches.

## Check your understanding

Before moving on, can you answer these in a sentence each?

- What are the two things an agent adds to a bare language model?
- What does it mean that the agent can only reason about its *context*?
- Why can the same request give a slightly different answer twice, and why is
  that not automatically a bug?

If any of those is fuzzy, re-read the matching section. The next page assumes
these three ideas.

## How this connects to the other guides

- **[How to work with agents](working-with-agents.md)** is the next step. Now
  that you know what an agent *is*, that page shows how to actually drive one in
  a conversation and get useful results.
- **[English as a programming language](english-as-code.md)** develops the idea,
  raised above, that the words you give an agent are the real program.
- **[MISSION.md](../../MISSION.md)** and **[PRINCIPLES.md](../../PRINCIPLES.md)**
  explain why Magpie treats building with agents as a first-class craft worth
  teaching (PRINCIPLE 18).

## Licence

Everything in `docs/education/` is under the Apache License 2.0 (PRINCIPLE 17).
Pages written with help from AI carry a `Generated-by:` note in their commit
message, following ASF Generative Tooling Guidance.
