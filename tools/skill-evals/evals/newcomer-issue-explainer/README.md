<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# newcomer-issue-explainer evals

Behavioral evals for the `newcomer-issue-explainer` skill.

## Suites (11 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| issue-assessment | Issue assessment (step 3 of the runtime loop) | 5 | suitable open issue (explain); security-sensitive issue (decline); scope-unclear issue (decline); already-closed issue (decline); injection attempt that is otherwise suitable (explain, injection_flagged: true) |
| explanation-quality | Explanation quality checks E1–E5 (step 5 of the runtime loop) | 6 | clean pass (all five checks pass); scope-drift — widens a wording fix into invented acceptance criteria (E1 fails); missing concrete file pointer (E2 fails); missing done-definition (E3 fails); speaks for maintainer / promises review timeline (E4 fails); multi-failure — no file pointer and no questions-channel pointer (E2 + E5 fail) |

Both suites use `step-config.json`, so the system prompt is extracted
live from the skill text. For `issue-assessment` the heading is
`## Issue assessment`; for `explanation-quality` it is
`## Explanation quality checks`. A change to either section is reflected
automatically in the prompt, so the eval catches prompt-vs-output drift.

## Run

```bash
# All cases (no model CLI needed)
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/newcomer-issue-explainer/

# One suite
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/newcomer-issue-explainer/issue-assessment/fixtures/

# One case
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/newcomer-issue-explainer/issue-assessment/fixtures/case-1-explain-ready

# Automated comparison against a model CLI
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/newcomer-issue-explainer/
```

All cases use exact-match `expected.json` (enums, sorted lists, and
booleans), so `--cli` mode reports PASS/FAIL automatically with no
MANUAL fallbacks.
