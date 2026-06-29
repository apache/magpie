<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone checks

Every drafted comment is run through this checklist before it
is shown to the maintainer. The checks exist to enforce
[`docs/mentoring/spec.md` § Voice](../../docs/mentoring/spec.md#voice)
and [§ Forbidden](../../docs/mentoring/spec.md#forbidden) at
runtime, so the maintainer reviews the *intervention*, not the
register.

A draft that fails any check is revised; if a second revision
still fails, the skill surfaces the failing rule to the
maintainer with the offending sentence and asks for guidance —
it does **not** post a comment that fails tone.

The checks run in order. The first failure stops the run.

---

## Hard fails (the comment cannot be posted)

| # | Rule | Detection |
|---|---|---|
| 1 | No praise without specificity. | Reject if the draft contains "great question", "thanks for the contribution", "awesome", "amazing", "fantastic", "love this", or any standalone praise sentence (a sentence whose only content is positive affect). Praise *with* a specific reference ("nice catch on the off-by-one in `foo()`") is fine, but Agentic Mentoring does not have that information by construction; in practice this rule means: no praise. |
| 2 | No restating the contributor's message. | Reject if the draft contains "so what you're saying is", "if I understand correctly", "you mentioned that", or any sentence whose content is a paraphrase of the contributor's most recent message. |
| 3 | No AI self-reference outside the footer. | Reject if the body (everything before `<ai_attribution_footer>`) contains "as an AI", "I'm an AI", "I cannot", "as a language model", "I was trained", "my training", or "I don't have access to". The footer says it once. The body says nothing. |
| 4 | No speaking for the maintainer. | Reject if the draft contains "the maintainers will probably", "the maintainers want", "the team would prefer", or any forward-looking claim about a maintainer decision. The skill says "a maintainer will reply" and stops. |
| 5 | No hedging. | Reject if the draft contains "it seems like", "perhaps", "I think maybe", "this might possibly", "I'm not sure but". The pointer is either right or shouldn't be posted. |
| 6 | One ask per comment. | Reject if the draft contains more than one direct question (counted by `?` outside code blocks) or more than one imperative sentence aimed at the contributor. If the contributor is missing several things, ask as a numbered list, not as separate paragraphs. |
| 7 | Footer present and verbatim. | Reject if the draft does not end with the literal `<ai_attribution_footer>` expansion from `<project-config>/mentoring-config.md`. Reject if anything follows the footer. |
| 8 | Author tagged once. | Reject if `@<author>` appears zero times or more than once. The first line tags; the rest of the comment does not. |
| 9 | No paraphrased docs. | Reject if the body contains a quoted block of more than two lines from a project doc. The convention is link, don't quote. |
| 10 | No predictions about review outcome. | Reject if the draft contains "looks good", "this should be approved", "this will probably be merged", "I don't think this will land". Agentic Mentoring does not signal review outcomes. |

---

## Soft fails (revise and re-check)

These do not block posting, but the skill revises once before
showing the maintainer. They exist to keep the register tight
without stalling the loop on stylistic preference.

| # | Rule | Detection |
|---|---|---|
| 11 | First line states the action. | The first sentence should be a question or imperative directed at the contributor. If it's meta ("I'm reaching out because…"), revise to lead with the action. |
| 12 | Comment is short. | Soft cap at 6 sentences (excluding the footer). Beyond that, the comment is doing too much — likely violating rule 6. |
| 13 | Plain English. | Reject jargon the contributor is unlikely to know without the link being clicked. If the draft uses a project-internal term, it should appear inside the linked label, not in prose. |
| 14 | No exclamation marks outside the footer. | The teaching register is patient, not enthusiastic. Footer can keep them if the configured footer has them; the body does not add new ones. |

---

## Rules that are deliberately not checks

Surfaced so reviewers can push back.

- **Reading level / Flesch score.** Tone is judged by humans
  in PR review of [`comment-templates.md`](comment-templates.md),
  not by automated readability scoring. Readability checkers
  reward different writing for different audiences and would
  inject style noise that doesn't serve the contributor.
- **Sentiment analysis.** Same reason. The forbidden-phrase
  list above is more honest about what we actually want to
  prevent.
- **Length cap as hard fail.** Rule 12 is a soft cap because
  the right length depends on the intervention; a why-question
  answer can legitimately need a few sentences of context.
- **Inclusivity / language scan.** Important, but lives in the
  framework's general writing standards, not in the Agentic Mentoring
  tone checks specifically.
