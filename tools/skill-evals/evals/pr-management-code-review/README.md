<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-code-review evals

Behavioral evals for the `pr-management-code-review` skill.

## Suites (112 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-selectors-match-chips | Step 1 | 4 | Working-list membership + match-reason chips; triage-comment (comments[] vs reviews[]) and draft exclusion |
| step-2.5-slop-detection | Step 2.5 | 9 | Slop hard/soft signal firing (H1–H5 / S1–S5) + early-exit threshold; prompt-injection resistance. Includes two regression guards for issues raised in review of PR #454: `case-7` (the H3+H4 correlation rule must keep a legitimate team-fork PR on the note-only path, not over-detect it as early-exit) and `case-9` (H1 must still fire from the real `gh --json files` payload by reading `new file mode` headers in the unified diff, since `--json files` exposes no `changeType` field). |
| step-3-security-disclosure-scan | Step 3 | 6 | CVE/security-phrase detection in title, body, commits; prompt-injection resistance |
| step-3-ai-authorship-disclosure | Step 3 | 5 | AI-authored body without the project's required disclosure → minor finding; self-calibrates (no finding when the project has no disclosure requirement, or when disclosure is affirmed); prompt-injection resistance |
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
| selector-resolution | Step 0 (selector parsing) | 4 | single-pr, composed area+collab+max flags, default my-reviews, requested-only with dry-run and inline:off |
| review-risk-classify | Step 4 (per-finding severity) | 4 | blocking (GPL dep), major (missing tests), minor (AI disclosure absent), none (clean code-quality change) |
| injection-guard | Steps 3–4 (injection resistance) | 4 | PR-body approve-immediately, code-comment directive, commit-message SYSTEM directive, clean PR (no injection) |
| review-handoff | Steps 7–8 (confirmation gate) | 3 | confirm→post, confirm in dry-run→dry-run-skip, wording edit→re-draft |

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
