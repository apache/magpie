<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-stats evals

Behavioral evals for the `pr-management-stats` skill.

## Suites (13 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| classify | Step 2 | 6 | untriaged (no comments), triaged_waiting, triaged_responded via comment, triaged_responded via post-triage commit, stale marker (pre-dates head commit) → untriaged, legacy HTML-comment marker |
| pressure-weight | Step 4 (aggregate) | 7 | All weight tiers: 0 (collaborator), 0 (draft), 1 (ready label), 1 (fresh untriaged <7d), 2 (stale triaged_waiting ≥7d), 3 (untriaged ≥7d <28d), 5 (untriaged ≥28d) |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-stats/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-stats/pressure-weight/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-stats/pressure-weight/fixtures/case-7-untriaged-week-old
```
