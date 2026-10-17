<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-reassess-stats evals

Behavioral evals for the `issue-reassess-stats` skill.

## Suites (8 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-fetch-verdicts | Step 1 (fetch the verdicts) | 3 | all valid, parse error, empty directory |
| step-2-classify | Step 2 (classify) | 2 | mixed verdicts with partial fix, all fixed |
| step-3-aggregate | Step 3 (aggregate) | 3 | healthy, needs attention, action needed |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-reassess-stats/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-reassess-stats/step-3-aggregate/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-reassess-stats/step-3-aggregate/fixtures/case-1-healthy
```

## Run history

Live model runs over this whole eval directory, newest first.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-10-16 | `399ab1bc` | `claude-opus-5-5` | 10 | pass |  |
| 2026-10-13 | `dadb315c` | `claude-fable-5-1` | 4 | `step-2-classify/case-1-mixed-verdicts` failed 2 of 4 | fix: [#1615](https://github.com/apache/magpie/pull/1615) |
