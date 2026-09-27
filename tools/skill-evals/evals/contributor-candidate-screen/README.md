<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# contributor-candidate-screen eval suite

Behavioural eval suite for the
[`contributor-candidate-screen`](../../../../skills/contributor-candidate-screen/SKILL.md)
skill. Tests five decision points:

| Step dir | What is tested | Cases |
|---|---|---|
| `step-0-gates` | A public report repository is refused with no alternative offered; a private one proceeds after the audience is confirmed | 2 |
| `step-2-pre-filter` | Pre-filter ratio applied; every dropped contributor logged with counts | 1 |
| `step-3-measure-and-shortlist` | Shortlist boundaries at `shortlist_max_missing`; evidence-only metrics never count as missing | 1 |
| `step-4-write-report` | Floor-not-decision note; verified real name; no `@`-mentions anywhere in the report | 1 |
| `step-5-deliver` | No write without confirmation; privacy re-checked before the write; nothing posted elsewhere | 3 |

## Run

```bash
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/contributor-candidate-screen/
```
