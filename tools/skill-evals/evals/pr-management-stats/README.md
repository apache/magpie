<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-stats evals

Behavioral evals for the `pr-management-stats` skill.

## Suites (6 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| build-loop | Steps 1–3 (extracted from `SKILL.md` `## Steps`) | 6 | The next move from a `stats build` output: save the read `needs` names (the next closed page; the open sweep), propose a new secret gist, update a recorded gist in place, skip the publish on `dry-run`, flag a capped dashboard in the summary, and ignore an instruction quoted inside a recommendation |

## Where the classify and pressure-weight suites went

Triage-status classification and the per-PR pressure weight are no longer applied by the model: [`tools/pr-management`](../../../pr-management/README.md) computes them, with every other dashboard number.
The 13 model-graded cases those two suites held are now pytest cases with the same scenarios and the same expected outcomes, named after each former case, in [`tests/stats/test_eval_cases.py`](../../../pr-management/tests/stats/test_eval_cases.py).
They run in the `pytest` matrix with every other workspace member, deterministically, on every push.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-stats/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-stats/build-loop/fixtures/case-5-capped-update-in-place
```
