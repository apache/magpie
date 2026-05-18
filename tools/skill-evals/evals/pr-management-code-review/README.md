# pr-management-code-review evals

Behavioral evals for the `pr-management-code-review` skill.

## Suites (36 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-3-security-disclosure-scan | Step 3 | 6 | CVE/security-phrase detection in title, body, commits; prompt-injection resistance |
| step-4-third-party-license | Step 4 | 6 | X/B/A licence classification, LICENSE update check; licenses/ dir alone is insufficient |
| step-4-compiled-artifacts | Step 4 | 5 | .jar/.pyc/.so/.whl detection; major vs blocking escalation |
| step-4-image-ip | Step 4 | 4 | Diagram vs logo judgement; screenshot exemption |
| step-4-license-headers | Step 4 | 8 | Tooling deference, exclusion masking, broad exclusions, exemptions (JSON, .md, README, LICENSE) |
| step-6-disposition | Step 6 | 6 | APPROVE / REQUEST_CHANGES / COMMENT auto-pick logic |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-code-review/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-code-review/step-3-security-disclosure-scan/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-code-review/step-4-license-headers/fixtures/case-3-exclusion-masking
```
