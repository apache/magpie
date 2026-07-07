<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-reproducer evals

Behavioral evals for the `issue-reproducer` skill.

## Suites (27 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-inventory | Step 1 (inventory) | 4 | single block with env, multiple blocks across comments, no code blocks, injection in body |
| step-2-pick-candidate | Step 2 (pick candidate reproducer) | 3 | only one block, simplest complete, maintainer-simplified |
| step-3-classify-shape | Step 3 (classify shape) | 5 | shape A, B, C, D, E |
| step-5.5-confirm | Step 5.5 (confirm before executing untrusted code) | 3 | clean, network call, env-read + subprocess |
| step-7-verify | Step 7 (verify against original failure pattern) | 6 | still-fails-same, fixed-on-master, intended-behaviour, cannot-run-environment, still-fails-different, prompt-injection override attempt |
| step-8-baselines | Step 8 (historical baselines) | 3 | two maintainer baselines, no baselines, mixed statuses |
| step-10-compose-verdict | Step 10 (compose verdict) | 3 | still-fails maintainer-confirmed, fixed no confirmation, intended-behaviour |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-reproducer/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-reproducer/step-8-baselines/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-reproducer/step-5.5-confirm/fixtures/case-3-env-read-and-subprocess
```
