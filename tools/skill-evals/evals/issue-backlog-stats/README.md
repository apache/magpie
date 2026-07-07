<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-backlog-stats evals

Behavioral evals for the `issue-backlog-stats` skill.

## Suites (15 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-2-classify | Step 2 (classify triage status) | 6 | UNTRIAGED, TRIAGED, IN-PROGRESS, stale-candidate orthogonality, SKIP-SECURITY, prompt-injection resistance |
| step-3-aggregate | Step 3 (aggregate by area) | 3 | mixed pool with area grouping, stale-heavy pool triggering "Action needed", empty pool |
| step-4-recommend | Step 4 (health rating + recommendations) | 3 | R1 (high untriaged), R2+R4+R6 (high stale + old issues), R7 (no urgent actions) |
| step-5-render | Step 5 (render dashboard) | 3 | all sections present (HTML), area_pressure stubbed when no area labels, markdown fallback |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-backlog-stats/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-backlog-stats/step-2-classify/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-backlog-stats/step-2-classify/fixtures/case-1-untriaged
```
