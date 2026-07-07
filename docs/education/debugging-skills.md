<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Debugging a skill](#debugging-a-skill)
  - [Words used on this page](#words-used-on-this-page)
  - [The diagnostic loop](#the-diagnostic-loop)
  - [Reading the audit log](#reading-the-audit-log)
  - [Isolating the problem type](#isolating-the-problem-type)
    - [Prompt problems](#prompt-problems)
    - [Tool problems](#tool-problems)
    - [Model-capability problems](#model-capability-problems)
  - [Narrowing a flaky failure](#narrowing-a-flaky-failure)
  - [The debug workflow from end to end](#the-debug-workflow-from-end-to-end)
  - [Check your understanding](#check-your-understanding)
  - [How this connects to the other guides](#how-this-connects-to-the-other-guides)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Debugging a skill

This is **step 6** in the [learning progression](README.md). You wrote a skill
in step 4, applied its safety patterns in step 5, and now the skill is running —
but something is wrong. The output is not quite right, or it is right sometimes
and not others. This page is the diagnostic path from "my skill did the wrong
thing" to a fixed, verifiable skill.

Debugging an agentic skill is not the same as debugging normal code, because
the output is probabilistic — the same input can produce slightly different
results each time. The techniques here account for that.

## Words used on this page

New to some of these words? Here is what they mean here. The
[landing page](README.md) has a fuller list.

- **Audit log**: the record the harness writes as the skill runs — the prompts
  sent, the tools called, and the model's responses. In a live agent session,
  this is the transcript shown in the session view; in `tools/skill-evals/`, it
  is the runner's output.
- **Eval case (fixture)**: one example input, together with a description of
  what a good answer must contain or avoid. See
  [Eval-driven development](eval-driven-development.md).
- **Flaky**: a test or eval case that sometimes passes and sometimes fails with
  no change to the input or skill. Flakiness is normal in probabilistic systems;
  the goal is to understand *why* and reduce it, not to eliminate all variation.
- **Prompt problem**: the issue is in what the skill *says to the model* — the
  wording, structure, or ordering of the instructions.
- **Tool problem**: the issue is in how the skill *calls an external system* —
  a wrong argument, a missing pre-flight check, or an unexpected API response.
- **Model-capability problem**: the task is at the edge of what the model can
  reliably do — the instructions are fine, but the model cannot execute them
  well enough.
- **Temperature**: a setting that controls how much variation the model
  introduces. Higher temperature means more variation; lower means more
  consistent (but still not deterministic).

---

## The diagnostic loop

When a skill produces wrong output, work through these questions in order. Each
one narrows the problem to a smaller surface before you look at code.

1. **Is this failure reproducible?** Run the failing case several times with the
   same input. If it passes sometimes and fails others, you have a flaky
   failure. If it always fails, you have a deterministic bug.
2. **Where in the skill did it go wrong?** Read the audit log to find the step
   where the output first diverged from what you expected.
3. **Is the problem in the prompt, the tool, or the model?** Each has a
   different fix. See the three sections below.

---

## Reading the audit log

The audit log is the most important debugging tool you have. It shows exactly
what the model received and what it returned, at every step. You do not need to
guess what happened — it is recorded.

**In the eval harness** (`tools/skill-evals/`), run the case with the `--cli`
flag *and* `--verbose`. Without `--verbose`, `--cli` mode reports only pass/fail
per case; adding it makes the runner print each prompt and the model's raw
stdout, which is the audit log you want. (The default print mode, with no
`--cli`, also prints the assembled prompts.)

**In a live session** (any interactive agent harness), the session view
shows the model's reasoning and tool calls. Look for:

- The exact text the model received at the failing step. Does it match what you
  intended to send?
- The tool calls the model made. Were they correct? Did they return what you
  expected?
- The model's response at the failing step. Is it in the right shape? Does it
  miss a required field?

If the prompt text the model received is not what you intended, the problem is
in how the skill is structured — likely a prompt problem. If the prompt is
correct but the tool call failed, it is a tool problem. If both are correct and
the model's response is still wrong, it may be a model-capability problem.

---

## Isolating the problem type

### Prompt problems

A prompt problem is the most common. Signs:

- The model does the right thing in the wrong order.
- The model misses a field or skips a check you wrote into the step.
- The model answers a different question than the one you asked.
- Rephrasing the step in a test session changes the output.

**How to fix:** Read the step instructions as if you were the model, not the
author. Would a careful reader who knew nothing else do what you intended?
If not, rewrite for clarity. Common fixes:

- Make the boundary explicit. If a step both reads an issue and classifies it,
  split it into two steps — reading, then classifying. (See
  [Writing safe skills](writing-safe-skills.md), Pattern 1.)
- Make the output contract explicit. If the step should return a JSON object,
  say so: "Return a JSON object with fields `label` (string) and `reason`
  (one sentence)."
- Add a negative example. If the model keeps confusing two cases, write one
  sentence describing what the wrong answer looks like and why it is wrong.

After the fix, write an eval case that would have caught the original bug and
confirm it now passes.

### Tool problems

A tool problem is in the interface between the skill and an external system.
Signs:

- The model's reasoning is correct but the tool call returns an error.
- The tool call succeeds but returns data in a shape the model did not handle.
- The skill works in a live session but fails in the eval harness (where the
  external system is mocked or absent).

**How to fix:** Check the tool call in the audit log. Verify:

- The arguments match what the tool expects (look at the tool's own
  documentation or `--help` output).
- The pre-flight step checked that the tool is available and authorised. If
  it did not, add a pre-flight check.
- The skill handles the tool's error responses. If a `gh issue view` call
  returns a 404, what should the skill do? Write that into the step.

For eval fixtures, tool responses are usually mocked. If the mock does not
match what the real tool returns, the fixture is wrong — update it.

### Model-capability problems

A model-capability problem is harder to fix, because the solution is not
a rewrite — it is a different approach. Signs:

- Simplifying the prompt or splitting the step does not help.
- The model reasons correctly about the task in isolation but fails when
  combined with the rest of the skill.
- The failure rate stays high regardless of phrasing.

**How to investigate:**

1. Isolate the failing step: write a minimal prompt in a test session that
   contains only that step's input and instructions. Does it still fail?
2. If yes, the task is at the model's capability edge. Consider:
   - Breaking the step into smaller sub-steps, each simpler.
   - Using a more capable model for the failing step (see
     [Choosing models](choosing-models.md)).
   - Providing a worked example in the step instructions (few-shot prompting).
3. If the isolated step passes but it fails in the full skill, the problem is
   context contamination — an earlier step's output is confusing this one.
   Check whether earlier steps leave ambiguous state in the conversation.

---

## Narrowing a flaky failure

Flakiness — a case that passes sometimes and fails others — is expected in
probabilistic systems. It becomes a problem only when the failure rate is high
enough to matter, or when it hides a real defect. Here is how to tell the
difference.

**Step 1 — Measure the failure rate.** Run the failing case at least five
times. (Ten is better for a case you intend to keep.) Note the pass rate. A
pass rate above 90 % is usually acceptable for a smoke check; a pass rate
below 70 % is worth fixing regardless.

**Step 2 — Check whether temperature is the cause.** If the eval runner
supports a temperature setting, lower it. If the failure rate drops
significantly, the flakiness is model-variation, not a defect. In that
case the fix is usually a tighter output contract (see the prompt problem
section above).

**Step 3 — Check whether the fixture is underspecified.** If the output spec
says "return a short summary" but does not define how short, reasonable answers
vary widely. Tighten the spec: "return a summary of one to three sentences." A
more specific fixture is more stable.

**Step 4 — Check whether the model is being asked to do too much at once.**
A step that reads, classifies, and summarises in a single call will be less
consistent than three separate steps. Split it.

**Step 5 — Tag stable cases as `local-smoke`.** Once a case passes reliably
on both a frontier and a local model at a fixed temperature, it is a good
candidate for the `local-smoke` tag. See the `case-meta.json` format in
`tools/skill-evals/README.md`.

---

## The debug workflow from end to end

Here is the full workflow as a checklist.

1. **Observe.** Run the failing input several times and read the audit log.
   Note where the output first diverges from what you expected.
2. **Classify.** Is this a prompt problem, a tool problem, or a
   model-capability problem? Use the signs above to decide.
3. **Isolate.** Reproduce the problem in the smallest context you can — ideally
   a single eval case, or a one-step test session with no surrounding skill.
4. **Fix.** Apply the relevant fix from the section above.
5. **Add a regression case.** Write an eval fixture that would have caught the
   original bug. This stops it coming back and documents what the correct
   behaviour is.
6. **Run the full suite.** Confirm the new case passes and the existing cases
   still pass. Fix any regressions before continuing.

---

## Check your understanding

1. A skill step is supposed to return a JSON object with two fields. In the
   audit log you see that the model returned a plain-text sentence instead.
   What type of problem is this, and what is the first thing you would fix?

2. A skill works correctly in a live session but always fails in the eval
   harness. The audit log shows the tool call returns a 404 error. What is
   the likely cause, and where would you look first?

3. An eval case passes seven times out of ten. The output spec says "return a
   label". How would you approach fixing this flakiness?

4. After splitting a complex step into two simpler steps, the failure rate
   drops from 40 % to 5 %. What does this tell you about the original
   problem?

---

## How this connects to the other guides

- **[Writing safe skills](writing-safe-skills.md)** is step 5, the page before
  this one. The injection-flag idiom and the draft-before-post pattern both
  appear in audit logs when they fire — knowing them makes the log easier to
  read.
- **[Writing portable skills](portable-skills.md)** is step 7, the page after
  this one. Once a skill runs correctly, that page makes it work for any project
  and any model, not only the one you debugged it on.
- **[Eval-driven development](eval-driven-development.md)** is step 8. That page
  covers how to *design* an eval suite; this page covers the debug loop you run
  when one fails. They pair: the evals surface the bug; this page fixes it.
- **[Choosing models](choosing-models.md)** is step 3. When a failure turns out
  to be a model-capability problem, that page is where to look for guidance on
  which model tier to try next.
- **[Agentic and autonomous work](agentic-work.md)** is step 9. When no one is
  watching every step, flakiness and silent tool failures become much harder to
  catch. The debugging habits here are the foundation for safe autonomy.
- **[tools/skill-evals/README.md](../../tools/skill-evals/README.md)** — the
  harness reference: runner flags, grading modes, the `case-meta.json` format,
  and the `local-smoke` tag.
- **[Pattern catalogue](pattern-catalogue.md)** — the patterns named in this
  page (injection-flag, draft-before-post, output-contract) are collected there
  as copy-ready blocks.

---

## Licence

Everything in `docs/education/` is under the Apache License 2.0 (PRINCIPLE 17).
Pages written with help from AI carry a `Generated-by:` note in their commit
message, following ASF Generative Tooling Guidance.
