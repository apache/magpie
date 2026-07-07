<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup evals

Behavioral evals for the `setup` skill.

## Suites (5 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-verify-drift | verify.md § Check 3 (drift) | 5 | clean, method/URL mismatch, ref mismatch, svn-zip SHA-512 mismatch, local lock missing |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup/step-verify-drift/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup/step-verify-drift/fixtures/case-1-clean
```

## Notes

- `step-verify-drift` cases are fully auto-comparable: all three output
  fields (`status`, `severity`, `remediation`) are enumerated strings.
