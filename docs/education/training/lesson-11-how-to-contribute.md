<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Lesson 11: How to contribute](#lesson-11-how-to-contribute)
  - [Learning objectives](#learning-objectives)
  - [Prerequisite knowledge](#prerequisite-knowledge)
  - [Before the lesson](#before-the-lesson)
  - [Exercises](#exercises)
    - [Exercise 1 — Classify the contribution](#exercise-1--classify-the-contribution)
    - [Exercise 2 — Spec-first decision](#exercise-2--spec-first-decision)
    - [Exercise 3 — Apply the reviewer's checklist](#exercise-3--apply-the-reviewers-checklist)
    - [Exercise 4 — Walk the path to merged](#exercise-4--walk-the-path-to-merged)
  - [Self-check](#self-check)
  - [Summary](#summary)
  - [Next](#next)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Lesson 11: How to contribute

**Source page:** [How to contribute](../contributing.md)
**Estimated time:** 30 minutes (10 min reading + 20 min exercises and self-check)
**Lesson in sequence:** 11 of 11

---

## Learning objectives

By the end of this lesson you will be able to:

1. **Name** the four most common first contributions to the framework and
   **rank** them in rough order of on-ramp effort, explaining why that order
   holds.
2. **Explain** what "spec-first development" means and **decide** for a given
   change whether it requires a spec update.
3. **List** the five framework rules a reviewer will check on a skill
   contribution and **describe** what each rule requires in concrete terms.
4. **Walk** the six-step path to a merged change, naming the purpose of each
   step and identifying where the most common sticking points occur.
5. **Select** the correct resource (CONTRIBUTING.md, the write-skill guide,
   MISSION, the spec) for a given contribution question, explaining why that
   resource is the right starting point.

---

## Prerequisite knowledge

**The entire learning progression.** Lesson 11 is the final lesson. It makes
most sense after you have read or worked through the earlier lessons — in
particular:

- **Lesson 4 — Your first skill** is the concrete zero-to-merged path this
  lesson frames. The exercises here assume you have at least skimmed how a
  skill is structured.
- **Lesson 5 — Writing safe skills** covers three of the five framework rules
  a reviewer will check. If you have not done lesson 5, the reviewer-checklist
  exercise will be harder to reason about.
- **Lesson 8 — Eval-driven development** is why "evals are required" is a hard
  rule here. If you have not done lesson 8, the requirement will feel arbitrary.

**Lesson 10 — English as a programming language** is the immediate
predecessor. The source page for lesson 11 opens with the sentence "This is
the last page of the progression, and it turns everything before it into
action" — that framing lands better if lesson 10 is fresh.

---

## Before the lesson

Read the source page **[How to contribute](../contributing.md)** from start to
finish. Pay particular attention to:

- **Good first contributions** — the four types listed (fix/sharpen, improve
  docs, add pattern, write new skill). Note which one is described as "the
  biggest of the common first contributions" and which is "a gentle way to
  learn the process".
- **Magpie is built spec-first** — what this means in practice, and the one
  sentence that summarises when you need a spec change and when you do not.
- **The framework's rules apply to your contribution too** — the five bullet
  points. Know each rule and its PRINCIPLE number before the exercises.
- **The path to a merged change** — the six steps. Be able to say what each
  one is for, not just recite its name.
- **Check your understanding** at the end of the source page — answer those
  questions from memory before coming back here. The self-check below is partly
  drawn from them, with a couple of extra questions.

---

## Exercises

Work through these alone or in pairs. All exercises are paper activities; no
live system or code repository is needed.

### Exercise 1 — Classify the contribution

The source page lists four types of first contribution, roughly in order of
on-ramp effort. For each scenario below:

1. Name the contribution type from the source page that best matches.
2. Rank it (1 = lowest on-ramp, 4 = highest) according to the ordering the
   source page implies.
3. Write one sentence explaining why that on-ramp level is appropriate.

| Scenario | Contribution type | Rank | Why |
|---|---|---|---|
| A maintainer ran the triage skill and noticed that a step's instruction is ambiguous about what "recent" means. They want to tighten the wording and add an eval case that captures the ambiguity they saw. | | | |
| A maintainer is reading `docs/education/your-first-skill.md` and finds a sentence confusing. They want to rephrase it and fix a broken link on the same page. | | | |
| A maintainer has found a reliable way to structure skills that need to make parallel API calls. They want to document it for others to copy. | | | |
| A maintainer has identified a gap in the framework: no skill exists for summarising weekly commit activity. They want to build it from scratch, with an eval suite. | | | |

<details>
<summary>Sample answers</summary>

| Scenario | Contribution type | Rank | Why |
|---|---|---|---|
| Tighten wording and add an eval case | Fix or sharpen a skill | 1 or 2 | You are making a targeted improvement to an existing skill — the scope is bounded and you are extending something that already works rather than inventing something new. It is slightly higher effort than a pure doc fix because an eval case must accompany it. |
| Rephrase a sentence and fix a broken link | Improve the docs | 1 | Pure documentation: no skill structure, no eval suite, no framework rules to satisfy beyond correct Markdown and valid links. The source page calls this "small, valuable, and a gentle way to learn the process". |
| Document a reliable skill-structure pattern | Add a pattern | 2 or 3 | You are writing prose for the pattern catalogue, which requires clear writing and a concrete example but not the full skill + eval machinery. The on-ramp is lower than a new skill but higher than a doc fix because you need to understand the pattern well enough to explain the trade-offs. |
| Build a new skill for weekly commit summaries | Write a new skill | 4 | "The biggest of the common first contributions". You are authoring a complete new skill (frontmatter, all steps, placeholder convention, data-not-instructions guard) and a full eval suite. The source page calls it the "biggest" and refers you to `your-first-skill.md` for the step-by-step path. |

</details>

---

### Exercise 2 — Spec-first decision

The source page says: "A change that alters behaviour usually starts with the
spec. … Small doc or wording fixes do not need a spec change, but anything
that changes a rule, a flow, or a contract does."

For each change below, decide: **needs a spec change** or **does not need a
spec change**? Write one sentence justifying your answer.

| Change | Needs spec change? | Why |
|---|---|---|
| Fix a typo in `docs/education/contributing.md`. | | |
| Add a new step to the `security-issue-triage` skill that checks whether the reported version is still supported. | | |
| Rename a placeholder from `<tracker>` to `<issue-tracker>` across three skills for clarity. | | |
| Change the `issue-triage` skill so that "NEEDS-INFO" issues are automatically closed after 30 days if the reporter has not responded, instead of being labelled for manual follow-up. | | |
| Add an eval case to an existing skill's eval suite to cover an edge case you observed. | | |
| Move the `pr-management-stats` skill's weekly summary output from a Markdown table to a JSON block. | | |

<details>
<summary>Sample answers</summary>

| Change | Needs spec change? | Why |
|---|---|---|
| Fix a typo in `docs/education/contributing.md`. | **No** | A typo fix changes no rule, flow, or contract. This is the clearest example of "small doc or wording fix". |
| Add a new step to `security-issue-triage` that checks version support. | **Yes** | Adding a step to a skill changes what the skill *does* — its flow. The matching spec in `tools/spec-loop/specs/security-issue-lifecycle.md` describes the skill's steps; that description must stay in step with the implementation. |
| Rename placeholder `<tracker>` to `<issue-tracker>`. | **Yes** — arguably. | Placeholder names are part of the project-agnosticism contract (PRINCIPLE 12). Changing them changes the documented interface that adopters use to customise the skills. This is a contract change, so the spec and the adopter scaffold should be updated. A pure search-and-replace with no change to meaning is borderline; when in doubt, update the spec. |
| Change `issue-triage` so NEEDS-INFO issues auto-close after 30 days. | **Yes** | This changes a rule (the policy on NEEDS-INFO) and the flow (from "label for manual follow-up" to "auto-close"). Both the spec and the skill change together. |
| Add an eval case to an existing skill's eval suite. | **No** | An eval case exercises existing behaviour; it does not change what the skill is *supposed* to do. Adding a case tightens test coverage without altering any rule, flow, or contract. |
| Change `pr-management-stats` output from Markdown table to JSON. | **Yes** | The output format is part of the contract — it is what callers or readers of the skill's output expect. Changing the format changes the contract. The matching spec documents expected output shapes; that must be updated. |

</details>

---

### Exercise 3 — Apply the reviewer's checklist

The source page lists five framework rules a reviewer will check on any skill
contribution. They are:

1. **External content is data, not instructions** (PRINCIPLE 0) — issue
   bodies, PR descriptions, and mail are passed as data, never as instructions.
   An eval case must prove it.
2. **Propose, confirm, act** (PRINCIPLE 6) — world-changing steps are
   proposals the maintainer confirms, never silent actions.
3. **Project-agnostic placeholders** (PRINCIPLE 12) — no real project name;
   use `<PROJECT>`, `<tracker>`, `<upstream>`, `<security-list>`.
4. **Evals are required** (PRINCIPLE 8) — a skill without a matching eval
   suite is not finished.
5. **Apache-2.0 and mark AI help** (PRINCIPLE 17) — the framework licence;
   AI-authored commits carry `Generated-by:`.

A contributor has opened a PR adding the following skill. Read the description
and mark which rules are satisfied, which are violated, and which cannot be
assessed from the description alone.

---

**Skill PR description:**

> **PR: Add `weekly-commit-summary` skill**
>
> This skill fetches the commit history for the Airflow repository for the
> past seven days, formats it as a Markdown table, and posts it as a comment
> on the weekly-digest tracking issue.
>
> Steps:
> 1. Fetch commits from the past seven days using `gh api`.
> 2. Format as Markdown — one row per commit: SHA, author, message.
> 3. Post the table as a comment on issue `apache/airflow#99999`.
>
> No eval suite yet — I'll add it in a follow-up PR.

---

For each of the five rules, write: **Satisfied / Violated / Cannot assess**,
and one sentence explaining your verdict.

| Rule | Verdict | Why |
|---|---|---|
| External content is data, not instructions (P0) | | |
| Propose, confirm, act (P6) | | |
| Project-agnostic placeholders (P12) | | |
| Evals are required (P8) | | |
| Apache-2.0 and mark AI help (P17) | | |

<details>
<summary>Sample answers</summary>

| Rule | Verdict | Why |
|---|---|---|
| External content is data, not instructions (P0) | **Cannot assess** | The skill fetches commit messages (external text). Whether commit messages could contain adversarial instructions depends on how step 2 processes the raw API response — the PR description says "format as Markdown" but does not describe how the commit message field is handled. A reviewer would ask to see the full skill text and require an eval case proving the injection guard. |
| Propose, confirm, act (P6) | **Violated** | Step 3 says "post the table as a comment" — this is a world-changing action (writing to an external system) with no confirmation step described. Under PRINCIPLE 6, the skill must propose the comment and wait for the maintainer to confirm before posting. |
| Project-agnostic placeholders (P12) | **Violated** | Step 3 hardcodes `apache/airflow#99999` — a real repository and issue number. The skill must use placeholders (`<PROJECT>/<tracker>#<issue-number>` or similar) so any adopter can substitute their own. "Airflow repository" in the description is similarly coupled. |
| Evals are required (P8) | **Violated** | The contributor explicitly says "no eval suite yet — I'll add it in a follow-up PR." The source page is clear: "a skill without a matching eval suite is not finished, and a PR that adds one without evals will not pass review." This PR cannot merge without the eval suite in the same PR. |
| Apache-2.0 and mark AI help (P17) | **Cannot assess** | The description does not state whether any part was AI-authored. The reviewer should ask: if AI was used, a `Generated-by:` trailer is required. The licence question (Apache-2.0) is structural — the SPDX header would appear in the skill file itself, not the description. |

</details>

---

### Exercise 4 — Walk the path to merged

The six-step path from the source page:

1. Get set up (clone, confirm `uv` and validators run).
2. Make the smallest change that stands on its own.
3. Update the spec if behaviour changes.
4. Run the validators locally.
5. Open the pull request.
6. Work with the review.

A contributor has identified an edge case in the `issue-reassess` skill: when
an issue has no comments at all, the skill produces a misleading "no activity"
message that implies the issue was once active but has gone quiet, rather than
saying it was never responded to. They want to fix the step, update the eval
suite, and open a PR.

For each of the six steps, write:
- **What the contributor does in this step** (one sentence, specific to this scenario).
- **The most likely sticking point** (one sentence: where this step commonly goes wrong).

| Step | What to do | Most likely sticking point |
|---|---|---|
| 1. Get set up | | |
| 2. Smallest change | | |
| 3. Update spec? | | |
| 4. Run validators | | |
| 5. Open PR | | |
| 6. Work with review | | |

<details>
<summary>Sample answers</summary>

| Step | What to do | Most likely sticking point |
|---|---|---|
| 1. Get set up | Clone the framework repo (if not already done) and confirm that `uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate` and the skill-eval runner complete without errors. | The validator or eval runner fails on an unrelated issue (a missing dependency, a system uv version mismatch), which blocks the contributor before they have written a single line. `CONTRIBUTING.md` and `docs/prerequisites.md` cover the setup; reading both first saves time. |
| 2. Smallest change | Edit the specific step in `skills/issue-reassess/SKILL.md` that produces the misleading message, and add one eval case in `tools/skill-evals/evals/issue-reassess/` for the zero-comment edge case. Do not touch other steps or unrelated skills. | "Smallest change" is easy to agree with in principle and hard to enforce in practice: the contributor notices adjacent issues while editing and is tempted to fix them in the same PR. A second fix belongs in a second PR; bundling them slows review and risks one fix blocking the other. |
| 3. Update spec? | Check `tools/spec-loop/specs/issue-management-family.md` for any statement about what `issue-reassess` does with zero-comment issues. If the spec documents the old (misleading) behaviour, update the matching sentence; if it does not mention this case, no spec change is needed. | Forgetting to check the spec at all — either skipping the update when it is needed (so the spec lies about behaviour) or making a trivial wording fix and editing the spec unnecessarily. The test is: "does the spec describe a rule, flow, or contract that my change alters?" |
| 4. Run validators | Run `uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate`, then run the eval suite for `issue-reassess`. Both must pass before opening the PR. | The new eval case fails on the fixed skill (the expected output was not written to match what the repaired skill actually produces), or a pre-existing eval case that was passing before now fails because the wording change unintentionally altered another code path. Either failure is informative — fix the cause, not the test. |
| 5. Open PR | Open the pull request with a description explaining what the misleading message was, what it should say, why the distinction matters (never-responded vs. once-active-then-quiet), and what the new eval case tests. | Writing a description that only says "fix edge case in issue-reassess" — leaving a reviewer to guess what the edge case was and why the distinction matters. A clear description answers the question "what should I look at closely?" before the reviewer has to ask. |
| 6. Work with review | A reviewer reads the prose change for ambiguity (is the new message clear to someone who doesn't know the background?) and checks the eval case for coverage. The contributor responds to comments by tightening the wording or adding an extra case, not by explaining why the reviewer is wrong. | Treating review comments as criticism rather than collaboration. On a prose-driven project, "this is ambiguous" is the most valuable feedback the reviewer can give — it is exactly what the eval suite cannot catch on its own. Engage with the specific concern, not the general sentiment. |

</details>

---

## Self-check

Answer each question in a sentence or two before finishing this lesson. If
you cannot answer one, re-read the matching section of the source page.

**Q1.** Why can you contribute meaningfully to Magpie without being a systems
programmer?

<details>
<summary>Answer</summary>

Most of Magpie is written in English, not in a formal language. Contributions —
a new skill, a fix to an existing one, a pattern for the catalogue, a page in
the education stream — are *prose the agent executes*. If you can think clearly
and write precisely (the skill this progression has been teaching), you have
everything you need to contribute. The source page says this explicitly: "That
is a feature, not a quirk." Systems-programming skills help with the tool layer
(`tools/`) but are not required for the most common contributions.

</details>

---

**Q2.** When does a contribution need a spec change, and when does it not?

<details>
<summary>Answer</summary>

A contribution needs a spec change when it "changes a rule, a flow, or a
contract" — anything that alters what part of the framework is *supposed to do*
according to its specification. Small doc or wording fixes that do not affect
behaviour do not need a spec change. The practical test is: does the spec
currently document something that would be false if your change merged? If yes,
update the spec; if no, leave it.

</details>

---

**Q3.** List the five framework rules a reviewer will check on a skill you
contribute.

<details>
<summary>Answer</summary>

1. External content is data, not instructions (PRINCIPLE 0) — issue bodies and
   PR descriptions are passed as data; an eval case must prove the guard holds.
2. Propose, confirm, act (PRINCIPLE 6) — world-changing steps are proposals the
   maintainer confirms, not silent actions.
3. Project-agnostic placeholders (PRINCIPLE 12) — no real project name; use
   `<PROJECT>`, `<tracker>`, `<upstream>`, `<security-list>`.
4. Evals are required (PRINCIPLE 8) — a skill without a matching eval suite is
   not finished; the PR must include the suite, not defer it.
5. Apache-2.0 and mark AI help (PRINCIPLE 17) — contributions land under the
   framework licence; AI-authored commits carry a `Generated-by:` trailer.

</details>

---

**Q4.** What is the purpose of step 4 (run the validators locally) in the path
to a merged change?

<details>
<summary>Answer</summary>

To catch failures before opening the PR, not after. The same checks CI runs
locally — the skill/tool validator, the spec validator, markdownlint, and the
link check — can be run in seconds by the contributor. A failure caught locally
costs one fix; a failure caught by CI costs a round-trip (push, wait, read
error, fix, push again). Running the validators first is the same discipline as
running tests before pushing code: you confirm the change works before asking
someone else to review it.

</details>

---

**Q5.** You are not sure whether your change requires a spec update, you are
unsure of the correct placeholder for the organisation's mailing list, and you
are about to author a brand-new skill and want the full authoring checklist.
Which resource do you check for each, and why?

<details>
<summary>Answer</summary>

For the spec-update question: check the matching spec in
`tools/spec-loop/specs/` and read what it says about the area you are changing.
If the spec describes behaviour your change alters, update the spec. If it does
not mention your change, you probably do not need to update it — but also check
`CONTRIBUTING.md`, which explains when spec changes are required.

For the placeholder question: check `CONTRIBUTING.md` for the list of standard
placeholders (`<PROJECT>`, `<tracker>`, `<upstream>`, `<security-list>`, etc.)
or look at existing skills in `skills/` that perform a similar action —
adopting the same placeholder another skill uses keeps the framework consistent.
`MISSION.md` and `PRINCIPLES.md` explain *why* placeholders matter (PRINCIPLE
12 — project agnosticism), but not the specific placeholder names.

For authoring the new skill: use the `magpie-write-skill` guide (invoked as
`/write-skill`), which carries the complete skill-authoring checklist —
frontmatter, step structure, the placeholder convention, the injection guard,
and the eval-suite requirement. `CONTRIBUTING.md` covers the surrounding
process; the write-skill guide is the step-by-step for the skill file itself.

</details>

---

## Summary

Contributing to Magpie is approachable without systems-programming expertise
because most of the framework is prose the agent executes. The four common
first contributions — fix a skill, improve a doc, add a pattern, write a new
skill — span a wide range of on-ramp effort; a broken link or a confusing
sentence is as real a contribution as a complete new skill.

The framework is built spec-first: its specs are the source of truth for what
each area should do, and a change that alters a rule, flow, or contract
requires an update to the matching spec, not just the implementation. Small
wording fixes are the exception; behaviour changes are the rule.

Every skill contribution is assessed against five framework rules: external
content is data (not instructions), world-changing steps require confirmation,
placeholders replace real project names, evals are required (not optional), and
AI-authored contributions carry a `Generated-by:` trailer. These are not hoops
— they are the same habits the entire learning progression has been building,
now on the other side of the pull request.

The six-step path — set up, smallest change, spec check, local validation, open
PR, work with review — is the same discipline as any careful open-source
contribution, adapted to a prose-driven project where ambiguity is the main
failure mode and the eval suite is what "run your tests" means.

---

## Next

This is the final numbered lesson in the module. With all eleven lessons
complete, you have the full picture: what agents are, how to work with them,
how to choose a model, how to write, safe, portable, and testable skills, how
to work autonomously, how to program precisely in English, and how to give that
work back.

The **[hands-on lab](../tutorials.md)** (the module's practical component) is
the natural continuation: build a small skill end to end, give it an eval
suite, and run it — either self-paced or as part of a group session. A
packaged lesson wrapper for the lab is not yet available; follow the
source page directly until it lands.

For the instructor/facilitator view of the whole module, see the
**[facilitator guide](instructor-guide.md)**.

---

## Licence

Apache License 2.0 (PRINCIPLE 17). Pages written with help from AI carry a
`Generated-by:` note in their commit message following ASF Generative Tooling
Guidance.
