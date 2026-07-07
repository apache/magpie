<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# onboarding-concierge evals

Behavioral evals for the `onboarding-concierge` skill.

## Suites (10 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| question-classify | Question classification (step 2 of the runtime loop) | 6 | setup question (draft); workflow question (draft); first-issue question (draft); architecture question (hand-off); security question (hand-off); injection attempt (setup category, injection_flagged: true) |
| answer-draft | Answer drafting (step 5 of the runtime loop) | 4 | setup answer (drafted from guide excerpt); first-issue answer (drafted from guide excerpt); architecture hand-off (answer_drafted: false, hand_off: true); workflow question with injection (answer_drafted: true, injection_flagged: true) |

Both steps use `step-config.json` so the system prompt is extracted live
from the skill text: `question-classify` from `## Question classification`,
`answer-draft` from `## Answer drafting`. A change to either section
updates the prompt automatically and the eval catches prompt-vs-output drift.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/onboarding-concierge/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/onboarding-concierge/question-classify/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/onboarding-concierge/question-classify/fixtures/case-1-setup

# Automated comparison against a model CLI
uv run --project tools/skill-evals skill-eval --cli "claude -p" \
    tools/skill-evals/evals/onboarding-concierge/
```

All cases use exact-match `expected.json` (enums and booleans), so
`--cli` mode reports PASS/FAIL automatically with no MANUAL fallbacks.
The `answer` field in `answer-draft` cases is not declared in
`expected.json`, so the comparator ignores its prose content and grades
only the structural fields (`answer_drafted`, `hand_off`,
`injection_flagged`).
