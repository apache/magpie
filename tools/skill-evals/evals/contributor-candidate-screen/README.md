<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# contributor-candidate-screen eval suite

Behavioural eval suite for the
[`contributor-candidate-screen`](../../../../skills/contributor-candidate-screen/SKILL.md)
skill. Tests six decision points:

| Step dir | What is tested | Cases |
|---|---|---|
| `step-0-gates` | A public report repository is refused with no alternative offered; a private one proceeds after the audience is confirmed | 2 |
| `step-1-pool` | Roster ids mapped to GitHub handles (unmapped ids listed, current committers excluded); a merged-PR search over 1000 results sliced by month, never truncated | 2 |
| `step-2-pre-filter` | Pre-filter ratio applied; a zero (evidence-only) floor ignored; the PMC pool not count-filtered by default; no recent landed change drops a contributor; `require: all` and `targets: both`; every dropped contributor logged with counts | 4 |
| `step-3-measure` | Everyone who passed the pre-filter goes into the report, alphabetically, with no comparison against the floors | 1 |
| `step-4-write-report` | Surfacing note at the top; verified real name; no `@`-mentions anywhere in the report; capped counts shown as minimums; people listed alphabetically, never by activity, with no floors-met count or threshold column | 3 |
| `step-5-deliver` | No write without confirmation; privacy re-checked before the write; nothing posted elsewhere | 3 |

## Run

```bash
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/contributor-candidate-screen/
```
