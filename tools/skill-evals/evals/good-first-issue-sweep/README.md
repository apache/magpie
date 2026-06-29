# good-first-issue-sweep evals

Eval suite for the
[`magpie-good-first-issue-sweep`](../../skills/good-first-issue-sweep/SKILL.md)
skill.

## Coverage

| Step | Eval | Cases |
|---|---|---|
| Step 2 — Classify each issue | `step-2-classify` | 6 |

## step-2-classify

Exercises the G1–G7 suitability rubric. The system prompt is extracted
from the `## Step 2 — Classify each issue` heading in the skill. The
user prompt template substitutes `{report}` with the issue content.

| Case | Expected | What it tests |
|---|---|---|
| `case-1-ready` | `READY` | All G1–G7 pass; concrete scope, code pointer, small effort, no risk signals |
| `case-2-near-miss-no-code-pointer` | `NEAR-MISS [G3]` | G3 failure: feature-area prose without a specific file path |
| `case-3-near-miss-vague-scope` | `NEAR-MISS [G1, G2, G3]` | G1/G2/G3 failures: open-ended improvement request with no file pointer and no concrete DoD |
| `case-4-skip-security` | `SKIP (security-sensitive)` | G5 hard-stop: auth/credential vulnerability |
| `case-5-skip-architectural` | `SKIP (architectural-decision)` | G6 hard-stop: cross-cutting API design decision |
| `case-6-injection-ignored` | `SKIP (security-sensitive), injection_flagged=true` | G5 hard-stop wins; embedded agent instruction is flagged and ignored |
