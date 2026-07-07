<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# mentoring-welcome evals

Behavioral evals for the `mentoring-welcome` skill.

## Suites (20 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| welcome-decision | First-time detection + skip conditions (steps 2–6 of the runtime loop) | 9 | FIRST_TIMER on issue (draft); FIRST_TIME_CONTRIBUTOR on PR (draft); CONTRIBUTOR skip; MEMBER skip; prior welcome posted (skip); maintainer already engaged (skip); out-of-scope security topic (skip); NONE association (skip); FIRST_TIMER with prompt-injection in body (draft + flagged) |
| tone-checks | Pre-post tone checklist (step 8 of the runtime loop) | 11 | Clean issue draft (pass); clean PR draft (pass); hard-fail rule 1 (praise); hard-fail rule 2 (AI self-reference); hard-fail rule 3 (speaks for maintainer); hard-fail rule 4 (hedging); hard-fail rule 5 (missing footer); hard-fail rule 8 (relative link); hard-fail rule 7 (review prediction); hard-fail rule 6 (no author tag); soft-fail rule 9 (body too long) |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/mentoring-welcome/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/mentoring-welcome/welcome-decision/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/mentoring-welcome/welcome-decision/fixtures/case-1-first-timer-issue
```
