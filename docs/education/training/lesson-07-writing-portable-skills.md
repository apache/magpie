<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Lesson 7 — Writing portable skills](#lesson-7--writing-portable-skills)
  - [Learning objectives](#learning-objectives)
  - [Prerequisite knowledge](#prerequisite-knowledge)
  - [Before the lesson](#before-the-lesson)
  - [Exercises](#exercises)
    - [Exercise 1 — Spot the portability problems](#exercise-1--spot-the-portability-problems)
    - [Exercise 2 — Apply the placeholder convention](#exercise-2--apply-the-placeholder-convention)
    - [Exercise 3 — Replace a vendor dependency with a capability floor](#exercise-3--replace-a-vendor-dependency-with-a-capability-floor)
    - [Exercise 4 — Move a hardcoded value into adopter config](#exercise-4--move-a-hardcoded-value-into-adopter-config)
    - [Exercise 5 — Make the harness-dependent steps portable](#exercise-5--make-the-harness-dependent-steps-portable)
  - [Self-check](#self-check)
  - [Summary](#summary)
  - [Next](#next)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Lesson 7 — Writing portable skills

**Source page:** [Writing portable skills](../portable-skills.md)
**Estimated time:** 35 minutes (20 min reading + 15 min exercises and self-check)
**Lesson in sequence:** 7 of 11

---

## Learning objectives

By the end of this lesson you will be able to:

1. **Identify** the three classes of non-portable element in a skill step
   (project-specific name, vendor/model name, harness-specific command) and
   name which portability axis each violates.
2. **Apply** the four standard placeholders (`<PROJECT>`, `<upstream>`,
   `<tracker>`, `<security-list>`) correctly, knowing when to use each and
   when a value belongs in adopter config instead.
3. **Rewrite** a skill step that hardcodes a project name or issue-tracker URL
   so that it reads the value from `<project-config>/project.md` instead.
4. **Convert** a vendor-named step ("Ask Claude to…") to a capability-floor
   statement, and explain why the floor form is correct even when the task is
   genuinely complex.
5. **Classify** a harness-specific command in a skill step, replace it with a
   harness-neutral equivalent, and state when a harness-specific limit is
   acceptable to ship.

---

## Prerequisite knowledge

**Lesson 5 — Writing safe skills.** The injection-resistance and
draft-before-post patterns from that lesson appear in the before-and-after
example in the source page. You should be comfortable naming boundaries and
treating issue-body text as data before applying the portability rewrites here.

**Lesson 6 — Debugging a skill.** The output-contract and step-splitting
techniques from lesson 6 interact with portability: a step that is complex
enough to require a named vendor model is often a step that should be split,
not specialised.

---

## Before the lesson

Read the source page **[Writing portable skills](../portable-skills.md)** from
start to finish. Pay particular attention to:

- **The two portability axes** — project-agnostic and model-neutral are
  independent; understand the difference before the exercises.
- **The four placeholders** — their names, what each stands for, and the table
  of example values. The exercises will ask you to choose the right one.
- **Pattern 2 — Read from adopter config** — including the model step that
  names the keys to extract and what to do when a key is missing.
- **Pattern 4 — Capability floor, not a vendor** — the table of "instead of
  this / write this" substitutions.
- **The before-and-after example** — trace each of the three changes and
  match them to the pattern that justifies them.
- **Check your understanding** at the end of the source page — answer those
  four questions from memory before coming back here.

---

## Exercises

Work through these alone or in pairs. Each exercise takes about two to three
minutes. No live system is needed; use the source page as a reference.

### Exercise 1 — Spot the portability problems

Each skill step below has one or more portability problems. For each step,
list:

- The non-portable element (quote the exact phrase).
- Which axis it violates (project-agnostic, model-neutral, or both).
- The pattern number from the source page that fixes it.

> **Step A.**
> ```text
> Fetch the issue body from the apache/kafka repository:
>   gh issue view NNN --repo apache/kafka --json body
> ```

> **Step B.**
> ```text
> Ask GPT-4o to read the issue body and decide: is this a bug, a feature
> request, or a question? Output one of the three labels.
> ```

> **Step C.**
> ```text
> In Claude Code, press Ctrl+K and type /magpie-issue:triage to start the
> skill. You will see the output in the conversation panel on the right.
> ```

> **Step D.**
> ```text
> Capture a screenshot of the rendered dashboard using the harness's
> built-in screen-capture tool, and attach it to the issue.
> ```

After labelling each, identify which three can be fixed by editing only the
skill body, and which one cannot: it depends on a tool that exists in only one
harness, so it calls for a documented limit rather than a rewrite.

### Exercise 2 — Apply the placeholder convention

The following steps contain real names that should be placeholders. Rewrite
each step using the correct placeholder from the table in the source page
(Pattern 1). Choose from `<PROJECT>`, `<upstream>`, `<tracker>`, and
`<security-list>`.

> **Step A.**
> ```text
> Post the following comment on the apache/airflow GitHub Issues thread:
> ```

> **Step B.**
> ```text
> If the issue concerns a security vulnerability, forward the full body
> to security@apache.org before proceeding.
> ```

> **Step C.**
> ```text
> Summarise the open items for the Airflow project and list them under
> the heading "Airflow open items".
> ```

For step C, think about whether `<PROJECT>` alone is enough, or whether the
summarised output should itself avoid a hardcoded name.

### Exercise 3 — Replace a vendor dependency with a capability floor

A colleague has written the step below for a skill that classifies issue bodies
using a structured JSON output. Rewrite the step to remove the vendor
dependency, following Pattern 4. Your rewrite must:

- Remove the vendor name.
- Name the capability the step actually needs (if any annotation is needed at
  all).
- Keep the instruction clear enough for any capable model to follow.

> ```text
> Step 3 — Classify the issue
>
> Use Claude Sonnet to read the issue body. Because this step requires
> multi-step reasoning and structured output, it will not work reliably on a
> smaller model. Return a JSON object with fields `label` (one of BUG /
> FEATURE-REQUEST / QUESTION) and `reason` (one sentence).
> ```

After rewriting, answer: does removing the vendor name mean the step will
always work on any model? If not, what is the honest statement to make?

### Exercise 4 — Move a hardcoded value into adopter config

The step below hardcodes a label name that differs from project to project.
Rewrite it to use Pattern 2 (read from adopter config). Your rewrite should:

- Add a preparatory step (or amend an existing one) that reads the required
  key from `<project-config>/project.md`.
- Replace the hardcoded label name with the config-read variable.
- Include the "stop if missing" guard.

> ```text
> Step 4 — Apply the triage label
>
> Add the label `needs-triage` to the issue:
>   gh issue edit NNN --repo <upstream> --add-label needs-triage
> ```

The label name (`needs-triage`) varies across projects. Write the config-read
step that extracts the project's actual triage-label name, then use it in the
`gh issue edit` command.

### Exercise 5 — Make the harness-dependent steps portable

Return to Step C and Step D from Exercise 1.

- Rewrite **Step C** so it runs on any harness: drop the harness-specific
  command and interface reference, and use a harness-neutral invocation and
  output instead (Pattern 5).
- **Step D** relies on a tool that exists in only one harness, so it cannot be
  made fully neutral. Describe how to ship it responsibly (Pattern 6): where in
  the skill you record the dependency, and the condition under which shipping
  with that limit is acceptable.

Then state, in one sentence, the difference between Step C and Step D that
decides whether a harness problem is a body rewrite or a documented limit.

---

## Self-check

Answer each question in a sentence or two before moving to lesson 8. If you
cannot answer one, re-read the matching section of the source page.

**Q1.** A skill step reads: *"Post this comment to the apache/kafka issue
tracker."* Name the portability problem, name the correct placeholder, and
write the corrected step.

<details>
<summary>Answer</summary>

The problem is a **project-specific name** — `apache/kafka` is hardcoded
instead of using a placeholder. This violates the project-agnostic axis
(PRINCIPLE 12). The step names the *issue tracker*, so the correct placeholder
is `<tracker>`, and the corrected step is: *"Post this comment on
`<tracker>#NNN`."* (This mirrors the Pattern 1 example on the source page.)
The related placeholder `<upstream>` stands for the repository identifier
itself (`org/repo`): use `<upstream>` when a step names the repo and
`<tracker>` when it names the issue tracker. Either way, no real project or
repository name should appear in the skill body.

</details>

---

**Q2.** A colleague argues that a step needs Claude specifically because it
"requires advanced reasoning". Is this a valid reason to write "Use Claude" in
the skill body? What would you write instead, and why?

<details>
<summary>Answer</summary>

It is **not** a valid reason to write a vendor name in the skill body. A
vendor name is a dependency on something outside your control — models change,
are deprecated, or are replaced by better ones. The honest statement is a
capability floor: for example, *"This step requires tool-calling capability
and multi-step reasoning."* If the step consistently fails on a wide range of
models, that is a signal to split the step (lesson 6, step-splitting technique)
rather than to lock in a vendor. In most cases, no annotation is needed at all:
the user's configured model runs the step.

</details>

---

**Q3.** A skill calls `gh`, `uv`, and `python` in its tool steps. Is this
skill harness-neutral? What property makes these tools portable?

<details>
<summary>Answer</summary>

Yes, a skill built on `gh`, `uv`, and `python` is **harness-neutral**. These
are harness-neutral tools (Pattern 6): they behave the same way regardless of
which agent host — Claude Code, OpenCode, Cursor, or any other — is running
the skill. Portability comes from the fact that the tools are external CLI
programs with stable interfaces, not APIs tied to a specific agent host. A
skill that relies only on such tools can be adopted by any project on any
harness without modification.

</details>

---

**Q4.** A skill hard-codes the label name `kind:bug` in a `gh issue edit`
command. When would this be acceptable, and when must it be moved to adopter
config?

<details>
<summary>Answer</summary>

Hardcoding `kind:bug` is only acceptable if the skill is written for exactly
one project and will never be shared. As soon as the skill is intended to work
across projects — which is the normal case for any skill in the framework's
`skills/` directory — the label name must be moved to adopter config (Pattern
2). Different projects use different label conventions (`bug`, `type: bug`,
`kind:bug`, `defect`, etc.). The skill body should read the label name from
`<project-config>/project.md` and stop with a clear message if the key is
missing, rather than silently applying the wrong label.

</details>

---

**Q5.** You have applied all six patterns and the validator passes. Is the
skill now portable? What else would confirm it?

<details>
<summary>Answer</summary>

Passing the validator and applying the six patterns is a strong signal, but
not final proof. The validator checks for known patterns (placeholder usage,
harness command references, vendor names); it cannot check logic. The
remaining confirmation step is running the skill's **eval suite against two
different models** (lesson 8, eval-driven development). If the same eval cases
pass on both models, you have evidence of model-neutrality in practice.
Similarly, running the skill in a second harness (even a minimal one) confirms
harness-neutrality. The six patterns are authoring discipline; evals are the
evidence.

</details>

---

## Summary

Portability is an authoring discipline, not a post-hoc fix. Two axes matter:
project-agnostic (no real project names, no hardcoded config values) and
model-neutral (no vendor names, no harness commands). Six patterns cover almost
every non-portable element a skill can contain: substitute placeholders for
project names (Pattern 1), read variable values from adopter config (Pattern
2), run the validator before opening a pull request (Pattern 3), name capability
floors instead of vendors (Pattern 4), write steps that any harness can execute
(Pattern 5), and prefer harness-neutral tools (Pattern 6). A skill that
satisfies all six patterns works for any project that adopts the framework and
for any model backend, present or future.

---

## Next

**[Eval-driven development](../eval-driven-development.md)** — step 8 of the
learning progression (lesson 8 of this module is not yet packaged; follow the
source page directly until it lands). Once a skill is portable, eval-driven
development is how you *prove* that it works — including across the models and
harnesses you just wrote it to support.

---

## Licence

Apache License 2.0 (PRINCIPLE 17). Pages written with help from AI carry a
`Generated-by:` note in their commit message following ASF Generative Tooling
Guidance.
