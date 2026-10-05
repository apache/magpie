<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# contributor-calibrate eval suite

Behavioural eval suite for the
[`contributor-calibrate`](../../../../skills/contributor-calibrate/SKILL.md)
skill. Tests three decision points:

| Step dir | What is tested | Cases |
|---|---|---|
| `step-1-find-nominations` | Nomination rows from the private list: outcome and deferral category, holdout and excluded threads never opened, no opinions or quotes kept, injection in a thread treated as data | 4 |
| `step-4-propose-floors` | Floor arithmetic: weighted 25th percentile of elected rows, a non-separating metric proposed as evidence only, no floors for a target with too few elected rows, no names in the diff | 3 |
| `step-6-write-configuration` | Write target: the personal layer resolved by `setup_preflight.layers` — the git-directory home on an unadopted repo, `.apache-magpie-local/` on an adopted one — never an offer of `.apache-magpie-overrides/`, even when asked for a project-wide change, and a stop when there is no personal layer | 4 |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/contributor-calibrate/

# Single step
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/contributor-calibrate/step-1-find-nominations/fixtures/
```
