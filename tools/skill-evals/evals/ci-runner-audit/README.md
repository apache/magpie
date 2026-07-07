<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# ci-runner-audit evals

Behavioral evals for the `ci-runner-audit` skill.

## Suites (6 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-scope-selection | Scope selection and command choice | 4 | explicit repo, ambiguous Apache project, full-org scan, prompt injection ignored |
| step-reporting | Reporting discipline | 2 | high-confidence vs broad candidates, CI-risk language instead of security overclaiming |

## Run

```bash
# All cases
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/ci-runner-audit/

# Single suite
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/ci-runner-audit/step-scope-selection/fixtures/

# Single case
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/ci-runner-audit/step-scope-selection/fixtures/case-4-injection-ignored
```

## What the suites cover

### step-scope-selection

Given a maintainer request, the model determines whether the scan scope
is explicit enough to run immediately or whether it must ask a scope
question first. The suite also checks that a prompt-injection attempt in
user-supplied text is flagged and ignored.

### step-reporting

Given mock TSV output, the model determines how to report findings. The
suite asserts that setup-action mismatches are high-confidence, broad
macOS candidates are marked false-positive-prone, and runner findings
are described as CI breakage / portability risks rather than security
vulnerabilities.
