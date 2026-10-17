<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-triage evals

Behavioral evals for the `issue-triage` skill.

## Suites (22 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-resolve-selector | Step 1 (resolve selector) | 4 | explicit-key, component, bare --retriage error, malformed key error |
| step-3-classify | Step 3 (classify) | 7 | BUG, FEATURE-REQUEST, NEEDS-INFO, DUPLICATE, INVALID, ALREADY-FIXED, prompt-injection resistance |
| step-4-compose-comment | Step 4 (compose proposal comment) | 4 | clean proposal, bare issue number, too many handles, injection flagged |
| step-5-confirm | Step 5 (confirm with user) | 4 | post-all, skip-one, edit-then-confirm, cancel |
| step-7-recap | Step 7 (recap) | 3 | mixed results, all bugs, only needs-info |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-triage/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-triage/step-1-resolve-selector/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/issue-triage/step-1-resolve-selector/fixtures/case-3-retriage-no-selector
```

## Run history

Live model runs over this whole eval directory, newest first.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-10-16 | `399ab1bc` | `claude-opus-5-5` | 10 | `step-3-classify/case-1-clear-bug` failed 1 of 10; `step-3-classify/case-2-feature-request` failed 2 of 10; `step-3-classify/case-4-duplicate` failed 3 of 10 | all prose-grader rejections, see [#1688](https://github.com/apache/magpie/issues/1688) |
