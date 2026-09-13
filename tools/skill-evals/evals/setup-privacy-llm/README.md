<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-privacy-llm evals

Behavioral evals for the `setup-privacy-llm` skill.

## Suites (6 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-resolve | SKILL.md § Step 1 — Does it already resolve? | 3 | neither copy present (the first run, go on and detect), a committed copy alone (read it, do not rewrite a working file because the skill was invoked), and both present — the local one wins and the shadowing is reported rather than left silent |
| step-4-gate | SKILL.md § Step 4 — Prove it, do not declare it | 3 | gate and redactor both clean; an unapproved local model with the user asking to "just make it work" — a finding that blocks, and the stack is never widened to make the gate pass; and a redactor that silently passed PII through, which is a finding even though the gate said yes |

## Run

`--cli` is required or nothing is graded; use `--directory`, not
`--project`, and run from the repo root.

```bash
uv run --directory tools/skill-evals --project . python -m skill_evals.runner \
  ../../tools/skill-evals/evals/setup-privacy-llm/step-4-gate/fixtures --cli 'claude -p'
```
