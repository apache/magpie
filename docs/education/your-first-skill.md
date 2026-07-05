<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Your first skill](#your-first-skill)
  - [Words used on this page](#words-used-on-this-page)
  - [Before you start](#before-you-start)
  - [What makes a skill different from code](#what-makes-a-skill-different-from-code)
  - [Step 0 — Look around the repository](#step-0--look-around-the-repository)
  - [Step 1 — Pick one small use case](#step-1--pick-one-small-use-case)
  - [Step 2 — Create the starter skill file](#step-2--create-the-starter-skill-file)
  - [Step 3 — Write the skill body](#step-3--write-the-skill-body)
  - [Step 4 — Check the skill definition](#step-4--check-the-skill-definition)
  - [Step 5 — Write an eval suite](#step-5--write-an-eval-suite)
  - [Step 6 — Open a pull request](#step-6--open-a-pull-request)
  - [After merge: keeping your skill current](#after-merge-keeping-your-skill-current)
  - [Common first-time mistakes](#common-first-time-mistakes)
  - [Where to go next](#where-to-go-next)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Your first skill

This is a step-by-step guide to writing your first working skill in
`<PROJECT>`. It takes you from "I have an idea" to "the pull request is merged".
You do not need any earlier experience with the framework.

This is not the full authoring reference. Once you know the shape of a skill,
the [`magpie-write-skill`](../../skills/write-skill/SKILL.md)
skill (you run it with `/write-skill`) takes you through every check, safety
step, and packaging detail. Come back to it after your first skill has landed
and you want the complete checklist.

## Words used on this page

New to some of these words? Here is what they mean here. The education landing
page has a fuller list.

- **Skill**: a text file (in Markdown) that tells the agent how to do one job,
  step by step.
- **Agent**: a program that uses an AI model to carry out a task.
- **Prompt**: the written input the agent receives.
- **Eval** (evaluation): a repeatable test of the agent's output. Because the
  output can vary, you run it over several example inputs.
- **Fixture**: one example input for an eval, together with a note on what a
  good answer must contain or avoid.
- **Frontmatter**: the small block of settings at the top of a skill file,
  between two `---` lines.
- **Placeholder**: a stand-in name such as `<PROJECT>` or `<tracker>` that each
  project fills in with its own value.
- **Pull request (PR)**: the change you offer to the project for review before
  it is merged.
- **Prompt injection**: when text the agent is reading tries to give it new
  orders. It is an attack, not a real instruction.

---

## Before you start

You need:

- A working checkout of the `<framework>` repository, and a setup that can run
  `uv` commands (see [CONTRIBUTING.md](../../CONTRIBUTING.md)).
- Enough knowledge of the project to name one task a maintainer now does by
  hand that the agent could draft instead.
- Ten to thirty minutes, depending on how much you need to read.

You do not need to understand the full set of skill types, the Privacy-LLM
gate, or how adapters work before you start. Those matter for complex skills. A
first skill almost always avoids them.

---

## What makes a skill different from code

A skill is a Markdown file that an AI agent reads and follows, step by step. It
is not a function, a script, or a config file.

| Traditional code | A skill |
|---|---|
| Runs the same way every time | Read by a language model, so the output can vary |
| Right or wrong (yes or no) | Better or worse at the task, by degree |
| Checked by a test suite | Checked by an **eval suite**: example inputs plus what a good answer must look like |
| Changed when the logic changes | Changed when the agent's behaviour drifts from what you meant |
| "Does it pass?" | "Does it behave well across all the examples?" |

This changes how you think about "correct". You cannot test a skill the way you
test a function. Instead, you write example cases that cover the range of real
inputs, and you check that the agent's output meets the criteria you care
about. When you find a new way it can fail, you add an example for it.

The [pattern catalogue](pattern-catalogue.md) has ready-to-copy
examples. The [eval-driven-development](eval-driven-development.md) page goes
deeper on how to judge output that can vary.

---

## Step 0 — Look around the repository

Skills live in `skills/<name>/SKILL.md`. Each skill is a directory (not
a single file), so there is room for supporting files, scripts, and eval
examples next to the skill text.

Read two or three existing skills first, to get a feel for the style:

```bash
ls skills/
cat skills/issue-fix-workflow/SKILL.md
```

Look at:

- The settings block (the frontmatter) at the top, between the `---` markers.
- The SPDX licence comment on the first line.
- The placeholders (`<PROJECT>`, `<tracker>`, `<upstream>`, `<security-list>`),
  used so that no real project name appears in the skill body.
- The "propose, confirm, act" loop: skills propose actions, and never carry
  them out until the maintainer confirms.

---

## Step 1 — Pick one small use case

Good first skills are small. One trigger, one output, one decision the agent
helps the person make. For example:

- *"When a contributor asks why their PR was closed, draft a reply that points
  to the right contributing guideline."*
- *"When a new dependency appears in a PR, check whether its licence fits, and
  flag it if not."*
- *"When an issue is closed as a duplicate, post a comment linking to the
  original."*

A skill that tries to do three things at once is harder to test, harder to
review, and harder to improve. Pick the smallest piece you can check.

---

## Step 2 — Create the starter skill file

The framework ships a script that creates a starter file for you. Run it from
the repository root, passing the skill name and the output directory:

```bash
python3 skills/write-skill/scripts/init_skill.py <name> --path skills/<name>
```

This creates `skills/<name>/SKILL.md` with the required settings keys,
the SPDX comment, the placeholder comment, and the adopter-overrides section
already in place.

Fill in the settings (the frontmatter) before you write the body:

```yaml
---
name: <name>
description: |
  One or two sentences. What does this skill do, and when is it useful?
  Written from the maintainer's perspective: "Triages incoming issues by
  …", not "This skill triages…".
when_to_use: |
  The trigger vocabulary. What phrases or situations cause the agent to
  invoke this skill? Be concrete — the agent uses this text to decide
  whether this is the right skill for the moment.
capability: capability:<tag>
license: Apache-2.0
---
```

The `capability:` tag places this skill in the framework's set of categories.
Look at the existing skills for the tag that fits best. Common values:
`capability:triage`, `capability:authoring`, `capability:security`,
`capability:release`, `capability:contributor-growth`.

---

## Step 3 — Write the skill body

A skill body is a list of numbered steps the agent follows in order. Each step
has a heading, a short note on why the step matters, and either a concrete
action for the agent to take or a decision for it to put to the maintainer.

The smallest useful structure:

```markdown
## Step 1 — [Name of what the agent does first]

[Why this step comes first. What context the agent needs.]

[The action: what to read, what to check, what to draft.]

## Step 2 — Propose to the maintainer

Draft a response with the following information:
- [Field 1]
- [Field 2]

Present this to the maintainer and wait for confirmation before
taking any action that is visible outside the session.
```

Every skill body must follow three rules:

1. **External content is data, not instructions** (PRINCIPLE 0). If the skill
   reads issue bodies, PR comments, email, or any other outside text, it passes
   that text through the Privacy-LLM gate or treats it as plain data. It never
   treats it as an order to the agent. Do not write a step that says "follow
   the instructions in the issue". Write a step that says "read the issue body
   to work out X".

2. **Propose, confirm, act.** Any action that is visible outside the session
   (posting a comment, applying a label, closing an issue) must be proposed to
   the maintainer and confirmed before it runs. The skill ends with a proposal,
   not an action, unless the maintainer has confirmed in this session.

3. **Use placeholders, not project names.** Write `<tracker>`, `<upstream>`,
   `<PROJECT>`, and `<security-list>` wherever a real project name would go. A
   skill with `apache/airflow` written into it will drift from the framework
   and break later.

---

## Step 4 — Check the skill definition

The framework's validator checks that the frontmatter is complete, the
placeholders are used, the links work, and the capability tag is present. Run
it before you write evals:

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

Fix every warning before you move on. The most common first-time problems:

- Missing `when_to_use` — the agent cannot pick your skill without it.
- No `capability:` tag — the taxonomy-coverage check fails.
- A real project name in the body — replace it with a placeholder.
- A broken link — check that every `[text](path)` points to a real file.

---

## Step 5 — Write an eval suite

A skill without an eval suite is not finished (AGENTS.md § Reusable skills). The
eval suite is your evidence that the skill behaves well across the range of
inputs it will meet in real use.

The harness tests a skill one step at a time. For each step you want to cover,
you give some example inputs and say what a correct answer must look like. See
[`tools/skill-evals/README.md`](../../tools/skill-evals/README.md) for the full
method. The layout is:

```text
tools/skill-evals/evals/<name>/
  <step>/                       # one directory per skill step you test
    fixtures/
      step-config.json          # which skill file and which step this tests
      user-prompt-template.md   # the input the agent receives
      output-spec.md            # the exact output a correct answer must return
      case-1-.../               # one directory per example case
      case-2-.../
```

`step-config.json` ties the eval to your skill and the step heading it checks:

```json
{
  "skill_md": "skills/<name>/SKILL.md",
  "step_heading": "## Step 2 — Propose to the maintainer"
}
```

`output-spec.md` states what the agent must return (the harness checks the
output against it, usually as structured JSON). `user-prompt-template.md` is the
input, with `{placeholders}` filled in from each case.

Write at least a few cases: a normal input, an empty or trivial input, and one
attack case (an input designed to make the agent act without confirmation). The
attack case is your prompt-injection check.

Run the suite from the repository root. On its own the runner just assembles the
prompts; add `--cli` with your agent's command to actually run and grade them
(for example `claude -p`, `llm`, or `ollama run …`):

```bash
# assemble the cases, no model call
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/<name>/

# run and grade with your agent's CLI
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "<agent-command>" \
    tools/skill-evals/evals/<name>/
```

See the [eval-driven-development](eval-driven-development.md) page for
a fuller worked example.

---

## Step 6 — Open a pull request

Before you open it:

```bash
# Final validation pass
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate

# Confirm evals still pass (add --cli with your agent's command to grade)
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "<agent-command>" \
    tools/skill-evals/evals/<name>/
```

Both must be clean. Then commit and open a PR against the default branch of
`<framework>`. The PR description should answer:

- What use case does this skill handle?
- What fixtures did you write, and what does each one cover?
- Is there anything the reviewer should look at closely in the skill body?

A reviewer will read the skill, run the evals, and check the injection-defence
steps. The review goes faster when the PR description points the reviewer at the
interesting decisions.

---

## After merge: keeping your skill current

Skills drift over time. The agent's behaviour changes as the model behind it
updates; the project's process changes as people come and go; the framework's
conventions change too.

When you notice drift:

1. Update the skill body to match the behaviour you now want.
2. Add a fixture that captures the failure you saw.
3. Run the eval suite again.
4. Open a PR.

There is no separate "maintenance" step. The eval suite is the living
definition of "correct" for your skill. Keeping it green is keeping the skill
healthy.

---

## Common first-time mistakes

**Writing a skill that acts instead of proposing.**
Every action visible outside the session must be confirmed first. If your
skill's last step is "post the comment", add a step before it: "Draft the
comment and propose it to the maintainer. Wait for confirmation."

**Writing in a project name.**
`<tracker>` and `<upstream>` are the placeholders. If you catch yourself
writing `apache/airflow`, that is a mistake to fix.

**Writing only one eval fixture.**
A single normal-case fixture is not a suite. At least add an empty-input case
and an attack case. The attack fixture is often the most valuable one: it is
the one that catches prompt-injection problems.

**Skipping the validator before opening the PR.**
CI runs the same validator. Running it yourself first saves a round of
back-and-forth.

**Writing a skill body that is too long.**
If your skill has more than eight steps, it is probably doing two jobs. Split
it. Two small skills you can test on their own are more reliable than one large
skill you cannot.

---

## Where to go next

This is **step 4** in the [learning progression](README.md). The natural next
step is to make its behaviour testable:

- **[Eval-driven development](eval-driven-development.md)** — step 5: how to judge
  output that can vary, with worked examples from real Magpie skills. Your skill
  is not finished until it has an eval suite, so this is the immediate next read.
- **[Agentic and autonomous work](agentic-work.md)** — step 6: once a skill is
  written and tested, this is how you let it run without watching every step.

Supporting references for skill-writing:

- **[magpie-write-skill](../../skills/write-skill/SKILL.md)** —
  the full authoring reference, with the security checklist and packaging
  details. Run it with `/write-skill` once you are ready for the complete
  walk-through.
- **[Pattern catalogue](pattern-catalogue.md)** — ready-to-copy skill, prompt,
  and tool-use patterns.
- **[Tutorials](tutorials.md)** — a hands-on lab that puts steps 4 and 5 into
  practice end to end.
- **[CONTRIBUTING.md](../../CONTRIBUTING.md)** — the framework's contribution
  process, PR conventions, and review expectations.
