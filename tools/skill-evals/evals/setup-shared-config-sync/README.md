<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-shared-config-sync evals

Behavioral evals for the `setup-shared-config-sync` skill.

## Suites (11 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-3-decide-action | Step 3 (decide action path) | 7 | in-sync, push-only, commit-then-push, pull-then-commit-then-push, not-a-git-repo, lock-held, injection resistance |
| step-5-draft-commit | Step 5 (draft commit message) | 4 | update existing script, add new config file, multi-file commit, injection in diff |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-shared-config-sync/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-shared-config-sync/step-3-decide-action/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-shared-config-sync/step-3-decide-action/fixtures/case-1-in-sync
```

## Notes

- `step-3-decide-action` cases are auto-comparable in `--cli` mode (enumerated
  action + boolean fields).
- `step-5-draft-commit` cases use structural `has_*` flags and are MANUAL
  (the runner prints prompts for human review rather than auto-comparing).
