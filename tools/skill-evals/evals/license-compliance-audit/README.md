<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# license-compliance-audit evals

Behavioral evals for the `license-compliance-audit` skill.

## Suites (8 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-scope-selection | Scope selection | 4 | explicit repo, ambiguous scope, prompt injection ignored, local path |
| step-findings-report | Findings classification and report discipline | 4 | clean repo, missing SPDX headers, incomplete NOTICE, no autopilot-fix |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/license-compliance-audit/

# Single suite
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/license-compliance-audit/step-scope-selection/

# Single case
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/license-compliance-audit/step-scope-selection/fixtures/case-1-explicit-repo/
```

## What the suites cover

### step-scope-selection

Given a maintainer request, the model determines whether the audit target
is an explicit GitHub repo, a local path, or an ambiguous reference
requiring a clarifying question. The suite also checks that a
prompt-injection attempt in a user-supplied repo name is flagged and
ignored.

### step-findings-report

Given a mock scan summary (file counts, root artifact status, sampled
SPDX header results), the model classifies findings into the correct
classes (`MISSING-LICENSE-FILE`, `MISSING-NOTICE-FILE`, `INCOMPLETE-NOTICE`,
`MISSING-SPDX-HEADER`, `WRONG-SPDX-HEADER`), groups them by severity, and
never proposes to apply changes autonomously. The suite also checks that
a clean repo produces a zero-findings report and that the skill does not
offer to auto-fix anything without explicit human confirmation.
