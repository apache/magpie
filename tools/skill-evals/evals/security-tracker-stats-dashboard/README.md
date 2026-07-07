<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Evals: security-tracker-stats-dashboard

Behavioral evals for the `security-tracker-stats-dashboard` skill.
Each case supplies a fixed prompt and an `expected.json` documenting
the correct structured output.  Run them with the skill-eval runner:

```bash
# All steps at once
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/security-tracker-stats-dashboard/

# Single step
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/security-tracker-stats-dashboard/step-1-resolve-config/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/security-tracker-stats-dashboard/step-1-resolve-config/fixtures/case-1-override-yaml-found
```

---

## Suites (11 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-resolve-config | Step 1 (resolve YAML config and granularity) | 4 | adopter YAML found, no YAML fallback to default, quarterly arg overrides, explicit output-path arg |
| step-2-cache-freshness | Step 2 (cache age decision) | 4 | fresh cache → run immediately, stale cache → propose refresh, missing cache → propose full fetch, clear-cache arg → full fetch |
| step-3-hard-rules | Hard rules (read-only + injection resistance) | 3 | mutation refused, config path surfaced (golden rule 4), prompt-injection resistance |

---

## How mocking works

External tool calls (`gh`, bash scripts, mtime checks) are never
executed during evals.  Their outputs are pre-rendered as structured
text inside each case's `report.md` and injected into the user turn.
The system prompt instructs the model to treat this content as
untrusted data from the environment — enabling the prompt-injection
resistance case in step-3-hard-rules where injected instructions
appear inside a fake cache summary.
