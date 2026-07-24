<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Facilitator guide — Building and running AI agents for open-source projects](#facilitator-guide--building-and-running-ai-agents-for-open-source-projects)
  - [Who this guide is for](#who-this-guide-is-for)
  - [Module overview](#module-overview)
  - [Delivery formats](#delivery-formats)
    - [Self-paced with facilitator check-ins](#self-paced-with-facilitator-check-ins)
    - [Instructor-led workshop (one day)](#instructor-led-workshop-one-day)
    - [Two-session intensive](#two-session-intensive)
    - [LMS-based self-study](#lms-based-self-study)
  - [Environment setup](#environment-setup)
    - [In-person](#in-person)
    - [Virtual](#virtual)
  - [Schedule templates](#schedule-templates)
    - [One-day workshop (~8 hours with breaks)](#one-day-workshop-8-hours-with-breaks)
    - [Two-session intensive](#two-session-intensive-1)
    - [Weekly reading group (~11 weeks)](#weekly-reading-group-11-weeks)
  - [Per-lesson facilitator notes](#per-lesson-facilitator-notes)
    - [Lesson 1 — What agents are](#lesson-1--what-agents-are)
    - [Lesson 2 — Working with agents](#lesson-2--working-with-agents)
    - [Lesson 3 — Choosing models](#lesson-3--choosing-models)
    - [Lesson 4 — Your first skill](#lesson-4--your-first-skill)
    - [Lesson 5 — Writing safe skills](#lesson-5--writing-safe-skills)
    - [Lesson 6 — Debugging a skill](#lesson-6--debugging-a-skill)
    - [Lesson 7 — Writing portable skills](#lesson-7--writing-portable-skills)
    - [Lesson 8 — Eval-driven development](#lesson-8--eval-driven-development)
    - [Lesson 9 — Agentic and autonomous work](#lesson-9--agentic-and-autonomous-work)
    - [Lesson 10 — English as a programming language](#lesson-10--english-as-a-programming-language)
    - [Lesson 11 — How to contribute](#lesson-11--how-to-contribute)
  - [Customising for your project](#customising-for-your-project)
    - [Replacing placeholders](#replacing-placeholders)
    - [Adapting examples](#adapting-examples)
    - [Selecting lessons](#selecting-lessons)
  - [Assessment and progression](#assessment-and-progression)
    - [Self-check questions](#self-check-questions)
    - [When a learner is not ready to proceed](#when-a-learner-is-not-ready-to-proceed)
    - [No formal certification](#no-formal-certification)
  - [Frequently asked questions](#frequently-asked-questions)
  - [Upstream contribution](#upstream-contribution)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Facilitator guide — Building and running AI agents for open-source projects

This guide is for **instructors and facilitators** running the Apache Training
module (this directory) as a structured course. Learners working through the
material self-paced do not need it — the lesson files stand alone.

---

## Who this guide is for

A **facilitator** is anyone organising and running the module for others:
a PMC member running a project on-boarding session, a community mentor
hosting a workshop at a conference, or a team lead running a weekly reading
group. No prior experience teaching AI is required; the lesson files carry the
technical content. This guide covers the logistics, timing, and facilitation
moves that turn static reading material into an active learning session.

---

## Module overview

Eleven lessons totalling approximately 7.5 hours of learner time:

| Lesson | Topic | Learner time |
|---|---|---|
| 1 | What agents are | 30 min |
| 2 | Working with agents | 30 min |
| 3 | Choosing models | 35 min |
| 4 | Your first skill | 60 min |
| 5 | Writing safe skills | 45 min |
| 6 | Debugging a skill | 50 min |
| 7 | Writing portable skills | 35 min |
| 8 | Eval-driven development | 60 min |
| 9 | Agentic and autonomous work | 45 min |
| 10 | English as a programming language | 30 min |
| 11 | How to contribute | 30 min |

Each lesson follows the same structure: read the source page → work through
four or five exercises (20–40 min) → answer the self-check questions. Exercises need
no computer; they use paper, a whiteboard, or a shared document. The self-check
questions include hidden answers that learners reveal to grade themselves.

---

## Delivery formats

### Self-paced with facilitator check-ins

Learners work through one or two lessons per week on their own. The
facilitator runs a 30-minute weekly check-in to answer questions and debrief
the self-check answers. **Recommended for distributed teams and reading
groups.** Lowest facilitation overhead; high learner flexibility.

### Instructor-led workshop (one day)

Cover all eleven lessons in a single day. Use the one-day schedule in the
[Schedule templates](#schedule-templates) section. Requires a dedicated room
or video-conference session. Best for initial project on-boarding, conference
tutorials, or intensive team training.

### Two-session intensive

Split the module across two half-days or two evenings. Lessons 1–5 (concepts
and first skill) in session one; lessons 6–11 (safety, portability, evals,
autonomy, prose discipline, and contributing) in session two. A natural break point: session two
builds on working skills, so learners have time between sessions to write one
for their own project.

### LMS-based self-study

Upload each lesson file as a unit in your learning management system. Tag
learning time using the per-lesson estimates above. Use the self-check
questions as the in-LMS quiz. The facilitator role reduces to answering
questions in the discussion forum.

---

## Environment setup

### In-person

- **Projector or large screen.** You will display source pages, lesson files,
  and learner diagrams. A browser with two tabs (source page and lesson file)
  is all you need.
- **Whiteboard or flip chart.** Every exercise mentions "paper or whiteboard";
  a shared whiteboard (physical or digital) works well for group exercises.
- **No computers for learners** are required for the exercises themselves. If
  learners have laptops, remind them to close them during exercise time to
  keep the group in sync.
- **Printed exercise sheets (optional).** The exercises are short enough to
  read from a screen, but some facilitators find printed sheets reduce context
  switching during exercises.

### Virtual

- **Video-conference platform** with screen sharing and a breakout-room
  feature. Breakout rooms let pairs or small groups work through exercises
  without the full group listening in.
- **Shared document** (a collaborative whiteboard or a shared markdown file)
  replaces the physical whiteboard. One doc per lesson works well; create them
  before the session.
- **Paste the exercise text into the shared doc** so learners can write their
  answers inline. After the exercise, unmute/reconvene and ask two or three
  groups to share.

---

## Schedule templates

### One-day workshop (~8 hours with breaks)

| Time | Activity |
|---|---|
| 09:00–09:15 | Welcome, objectives, module overview |
| 09:15–09:45 | Lesson 1 — What agents are |
| 09:45–10:15 | Lesson 2 — Working with agents |
| 10:15–10:50 | Lesson 3 — Choosing models |
| 10:50–11:00 | Break |
| 11:00–12:00 | Lesson 4 — Your first skill (60 min) |
| 12:00–13:00 | Lunch |
| 13:00–13:45 | Lesson 5 — Writing safe skills |
| 13:45–14:35 | Lesson 6 — Debugging a skill |
| 14:35–15:10 | Lesson 7 — Writing portable skills |
| 15:10–15:20 | Break |
| 15:20–16:20 | Lesson 8 — Eval-driven development (60 min) |
| 16:20–17:05 | Lesson 9 — Agentic and autonomous work |
| 17:05–17:35 | Lesson 10 — English as a programming language |
| 17:35–18:05 | Lesson 11 — How to contribute |
| 18:05–18:20 | Wrap-up and next steps |

Reduce to a half-day by covering lessons 1–5 only (concepts and first
skill). Lessons 6–11 form a natural second half.

### Two-session intensive

**Session 1 (~3.75 hours):** Welcome (15 min), lessons 1–5 (200 min), wrap-up
(10 min). Assign: write one skill for your project between sessions.

**Session 2 (~4.75 hours):** Review and share skills from the between-session
assignment (20 min), lessons 6–11 (250 min), retrospective (15 min).

### Weekly reading group (~11 weeks)

One lesson per week, 45 minutes per session. Learners read the source page
and lesson file before the session. The session time is for exercises and
debrief only.

| Week | Lesson | Prep (before session) |
|---|---|---|
| 1 | What agents are | Read `what-agents-are.md` and lesson 1 |
| 2 | Working with agents | Read `working-with-agents.md` and lesson 2 |
| 3 | Choosing models | Read `choosing-models.md` and lesson 3 |
| 4 | Your first skill | Read `your-first-skill.md` and lesson 4 |
| 5 | Writing safe skills | Read `writing-safe-skills.md` and lesson 5 |
| 6 | Debugging a skill | Read `debugging-skills.md` and lesson 6 |
| 7 | Writing portable skills | Read `portable-skills.md` and lesson 7 |
| 8 | Eval-driven development | Read `eval-driven-development.md` and lesson 8 |
| 9 | Agentic and autonomous work | Read `agentic-work.md` and lesson 9 |
| 10 | English as a programming language | Read `english-as-code.md` and lesson 10 |
| 11 | How to contribute | Read `contributing.md` and lesson 11 |

---

## Per-lesson facilitator notes

For each lesson: the core idea to anchor, discussion prompts to deepen the
group's understanding, common misconceptions to correct, and rough timing
guidance for instructor-led delivery.

These timings are for instructor-led delivery, where the reading is compressed
(skimmed, or presented together) to leave most of the slot for exercises. They
deliberately allocate less reading time than the self-paced estimates in each
lesson's own header — a workshop should spend its time on active practice, not
on reading the source page aloud.

---

### Lesson 1 — What agents are

**Core idea.** An agent is a loop: model, tools, loop, context. Every other
idea in the module is a consequence of this structure.

**Timing.** 30 min: 10 min to read the source page together or in pairs,
15 min exercises, 5 min self-check debrief.

**Discussion prompts.**

- "Before this lesson, how would you have described what an AI agent does?
  What would you change about that description now?"
- "The source page says the model can only reason about what is in its
  context. What does that mean for a skill you want to write for
  `<PROJECT>`? What would you need to put into context?"
- "Why does probabilistic behaviour matter more for testing an agent than
  for testing a function? What would you do differently?"

**Common misconceptions.**

- *"The agent has access to the whole repo / internet / database."* No — it
  can only see what has been explicitly put into context via tools. Draw the
  loop on the board and mark where information enters.
- *"Agents are deterministic if you use them the same way each time."*
  No — the model is probabilistic. The same input can produce different
  outputs. This is not a defect; it is a property to design around.

---

### Lesson 2 — Working with agents

**Core idea.** An agent is a collaborator, not a command-runner. The quality
of what you get out depends on the quality of what you put in.

**Timing.** 30 min: 10 min reading, 15 min exercises, 5 min debrief.

**Discussion prompts.**

- "Think about a task you would want to delegate to an agent in `<PROJECT>`.
  Write the first message you would send. Now read it back — is it complete?
  What would the agent need to clarify?"
- "The page talks about 'treating outside text as data, not instructions'.
  What does that mean in practice for a skill that processes issue comments
  from the public?"
- "When should you give up on steering a mid-task agent and start over?
  What signals tell you the agent is on the wrong path?"

**Common misconceptions.**

- *"You should give the agent as much context as possible."* More context is
  not always better — a long, unfocused context degrades response quality.
  The lesson's point is *relevant* context, not maximum context.
- *"If the agent makes a mistake, retry until it gets it right."* Retrying
  without changing the prompt will produce the same distribution of answers.
  Diagnose first; change the prompt, not just the run count.

---

### Lesson 3 — Choosing models

**Core idea.** There is no single best model for every task; there is a
best model for a given capability, speed, and cost combination, and the
eval suite is what decides.

**Timing.** 35 min: 10 min reading, 20 min exercises, 5 min debrief.

**Discussion prompts.**

- "For a skill that triages incoming issues on `<PROJECT>`, would you reach
  for the cheapest available model, the most capable, or something in
  between? What information would you need to decide?"
- "The page says 'let evals decide'. What does an eval tell you that a few
  manual test runs don't?"
- "A 'judge model' is a model that scores another model's output. When might
  you use a judge model for `<PROJECT>` tasks? What could go wrong?"

**Common misconceptions.**

- *"Always use the most capable model — it is most reliable."* Capability
  and reliability are different dimensions. The most capable model may be
  over-specified, slower, and more expensive for simple triage tasks.
- *"Local models are always worse."* For focused, rule-following tasks with
  tight prompts, a local model can match hosted performance at zero cost.
  The `local-smoke` eval tag exists precisely to test this claim.

---

### Lesson 4 — Your first skill

**Core idea.** A skill is a plain Markdown file with YAML frontmatter. Writing
one is within reach of any contributor who can open a pull request.

**Timing.** 60 min: 15 min reading, 35 min exercises (the writing exercise
takes longer), 10 min debrief.

**Discussion prompts.**

- "What task in `<PROJECT>` would benefit most from a repeatable agent skill?
  Why that one?"
- "What is the difference between a skill and a script? When would you reach
  for one instead of the other?"
- "The skill format requires a `description` field that triggers the skill.
  If your description is vague, what happens? Try writing two descriptions
  for the same skill — one vague, one precise — and compare them."

**Common misconceptions.**

- *"A skill needs to handle every possible edge case before I can ship it."*
  No — ship the happy path first, add an eval suite, and expand from there.
  A skill without an eval suite is incomplete; a skill with an eval suite can
  grow incrementally.
- *"The `description` field is just documentation."* The description is what
  the agent reads to decide *when* to invoke the skill. It is a trigger, not
  a comment.

---

### Lesson 5 — Writing safe skills

**Core idea.** Safety is not a review gate at the end; it is three properties
built into the skill as you write it: propose-confirm-act, data-not-instructions,
and sandbox-by-default.

**Timing.** 45 min: 10 min reading, 30 min exercises (the propose/confirm
classification exercise is dense), 5 min debrief.

**Discussion prompts.**

- "For the skill you imagined in lesson 4, which steps would need a
  confirm gate and which could run without one? Where is the line for
  `<PROJECT>`'s context?"
- "What is the difference between treating outside text as data vs.
  as instructions? Give an example from `<PROJECT>`'s issue tracker of
  text that could be mistaken for an instruction."
- "A skill that reads files only needs no special sandbox configuration.
  A skill that writes to the repo, posts comments, or sends email needs
  explicit permission entries. Why is the default 'no permission' and not
  'ask at runtime'?"

**Common misconceptions.**

- *"Propose-confirm-act slows the agent down — we want automation."*
  The confirm step is cheap: it is a human reading a proposal and pressing
  one button. Removing it when the action is irreversible (a posted comment,
  a merged PR) removes the only safety net.
- *"Data-not-instructions only applies to security-sensitive skills."*
  It applies to any skill that processes public or user-supplied text.
  Prompt injection is not limited to security contexts.

---

### Lesson 6 — Debugging a skill

**Core idea.** Debugging an agent is diagnostic work: isolate the failing
step, read the transcript, find the moment the agent diverged, and adjust the
prompt or context — not the retry count.

**Timing.** 50 min: 10 min reading, 35 min exercises, 5 min debrief.

**Discussion prompts.**

- "You run a skill three times on the same issue and get three different
  verdicts. How do you diagnose whether this is a prompt problem, a context
  problem, or just normal variance?"
- "What is the first thing you would look at in a skill transcript when the
  output looks wrong?"
- "When is it correct to increase the temperature of a model, and when is
  that the wrong move?"

**Common misconceptions.**

- *"Add more examples to the prompt and the skill will stop making mistakes."*
  More examples help with format and style. They do not fix ambiguous
  instructions — the model will still apply the ambiguous rule, just more
  consistently. Fix the rule first, then add examples.
- *"If the eval passes, the skill is correct."* An eval passing means the
  skill behaves correctly on the cases you tested. It does not mean it is
  correct on all inputs. Eval coverage is a claim about the tested set, not
  the full input space.

---

### Lesson 7 — Writing portable skills

**Core idea.** A skill that hard-codes project names, tool paths, or hosting
assumptions only works in one place. Portability comes from placeholders and
config-resolution, not from "making it generic."

**Timing.** 35 min: 10 min reading, 20 min exercises, 5 min debrief.

**Discussion prompts.**

- "Look at the skill draft you started in lesson 4. How many project-specific
  strings are in it? What would you need to replace to make it reusable across
  `<PROJECT>` and a sister project?"
- "The `<tracker>` placeholder resolves differently for a GitHub project and
  a Jira-backed project. Who decides which adapter to load, and when?"
- "What is the difference between a placeholder and a conditional? When is
  'if GitHub else Jira' the wrong approach?"

**Common misconceptions.**

- *"My skill only runs on `<PROJECT>`, so portability is not my concern."*
  Even a project-internal skill benefits from placeholders: it is easier to
  test with a dummy config, easier to explain to new contributors, and easier
  to donate upstream if the project later wants to.
- *"Placeholders make the skill harder to read."* A well-named placeholder
  (`<tracker>`, `<PROJECT>`) is more readable than a hardcoded URL. It makes
  the assumption explicit rather than hiding it in a string.

---

### Lesson 8 — Eval-driven development

**Core idea.** Correctness for an agent is not a binary; it is a distribution
over many inputs. An eval suite is how you measure that distribution and track
it over time.

**Timing.** 60 min: 15 min reading, 35 min exercises (the fixture design
exercise takes longer), 10 min debrief.

**Discussion prompts.**

- "For the skill you started in lesson 4, what are the four cases that
  every eval suite should cover? Write them out."
- "A colleague says their skill 'works fine' because they ran it five times
  on the same issue and it produced a good result. What is missing from that
  claim?"
- "What is the difference between a `local-smoke` eval case and a
  `frontier-only` case? Why does that distinction matter for a project that
  wants to adopt the skill with a local model?"

**Common misconceptions.**

- *"I will add evals after the skill is stable."* A skill without an eval
  suite cannot be called stable. Evals are what establish the baseline that
  'stable' means.
- *"More eval cases are always better."* Coverage matters more than count.
  Ten well-designed cases covering distinct failure modes are more useful than
  a hundred cases that all test the same happy path.

---

### Lesson 9 — Agentic and autonomous work

**Core idea.** Autonomy is not an on/off switch; it is a dial with four
rungs. Moving up the dial is only safe once you have the guardrails and evals
that make it safe — not before.

**Timing.** 45 min: 15 min reading, 25 min exercises, 5 min debrief.

**Discussion prompts.**

- "Where on the supervision dial does `<PROJECT>`'s current automated
  work sit? Where would you *want* it to sit in twelve months, and what
  guardrails would you need to add first?"
- "The propose-confirm-act pattern is the guardrail for supervised
  automation. What is the equivalent guardrail for unattended automation?"
- "A skill that runs on a cron schedule and posts comments autonomously
  has a larger blast radius than one that posts under human review. What
  does 'larger blast radius' mean concretely for `<PROJECT>`'s community?"

**Common misconceptions.**

- *"Fully autonomous is the goal — human review is just friction."*
  Autonomy is a tool, not an end state. The question is not 'how do we
  remove the human?' but 'at what rung is the risk acceptable given the
  guardrails we have?'
- *"Compounding errors are unlikely in practice."* In a short session they
  are unlikely. In a long autonomous run, the probability compounds across
  each action taken. One misclassified issue that triggers an incorrect
  follow-up action that triggers a public reply illustrates the chain.

---

### Lesson 10 — English as a programming language

**Core idea.** The words in a skill are the program. Ambiguity is a bug
class. The four disambiguating moves — define terms, say what done looks
like, state boundaries, name edge cases — are the tools for closing gaps.

**Timing.** 30 min: 10 min reading, 15 min exercises, 5 min debrief.

**Discussion prompts.**

- "Find a word in a skill you have read (or written) that is not defined.
  What would a model do with it? Write a one-sentence definition that closes
  the gap."
- "The page says 'ambiguity is the new class of bug'. Give an example of
  a wording ambiguity in a skill that would not be caught by a linter or
  type-checker but would cause the agent to behave unexpectedly."
- "DRY applies to prose as well as code. Find two skills in the framework
  that define the same concept differently. What is the cost of that
  duplication, and how would you fix it?"

**Common misconceptions.**

- *"Natural language is inherently imprecise — there is nothing you can do."*
  Natural language *can* be precise. Technical writing, legal text, and
  formal specifications are all precise natural language. The discipline is
  learnable and the four moves are concrete.
- *"The model will ask for clarification if something is ambiguous."*
  Models do not reject ambiguous instructions; they act on a plausible
  interpretation. The result is silent divergence between intent and
  execution.

---

### Lesson 11 — How to contribute

**Core idea.** Most of Magpie is prose the agent executes, so contributing is
within reach of anyone who can write precisely. The four first contributions —
fix a skill, improve a doc, add a pattern, write a new skill — all follow the
same spec-first, eval-backed, reviewed path.

**Timing.** 30 min: 10 min reading, 15 min exercises, 5 min debrief.

**Discussion prompts.**

- "Of the four first-contribution types (fix a skill, improve a doc, add a
  pattern, write a new skill), which would you start with for `<PROJECT>`, and
  why that one?"
- "Take a change you might make to one of `<PROJECT>`'s skills. Does it alter a
  rule, a flow, or a contract? Walk the group through whether it needs a spec
  update."
- "You are reviewing a contributor's first skill PR. Which of the five
  framework rules would you check first, and what would you look for in the
  diff?"

**Common misconceptions.**

- *"You need to be a strong programmer to contribute."* No — most contributions
  are prose the agent executes. Clear thinking and precise writing are the core
  skills; systems programming is only needed for the tool layer (`tools/`).
- *"Evals can come in a follow-up PR."* No — a skill without a matching eval
  suite is not finished, and a PR that defers the evals will not pass review.
  The eval suite ships in the same PR as the skill.

---

## Customising for your project

### Replacing placeholders

Every exercise uses `<PROJECT>` where a real project name would appear.
Before running the module, decide whether to:

1. **Replace globally** — do a find-and-replace in your copies of the lesson
   files. Fast; produces more readable exercise sheets.
2. **Ask learners to substitute as they go** — keeps the original files
   unmodified; slightly more cognitive load during exercises.

Other placeholders you may encounter:

| Placeholder | What it represents |
|---|---|
| `<PROJECT>` | The adopting project's name |
| `<tracker>` | The issue tracker (e.g. GitHub Issues, JIRA) |
| `<upstream>` | The main repository (e.g. `org/repo`) |
| `<security-list>` | The private security mailing list |

### Adapting examples

The source pages draw examples from open-source project maintenance. If your
audience works in a different domain (internal tooling, data pipelines,
etc.), swap the examples. The lesson structure remains the same; only the
illustrative context changes.

### Selecting lessons

You do not need to teach all eleven lessons in one sitting. A team that already
has experience with agent concepts and wants to focus on safety can start at
lesson 5. A team writing its first eval suite can teach lessons 1, 4, and 8
as a standalone mini-module. The lessons reference each other but are
designed to be understandable on their own.

---

## Assessment and progression

### Self-check questions

Each lesson ends with five or six self-check questions with hidden answers. Learners
reveal the answers themselves and grade their own understanding. This is
intentional: the goal is self-knowledge, not formal grading.

In an instructor-led session, use the self-check as a **group debrief**:
read each question aloud and ask learners to write a brief answer before you
reveal the answer. Gaps between a learner's answer and the reference answer
are the most productive discussion point.

### When a learner is not ready to proceed

If a learner cannot answer two or more self-check questions for a lesson,
suggest re-reading the source page before moving on. The lessons build
sequentially: a learner who does not understand context (lesson 1) will
struggle with evals (lesson 8).

### No formal certification

This module does not issue certificates. The intended outcome is that a
learner can read, write, debug, and evaluate a skill for their own project.
The evidence of that outcome is a skill they have written and an eval suite
that passes — not a quiz score.

---

## Frequently asked questions

**"Do learners need a running agent installation?"**
No. The exercises are paper-based or whiteboard-based. Learners can work
through all eleven lessons without installing any software. Lesson 4 (your first
skill) suggests writing a skill file; that requires only a text editor.

**"Can I skip the exercises and just present the source pages?"**
You can, but learners retain substantially less without active practice.
Exercises in this module are not optional enrichment; they are the mechanism
by which learners move from reading to application.

**"What if learners have very different backgrounds — some have never seen
a language model, others use one daily?"**
Lesson 1 is the equaliser: it defines terms that even experienced users often
hold loosely (the difference between a model and an agent, what context means
precisely). Spend extra time there. Experienced learners often find the
precision useful even if the concept is familiar.

**"How do I handle learners who want to build something live during the
module?"**
Encourage it as optional enrichment, but do not let live-building block
the group. Live building sessions fit better in the hands-on lab
([`tutorials.md`](../tutorials.md)) than during the lesson sequence. Point
interested learners there after the module.

**"Are there formal assessment instruments for each lesson?"**
Not yet. The self-check questions are the primary formative assessment.
Formal rubrics and summative assessments are planned for a future iteration
of the module; facilitators who develop them are encouraged to contribute
them back upstream (see [Upstream contribution](#upstream-contribution)).

---

## Upstream contribution

This module is shaped for contribution to
[Apache Training](https://training.apache.org/) so it can be taught beyond
the projects that adopt this framework. If you run the module and find gaps —
a lesson that generates persistent confusion, a discussion prompt that
falls flat, a misconception this guide does not address — please:

1. Open an issue or pull request against this repository (the framework
   repo, not your adopter repo) with the proposed change.
2. If you are contributing to Apache Training directly, the module's
   Apache-2.0 licence permits it. Coordinate with the Apache Training
   project on format requirements before submitting.
3. Add your project's experience to the module's pilot record so future
   facilitators can calibrate against real data.

Contributions that improve the instructor guide carry the same
`Generated-by:` convention as contributions to the lesson files: if you use
a generative tool to draft a section, note it in the commit message following
[ASF Generative Tooling Guidance](https://www.apache.org/legal/generative-tooling-guidance.html).

---

## Licence

Apache License 2.0 (PRINCIPLE 17). Pages written with help from AI carry a
`Generated-by:` note in their commit message following ASF Generative Tooling
Guidance.
