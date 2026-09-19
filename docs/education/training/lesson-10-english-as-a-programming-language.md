<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Lesson 10: English as a programming language](#lesson-10-english-as-a-programming-language)
  - [Learning objectives](#learning-objectives)
  - [Prerequisite knowledge](#prerequisite-knowledge)
  - [Before the lesson](#before-the-lesson)
  - [Exercises](#exercises)
    - [Exercise 1 — Spot the ambiguities](#exercise-1--spot-the-ambiguities)
    - [Exercise 2 — Disambiguate a skill step](#exercise-2--disambiguate-a-skill-step)
    - [Exercise 3 — Apply code-hygiene rules](#exercise-3--apply-code-hygiene-rules)
    - [Exercise 4 — Diagnose using the framing](#exercise-4--diagnose-using-the-framing)
  - [Self-check](#self-check)
  - [Summary](#summary)
  - [Next](#next)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Lesson 10: English as a programming language

**Source page:** [English as a programming language](../english-as-code.md)
**Estimated time:** 30 minutes (10 min reading + 20 min exercises and self-check)
**Lesson in sequence:** 10 of 11

---

## Learning objectives

By the end of this lesson you will be able to:

1. **Describe** the shift from formal-language precision to natural-language
   precision — where precision goes, and why vagueness fails more quietly than
   a syntax error.
2. **Identify** at least three specific ambiguities in a skill step and
   **explain** why each is a bug rather than harmless prose.
3. **Apply** the four code-hygiene rules (review, version, test, DRY) to the
   English instructions in a skill, explaining what each rule prevents.
4. **Explain** why a single successful run does not prove a prompt works,
   using the probabilistic nature of the model as the reason.
5. **Use** the "words are the program" framing to diagnose a given skill
   symptom — odd results, wording regressions, duplication drift — and name
   the action the framing prescribes.

---

## Prerequisite knowledge

**Lesson 4 — Your first skill.** This lesson is about the craft of writing
skill prose. You need to have written a skill already so the code-hygiene
rules feel like they apply to something real, not just theory. If you have
not done lesson 4 yet, do it first.

**Lesson 8 — Eval-driven development.** The source page for lesson 10 refers
repeatedly to the eval suite as "the test suite for code written in English".
Lesson 10 only makes full sense if you understand what an eval suite is and
why it is required. Lesson 8 is that foundation.

**Lessons 5 and 9 (recommended).** Writing safe skills (lesson 5) applies
the same disambiguation instinct to security guardrails. Agentic and autonomous
work (lesson 9) explains why imprecise prose fails worse when no person
watches. Both deepen the picture this lesson sketches.

---

## Before the lesson

Read the source page **[English as a programming language](../english-as-code.md)**
from start to finish. Pay particular attention to:

- **The table** — "The shift in one picture". Know both columns cold before
  the exercises, because the exercises will ask you to work from the right
  column only.
- **Precision still matters, it just moves** — the contrast between "Handle
  old issues" and the 30-word version that closes every gap. Exercise 2 is
  the same muscle.
- **Ambiguity is the new class of bug** — the four disambiguating moves
  (define terms, say what "done" looks like, state boundaries, name edge
  cases). Exercise 1 tests all four.
- **Because it's code, treat it like code** — the four code-hygiene rules
  (review, version, test, DRY). Exercise 3 applies them to concrete scenarios.
- **Check your understanding** at the end of the source page — answer those
  questions from memory before coming back here. The self-check below is partly
  drawn from them, with a couple of extra questions.

---

## Exercises

Work through these alone or in pairs. All exercises are paper activities;
no live model or system is needed.

### Exercise 1 — Spot the ambiguities

Each skill step below contains ambiguities. For each step, list every
ambiguous word or phrase you can find, name the specific bug it introduces
(what the model might do differently from what you intended), and name which
of the four disambiguating moves would close it.

The four moves are: (a) define your terms, (b) say what "done" looks like,
(c) state the boundaries, (d) name the edge cases.

**Step A:**
> Check recent issues and flag any that look problematic.

**Step B:**
> Summarise the PR and post it somewhere visible for the team.

**Step C:**
> If the contributor is new, give them a warm welcome and point them to the
> right docs.

<details>
<summary>Sample answers</summary>

**Step A — "Check recent issues and flag any that look problematic"**

| Ambiguous phrase | Bug introduced | Move to close it |
|---|---|---|
| "recent" | The model will pick a cutoff — last week, last month, last year — and that cutoff may differ each run. | (a) define your terms: "opened in the last 30 days" |
| "look problematic" | No criterion given; the model will invent one. Two runs may produce different lists. | (a) define your terms: "missing a reproduction step, or carrying the label `needs-info` for more than 7 days" |
| "flag" | Does "flag" mean add a label? Post a comment? Write to a report file? | (b) say what "done" looks like: "add the label `needs-attention` to each matching issue" |
| No scope stated | Does "issues" mean all issues, open only, or a specific component? | (c) state the boundaries: "open issues only, in the `<PROJECT>` repository" |
| No empty-queue case | What should happen if there are no recent issues? | (d) name the edge cases: "If no issues match, post a single-line summary noting that none were found" |

**Step B — "Summarise the PR and post it somewhere visible for the team"**

| Ambiguous phrase | Bug introduced | Move to close it |
|---|---|---|
| "Summarise" | Length, format, and content are all undefined — a one-liner or ten paragraphs are both valid. | (b) say what "done" looks like: "write a three-bullet summary covering what the PR does, why it is needed, and what to review" |
| "somewhere visible" | The model may choose Slack, a comment, a wiki page, or a tracking issue — inconsistently across runs. | (c) state the boundaries: "post as a comment on the PR itself" |
| "for the team" | "Team" is undefined — all maintainers? The code-owner of that file? The security team? | (a) define your terms or (c) state the boundaries: "for the maintainers listed in `CODEOWNERS` for the changed files" |

**Step C — "If the contributor is new, give them a warm welcome and point them to the right docs"**

| Ambiguous phrase | Bug introduced | Move to close it |
|---|---|---|
| "new" | First PR ever? First PR to this repo? New to open source entirely? The model may use different criteria each run. | (a) define your terms: "a contributor with no previously merged PR in this repository" |
| "a warm welcome" | Tone and length vary widely across runs; "warm" is not a specification. | (b) say what "done" looks like: "post the standard welcome comment from the `templates/first-contribution-welcome.md` file" |
| "the right docs" | Which docs? CONTRIBUTING.md? The setup guide? The skill-authoring page? | (c) state the boundaries: "link to `CONTRIBUTING.md` and `docs/prerequisites.md`" |
| No boundary on "new" detection | What if the contributor-history lookup fails (private account, API error)? | (d) name the edge cases: "If contributor history cannot be determined, treat the contributor as new and post the welcome" |

</details>

---

### Exercise 2 — Disambiguate a skill step

Rewrite the step below so that every ambiguity is closed. Use the four
disambiguating moves as your checklist: define terms, say what "done" looks
like, state boundaries, name edge cases. The rewritten step must leave the
model nothing material to invent.

**Original step:**
> Review the changed files and note anything worth raising.

Your rewrite should:
- Define what "changed files" means in this context (which PR? which files?).
- Define what "worth raising" means (give at least two concrete criteria).
- Describe what the output looks like (format, length, destination).
- Handle the edge case where nothing is worth raising.

<details>
<summary>Sample answer</summary>

> **Step 3 — Identify review items in the pull request**
>
> For each file changed in the pull request under review (from the diff
> already fetched in step 1), read the diff and identify lines that meet
> at least one of the following criteria:
>
> - **Missing test coverage:** a new function, method, or code path has no
>   corresponding test case in the same PR.
> - **API surface change:** a public function signature, a config key, or a
>   documented behaviour has changed without a corresponding CHANGELOG or
>   migration note.
> - **Security-relevant pattern:** a call that reads external content
>   (issue body, PR description, user input) is passed directly to a
>   shell command, an SQL query, or a templated output without explicit
>   sanitisation.
>
> For each item found, write a single bullet in this format:
> `- [file:line] <criterion name>: <one-sentence description of what you saw>`
>
> Collect all bullets into a Markdown block. If no items match any criterion,
> write exactly: `No review items found.`
>
> Do not post the block in this step; that is step 4. Do not add bullets for
> style preferences, naming conventions, or anything not listed above.

**What changed:**
- "changed files" → "each file changed in the pull request under review (from
  the diff already fetched in step 1)"
- "worth raising" → three named, concrete criteria (no improvisation)
- "note" → a specific bullet format with file, line, criterion, and description
- "anything" → bounded to exactly the three criteria listed; preferences excluded
- edge case ("nothing worth raising") → exact output string specified

</details>

---

### Exercise 3 — Apply code-hygiene rules

The source page names four code-hygiene rules that apply to skill prose as
they do to code:

- **Review it** — read skill prose for ambiguity and missing cases, not just
  typos, before it lands.
- **Version it** — prompt text lives in git; a wording change is a behaviour
  change and the history shows when it moved and why.
- **Test it** — run the skill against representative examples; do not trust
  a single successful run.
- **Keep it DRY** — shared rules in one place, pointed to rather than copied.

For each scenario below, name which rule applies (or which two, if more than
one is relevant), and write one sentence explaining what goes wrong if the
rule is ignored.

| Scenario | Rule(s) | What goes wrong if ignored |
|---|---|---|
| A maintainer copies the "stale issue" definition verbatim from the triage skill into the stale-sweep skill, because it is "easier than linking". | | |
| A wording change to a step in the triage skill is merged without running the eval suite first. | | |
| A skill is written entirely by one person and merged without a second reader looking at the prose for ambiguity. | | |
| The same skill is run once against a real issue and works. The maintainer concludes it is ready for automated use. | | |
| A skill step's wording drifts across three releases with no record of why it changed. | | |

<details>
<summary>Answers</summary>

| Scenario | Rule(s) | What goes wrong |
|---|---|---|
| Stale-issue definition copied across two skills. | **DRY** | The two copies drift apart over time — a calendar change is updated in one place and not the other, so the two skills make different decisions about staleness without anyone noticing. |
| Wording change merged without running evals. | **Test it** | The wording change may have silently shifted behaviour — the new prose is plausible to read but produces a different output distribution on the real input space. The failure is quiet (no crash, no error) and may only surface when a maintainer notices wrong decisions in production. |
| Skill written by one person, no second reader. | **Review it** | Ambiguities and missing edge cases that feel obvious to the author are invisible to them; a second reader with fresh eyes catches them before the skill is deployed. |
| Run once, concluded ready. | **Test it** | One run on one input gives no information about the input space. The model is probabilistic: the same prompt may produce different outputs on Tuesday or on an unusual input. The eval suite samples enough of the space to give real confidence. |
| Step wording drifts across three releases with no record. | **Version it** | No one can tell whether the drift was intentional or accidental, which wording was correct, or when the behaviour changed. The history is the explanation layer; without it, every wording question becomes archaeology. |

</details>

---

### Exercise 4 — Diagnose using the framing

The source page lists four symptom-to-diagnosis mappings using the "words are
the program" framing. For each symptom below, write: (a) the diagnosis the
framing prescribes, and (b) the concrete action it implies.

The four framing rules from the source page:
- Vague prompt giving odd results → **bug in your spec**, tighten the words.
- Wondering if a wording change is safe → **run the evals**, same as tests on a refactor.
- Tempted to paste a rule into three skills → **copy-paste code smell**, point to one source instead.
- Reviewing someone's skill → **reviewing code**, read for ambiguity and missing cases.

| Symptom | Diagnosis | Action |
|---|---|---|
| A triage skill classifies the same issue differently on consecutive days with no input change. | | |
| A maintainer is about to add the phrase "skip draft PRs" to the triage step, and asks whether it will break anything. | | |
| A code-reviewer is reading a newcomer's first skill PR and finds the prose a bit informal. | | |
| The phrase "for each open issue" appears in four different skills, each with a slightly different meaning of "open". | | |
| A skill is producing outputs that technically follow the step instructions but are not what the maintainer intended. | | |

<details>
<summary>Answers</summary>

| Symptom | Diagnosis | Action |
|---|---|---|
| Same issue classified differently on consecutive days. | Bug in the spec — the step leaves enough room that the model chooses differently each time. | Find the specific phrase that allows multiple readings and close it: add a precise criterion (e.g., label name, age threshold) that produces the same output regardless of when it runs. |
| "Will adding 'skip draft PRs' break anything?" | Run the evals — this is a wording change, which is a behaviour change, and the question "is it safe?" is exactly the question evals answer. | Add an eval case for a draft PR (if one does not exist), then run the full suite before merging. The evals tell you whether the new phrase produces the right distribution across the input space. |
| Reviewer finds the prose informal. | This is not a code-hygiene issue in itself — informal prose is not ambiguous prose. | Read for ambiguity, missing edge cases, and unstated assumptions (the review rule). Style is secondary; correctness is the goal. Flag any informal phrase that *also* introduces a gap in meaning; leave the rest. |
| "For each open issue" appears in four skills with different meanings. | Copy-paste code smell — the phrase has drifted because it was duplicated rather than shared. | Define "open issue" once (in a shared reference or a glossary comment) and replace the four copies with a pointer to that definition. |
| Outputs follow instructions but are not what the maintainer intended. | Bug in the spec — the instructions said something the maintainer did not mean. | Read the step aloud as if you had never seen the codebase before. Find the gap between "what the words literally permit" and "what the maintainer actually wants", then close it with a more precise phrase, an example, or an explicit exclusion. |

</details>

---

## Self-check

Answer each question in a sentence or two before moving to lesson 11. If you
cannot answer one, re-read the matching section of the source page.

**Q1.** Where does "precision" go when you program in English, and why does
vagueness fail more quietly than a syntax error?

<details>
<summary>Answer</summary>

Precision moves from *syntax* (the formal language either accepts or rejects
your code) to *meaning* (the words you choose determine what the model does).
Vagueness fails quietly because the model does not reject an imprecise
instruction with an error — it acts on a *plausible interpretation* of the
words. That interpretation may be reasonable but wrong, and you may not notice
until a real case surfaces the mismatch. A compiler shouts; a model guesses
silently.

</details>

---

**Q2.** Why is ambiguity a *bug* rather than a harmless feature of prose?

<details>
<summary>Answer</summary>

In ordinary writing, a phrase like "recent issues" is clear enough from
context. As an instruction to an agent, it is a decision the author did not
make — "recent" since when? The model fills that gap with an interpretation
that may vary across runs, across inputs, or across model versions. Every gap
is a place the agent guesses instead of following a rule, and guesses can
disagree with each other and with what the maintainer actually wanted. The
definition of a bug is behaviour that differs from intent; ambiguity
structurally produces that divergence.

</details>

---

**Q3.** Why can a single successful run not prove a prompt "works"?

<details>
<summary>Answer</summary>

The model is probabilistic: the same instruction, applied to a different input
or run on a different day, may produce a different output. A traditional
compiler is deterministic — passing once means passing always on that input.
A model is not, so one successful run proves only that the prompt worked *on
that input on that day*. The eval suite samples a representative slice of the
real input space and judges the results *as a whole*, which is what gives
evidence that the prompt works across the cases that matter, not just the
one you tested by hand.

</details>

---

**Q4.** A colleague says: "I reviewed the skill and it reads fine — I don't
see any typos." Is that a complete skill review? What is missing?

<details>
<summary>Answer</summary>

No. Reviewing code written in English means reading for *ambiguity, missing
edge cases, and unstated assumptions* — not for typos. A typo in a Python
function causes a NameError; a typo in a skill step is often still grammatical
and produces a plausible-but-wrong output with no error signal. The review
question is not "is this spelled correctly?" but "does every phrase leave the
model exactly one thing to do?" A complete skill review finds the words that
allow more than one interpretation and tightens them.

</details>

---

**Q5.** The same "stale issue" definition appears in three skills. Two of them
have since been updated; the third has not. What is the correct diagnosis and
the correct fix, using the "words are the program" framing?

<details>
<summary>Answer</summary>

Diagnosis: copy-paste code smell. Duplicated prose drifts apart exactly as
duplicated code does — a rule change is applied in two places and not the
third, so the three skills now make different decisions about staleness without
anyone noticing. The framing says: *one shared source, pointed to, not
copied*. The fix is to define "stale" once (in a shared reference or a
glossary comment at the top of the most-consulted skill), then replace the
three copies with a pointer to that definition. Now a single change to the
definition propagates to all three skills automatically.

</details>

---

## Summary

When you build with agents, the words you write are the program. Precision
does not go away — it moves from syntax to meaning. Vague phrases fail quietly:
the model acts on a plausible interpretation rather than rejecting the
instruction, and the mismatch between interpretation and intent may go
unnoticed until it matters. Ambiguity is the new class of bug: every undefined
term, unstated boundary, missing example, and unnamed edge case is a decision
the author did not make that the model will make instead. The four
disambiguating moves — define terms, say what "done" looks like, state
boundaries, name edge cases — are the tools for closing those gaps.

Because the words are the program, the same code-hygiene rules apply: review
the prose for ambiguity before it lands; version it in git so wording changes
are traceable; test it with an eval suite because one successful run is not
evidence; keep it DRY so shared rules live in one place and do not drift.
The model is probabilistic — the "compiler" never rejects a bad instruction
on your behalf — so testing harder is not optional, it is the engineering
discipline that makes programming in English reliable rather than hopeful.

---

## Next

**[How to contribute](../contributing.md)** — step 11 of the learning
progression (lesson 11 of this module is not yet packaged; follow the source
page directly until it lands). With the craft in hand — skills, guardrails,
evals, autonomy, and the programming-in-English discipline — step 11 is where
you put it to work by contributing to the framework itself.

---

## Licence

Apache License 2.0 (PRINCIPLE 18). Pages written with help from AI carry a
`Generated-by:` note in their commit message following ASF Generative Tooling
Guidance.
