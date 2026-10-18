<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-mentor evals

Behavioral evals for the `pr-management-mentor` skill.

## Suites (6 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| intervention | Picking the intervention (`pick-intervention.md`) | 5 | Template 1 (missing repro); template 2 (missing version); template 3 (convention gap); multiple triggers simultaneously (ask); no trigger fires (silent) |
| tone-checks | Tone rule 13 (judgement) | 1 | Jargon without a link (soft-fail rule 13) |

## Where the hand-off, gate and tone cases went

The hand-off triggers, the out-of-scope and maintainer-engaged gates, and every tone rule that is a phrase list or a count are no longer applied by the model: [`tools/pr-management`](../../../pr-management/README.md) (`pr-management mentor`) computes them.
The 23 model-graded cases those covered are now pytest cases with the same scenarios and expectations, named after each former case:
[`tests/mentor/test_assess.py`](../../../pr-management/tests/mentor/test_assess.py) (hand-off cases 1–5, intervention cases 4, 6, 8, 9) and
[`tests/mentor/test_tone.py`](../../../pr-management/tests/mentor/test_tone.py) (tone cases 1–13 and 15).
What stays here is judgement: which intervention fits a thread, and rule 13.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/intervention/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/intervention/fixtures/case-1-missing-repro
```
