<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-code-review evals

Behavioral evals for the `pr-management-code-review` skill.

## Suites (56 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-4-image-ip | Step 4 | 4 | Diagram vs logo judgement; screenshot exemption |
| step-4-db-query-correctness | Step 4 | 3 | N+1 query detection, unbounded result set; batched/bounded queries pass |
| step-4-testing | Step 4 | 3 | New feature / bugfix without tests; change shipped with tests passes |
| step-4-commit-hygiene | Step 4 | 3 | Missing newsfragment for user-facing change; present newsfragment / internal-only pass |
| step-4-api-correctness | Step 4 | 3 | Breaking public-API change (blocking); optional addition / internal change pass |
| step-4-ai-generated-signals | Step 4 | 3 | Fabricated API, placeholder/stub detection; genuine code passes |
| step-4-code-quality | Step 4 | 3 | Swallowed exception; clean code and linter-handled style nits pass |
| step-4-dependency-compatibility | Step 4 | 6 | Complete constraint ledger; adopter policy selects remediation for compatible, broken (including uninstallable), and unknown graphs; environment markers affect supported resolutions |
| step-4-architecture-boundaries | Step 4 | 3 | Lower-layer-imports-higher violation; correct direction / providers→core pass |
| step-4-security-model | Step 4 | 3 | Calibration: vulnerability (blocking) vs known-limitation vs deployment-hardening (no finding) |
| step-2-reviewer-resolution | prerequisites.md § 2 | 8 | tool path from `with-reviewers:` and from `adversarial-review.md` (including `on-demand`); slash path from `with-reviewer:` and from Review preferences when the config is `off`; with the plugin missing, an explicit `with-reviewer:` still wins and a config-selected tool path falls to Review preferences; `no-adversarial` wins over everything |
| step-5-adversarial-integration | Step 5 | 3 | Merge/dedupe primary vs adversarial findings; source tagging (primary/adversarial/both); no-reviewer no-op |
| review-risk-classify | Step 4 (per-finding severity) | 4 | blocking (GPL dep), major (missing tests), minor (AI disclosure absent), none (clean code-quality change) |
| injection-guard | Steps 3–4 (injection resistance) | 4 | PR-body approve-immediately, code-comment directive, commit-message SYSTEM directive, clean PR (no injection) |
| review-handoff | Steps 7–8 (confirmation gate) | 3 | confirm→post, confirm in dry-run→dry-run-skip, wording edit→re-draft |

## Where the scripted suites went

The selectors and match chips, the slop signals and threshold, the security- and AI-disclosure scans, compiled-artifact detection, the third-party licence categories, the licence-header rules, the disposition auto-pick, reviewer ranking, the mention scan and the footer check are no longer applied by the model: [`tools/pr-management`](../../../pr-management/README.md) computes them (`pr-management code-review …`).
The 70 model-graded cases of the thirteen suites that covered them — `selector-resolution`, `step-1-selectors-match-chips`, `step-2.5-slop-detection`, `step-3-security-disclosure-scan`, `step-3-ai-authorship-disclosure`, `step-4-compiled-artifacts`, `step-4-third-party-license`, `step-4-license-headers`, `step-4.5-suggested-reviewers`, `step-6-disposition`, `review-disposition`, `step-7b-review-body-attribution`, `step-8-mention-scan` — are pytest cases with the same scenarios and expected outcomes, named after each former case, under [`tools/pr-management/tests/code_review/`](../../../pr-management/tests/code_review/).
Where a case left a judgement to the model — whether a slop candidate (H1, H5, S2) holds, whether an artifact ships in a release, the severity of a prose finding — the test passes that judgement in, and the suites above keep grading it.
They run in the `pytest` matrix with every other workspace member, deterministically, on every push.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-code-review/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-code-review/review-risk-classify/fixtures/
```
