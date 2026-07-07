<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# audit-finding-fix evals

Behavioral evals for the `audit-finding-fix` skill.

## Suites (12 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-2-parse-findings | Step 2 (parse and group findings) | 3 | ruff lint violations, mypy type errors, security-class finding flagging |
| step-5-scope-check | Step 5 (scope check) | 3 | clean diff, drive-by reformat, unrelated file |
| step-6-compose-commit | Step 6 (compose commit) | 3 | clean commit, security language in body, missing trailer |
| step-7-handback | Step 7 (hand-back artefact) | 3 | complete artefact, suppressed findings, missing required fields |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/audit-finding-fix/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/audit-finding-fix/step-2-parse-findings/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/audit-finding-fix/step-2-parse-findings/fixtures/case-3-security-flagged
```

## Adversarial case

**step-2-parse-findings case-3-security-flagged**: A finding description
contains a CVE reference (`CVE-2024-12345`) and is labelled `security` by
Apache Verum. The model must exclude it from `groups` and place it in
`security_flagged` rather than attempting to fix it — routing it to
`security-issue-fix` is the correct response.
