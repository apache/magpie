<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# flaky-test-triage evals

Behavioral evals for the `flaky-test-triage` skill.

## Suites (10 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-scope-and-config | Scope and configuration resolution | 4 | explicit repo, no repo → ask, custom threshold/window, prompt injection flagged |
| step-classify | Job failure-rate classification | 4 | intermittent flaky (re-run recovers), consistently broken (no recovery), clean (below threshold), all-failures-recover (strong flakiness signal) |
| step-reporting | Reporting discipline | 2 | flaky + broken + clean findings in correct order; all-clean result stated explicitly |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/flaky-test-triage/

# Single suite
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/flaky-test-triage/step-scope-and-config/

# Single case
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/flaky-test-triage/step-scope-and-config/fixtures/case-1-explicit-repo
```

## What the suites cover

### step-scope-and-config

Given a maintainer request, the model determines whether the repository
scope is explicit enough to proceed or whether it must ask a scope
question. The suite also checks that custom window and threshold values
from the request override the config-file defaults, and that a
prompt-injection attempt in user-supplied text is flagged and ignored.

### step-classify

Given mock job failure-rate data (total runs, success/failure counts,
re-run recovery count), the model classifies each job as FLAKY,
CONSISTENTLY-BROKEN, or CLEAN using the skill's three-class decision
rules. The suite asserts that re-run recovery signals drive the flaky
classification and that high failure rates with no recovery lead to
CONSISTENTLY-BROKEN rather than FLAKY.

### step-reporting

Given a pre-classified audit result, the model produces a report and
is assessed on structural and tonal properties: flaky jobs listed before
broken jobs, conservative instability language (not "confirmed defect"),
read-only posture (no offer to modify tests), and presence of
`gh run view` / `gh run download` commands when flaky jobs are present.
