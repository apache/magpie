<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-stale-sweep evals

Behavioral evals for the `pr-stale-sweep` skill.

## Suites (19 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-fetch-pool | Step 1 (fetch candidate pool) | 4 | default selector, label filter, invalid threshold pair, explicit PR numbers |
| step-3-classify | Step 3 (classify each PR) | 6 | REQUEST-UPDATE, CLOSE-STALE with prior nudge, CLOSE-STALE via hard threshold, SKIP-SECURITY, SKIP-MAINTAINER-COURT, prompt-injection resistance |
| step-4-compose-comment | Step 4 (compose proposal comment) | 3 | clean REQUEST-UPDATE draft, clean CLOSE-STALE draft, bare PR reference caught |
| step-5-confirm | Step 5 (confirm with user) | 3 | post-all, skip-one, cancel |
| step-7-recap | Step 7 (recap) | 3 | mixed results, all REQUEST-UPDATE, security-flagged PRs in recap |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-stale-sweep/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-stale-sweep/step-3-classify/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-stale-sweep/step-3-classify/fixtures/case-1-request-update
```
