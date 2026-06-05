# pr-management-code-review evals

Behavioral evals for the `pr-management-code-review` skill.

## Suites (74 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-selectors-match-chips | Step 1 | 4 | Working-list membership + match-reason chips; triage-comment (comments[] vs reviews[]) and draft exclusion |
| step-3-security-disclosure-scan | Step 3 | 6 | CVE/security-phrase detection in title, body, commits; prompt-injection resistance |
| step-4-third-party-license | Step 4 | 6 | X/B/A licence classification, LICENSE update check; licenses/ dir alone is insufficient |
| step-4-compiled-artifacts | Step 4 | 5 | .jar/.pyc/.so/.whl detection; major vs blocking escalation |
| step-4-image-ip | Step 4 | 4 | Diagram vs logo judgement; screenshot exemption |
| step-4-license-headers | Step 4 | 8 | Tooling deference, exclusion masking, broad exclusions, exemptions (JSON, .md, README, LICENSE) |
| step-4-db-query-correctness | Step 4 | 3 | N+1 query detection, unbounded result set; batched/bounded queries pass |
| step-4-testing | Step 4 | 3 | New feature / bugfix without tests; change shipped with tests passes |
| step-4-commit-hygiene | Step 4 | 3 | Missing newsfragment for user-facing change; present newsfragment / internal-only pass |
| step-4-api-correctness | Step 4 | 3 | Breaking public-API change (blocking); optional addition / internal change pass |
| step-4-ai-generated-signals | Step 4 | 3 | Fabricated API, placeholder/stub detection; genuine code passes |
| step-4-code-quality | Step 4 | 3 | Swallowed exception; clean code and linter-handled style nits pass |
| step-4-architecture-boundaries | Step 4 | 3 | Lower-layer-imports-higher violation; correct direction / providers→core pass |
| step-4-security-model | Step 4 | 3 | Calibration: vulnerability (blocking) vs known-limitation vs deployment-hardening (no finding) |
| step-5-adversarial-integration | Step 5 | 3 | Merge/dedupe primary vs adversarial findings; source tagging (primary/adversarial/both); no-reviewer no-op |
| step-6-disposition | Step 6 | 6 | APPROVE / REQUEST_CHANGES / COMMENT auto-pick logic |
| step-7b-review-body-attribution | Step 7b | 3 | Golden rule 5 AI-attribution footer present / missing / paraphrased before posting |
| review-disposition | Step 2 (per-PR review loop — disposition) | 5 | APPROVE (clean PR), REQUEST_CHANGES (code issues), COMMENT (failing CI), COMMENT (unresolved maintainer REQUEST_CHANGES), prompt-injection resistance |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-code-review/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-code-review/review-disposition/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-code-review/review-disposition/fixtures/case-1-approve
```
