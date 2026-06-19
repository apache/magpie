<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# contributor-to-committer eval suite

Behavioural eval suite for the
[`contributor-to-committer`](../../../../skills/contributor-to-committer/SKILL.md)
skill. Tests three decision points:

| Step dir | What is tested | Cases |
|---|---|---|
| `step-0-resolve-inputs` | Input validation: login format, target defaulting, window resolution | 4 |
| `step-4-map-thresholds` | Threshold mapping: MET/APPROACHING/NOT_YET per dimension; traffic-light aggregation | 5 |
| `step-5-render-brief` | Brief rendering: correct traffic-light header, gap table values, hand-off offer | 4 |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/contributor-to-committer/

# Single step
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/contributor-to-committer/step-4-map-thresholds/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/contributor-to-committer/step-4-map-thresholds/fixtures/case-1-all-met
```
