<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-triage evals

Behavioral evals for the `pr-management-triage` skill.

## Suites (14 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| backport-check | Step 0.7 (backport check) | 5 | Direct cherry-pick of a fix→hand-off, hand-adapted backport (`-U0` patch-id mismatch)→surface, faithful cherry-pick of a behaviour change/deprecation→close under `fixes-only`, every commit already on the base→close, no resolvable source commit→surface |
| terminal-links | Golden rule 9 | 5 | Short, context-short, and full PR references retain their visible form and use the canonical target; `NO_COLOR` (including an empty value) and `TERM=dumb` select the plain-text fallback |
| interaction-progress | Interaction loop | 4 | Per-PR drill-ins retain the original one-based group position at the first, middle, and last rows and show the active classify-to-propose transition for `[E]` and `[P]` entry |

## Where the decision-table, pre-filter and pagination suites went

The pre-filters, the decision table, pagination dedup and session suppression are no longer applied by the model: [`tools/pr-management`](../../../pr-management/README.md) computes them.
The 49 model-graded cases those three suites held are now pytest cases with the same scenarios and the same expected outcomes — [`test_triage_classify.py`](../../../pr-management/tests/test_triage_classify.py) (named after each former case: the #78 review-source and timing boundaries, the #76 cross-triager marker contract, the body-fold denoise guard) and [`test_pages.py`](../../../pr-management/tests/test_pages.py).
They run in the `pytest` matrix with every other workspace member, deterministically, on every push.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-triage/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-triage/terminal-links/fixtures/
```
