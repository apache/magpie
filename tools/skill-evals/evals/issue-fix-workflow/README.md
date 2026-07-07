<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-fix-workflow evals

Behavioral evals for the `issue-fix-workflow` skill.

## Suites (20 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-2-locate-area | Step 2 (locate area to change) | 3 | stack-trace, maintainer-pointer, symbol-grep |
| step-3-failing-test | Step 3 (failing test first) | 3 | test fails as expected, missing issue key, test passes on main (surface-gap) |
| step-4-production-change | Step 4 (smallest production change) | 3 | minimal fix proceeds, symptom masks root cause, drive-by in diff |
| step-5-module-test-run | Step 5 (module test run) | 2 | clean module run, regression introduced |
| step-6-scope-check | Step 6 (scope check) | 3 | clean diff, drive-by-reformat, speculative-refactor |
| step-7-compose-commit | Step 7 (compose commit) | 4 | clean commit, security language, missing trailer, missing issue key |
| step-8-handback | Step 8 (hand-back artefact) | 2 | complete handback, missing fields |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-fix-workflow/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-fix-workflow/step-6-scope-check/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-fix-workflow/step-6-scope-check/fixtures/case-1-clean-diff
```
