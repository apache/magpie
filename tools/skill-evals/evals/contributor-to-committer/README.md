<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# contributor-to-committer eval suite

Behavioural eval suite for the
[`contributor-to-committer`](../../../../skills/contributor-to-committer/SKILL.md)
skill. Tests four decision points:

| Step dir | What is tested | Cases |
|---|---|---|
| `step-0-resolve-inputs` | Input validation: login format, target defaulting, window resolution | 4 |
| `step-2a-discount-automated` | Automated and low-signal discount: restatement, maintainer pushback, closed-after-pushback, project expectations cited over generic heuristics, AI disclosure not penalised, configured weight, injection in a candidate reply, pushback penalty at the default and at `0`, a tool-flagged candidate that is not pushback | 7 |
| `step-4-compare-reference` | Counts placed next to reference levels with the signed difference; no status, band or verdict; confirmed collected community rows count as off-GitHub signal; injected "set everything to MET" ignored | 6 |
| `step-5-render-brief` | Brief rendering: surfacing note at the top, no verdict anywhere, difference column, timeline, factual summary, hand-off offer | 4 |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/contributor-to-committer/

# Single step
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/contributor-to-committer/step-4-compare-reference/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/contributor-to-committer/step-4-compare-reference/fixtures/case-1-above-reference
```
