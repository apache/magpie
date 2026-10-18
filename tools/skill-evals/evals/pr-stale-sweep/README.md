<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-stale-sweep evals

Behavioral evals for the `pr-stale-sweep` skill.

## Suites (3 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-5-confirm | Step 5 (confirm with user) | 3 | post-all, skip-one, cancel |

## Where the other suites went

The selector plan, the classification, the comment bodies and the recap are no longer produced by the model: [`tools/pr-management`](../../../pr-management/README.md) (`stale-sweep plan | classify | render | recap`) computes them.
The 16 model-graded cases of `step-1-fetch-pool`, `step-3-classify`, `step-4-compose-comment` and `step-7-recap` are pytest cases with the same scenarios and expectations, named after each (`test_step1_case*` … `test_step7_case*`) in [`test_stale_sweep.py`](../../../pr-management/tests/stale_sweep/test_stale_sweep.py).
They run in the `pytest` matrix on every push.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-stale-sweep/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-stale-sweep/step-5-confirm/fixtures/case-1-post-all
```
