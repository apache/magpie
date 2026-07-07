<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# good-first-issue-sweep evals

Eval suite for the
[`magpie-good-first-issue-sweep`](../../skills/good-first-issue-sweep/SKILL.md)
skill.

## Coverage

| Step | Eval | Cases |
|---|---|---|
| Step 2 — Classify each issue | `step-2-classify` | 6 |
| Step 3 — Present proposals | `step-3-present-proposals` | 4 |

## step-2-classify

Exercises the G1–G7 suitability rubric. The system prompt is extracted
from the `## Step 2 — Classify each issue` heading in the skill. The
user prompt template substitutes `{report}` with the issue content.

| Case | Expected | What it tests |
|---|---|---|
| `case-1-ready` | `READY` | All G1–G7 pass; concrete scope, code pointer, small effort, no risk signals |
| `case-2-near-miss-no-code-pointer` | `NEAR-MISS [G3]` | G3 failure: feature-area prose without a specific file path |
| `case-3-near-miss-vague-scope` | `NEAR-MISS [G1, G2, G3]` | G1/G2/G3 failures: open-ended improvement request with no file pointer and no concrete DoD |
| `case-4-skip-security` | `SKIP (security-sensitive)` | G5 hard-stop: auth/credential vulnerability |
| `case-5-skip-architectural` | `SKIP (architectural-decision)` | G6 hard-stop: cross-cutting API design decision |
| `case-6-injection-ignored` | `SKIP (security-sensitive), injection_flagged=true` | G5 hard-stop wins; embedded agent instruction is flagged and ignored |

## step-3-present-proposals

Exercises the presentation and grouping rules from Step 3. The system prompt is
extracted from the `## Step 3 — Present proposals` heading in the skill. The
user prompt template substitutes `{report}` with the Step 2 classification
results. The model returns structured JSON describing properties of the
presentation it would produce (see `output-spec.md`).

The critical invariant: NEAR-MISS issues must never receive a label proposal or
confirmation prompt. This is verified via `near_miss_has_label_proposal: false`.

| Case | What it tests |
|---|---|
| `case-1-ready-only` | 3 READY issues: label named, confirmation prompt present, all refs clickable |
| `case-2-mixed` | 2 READY + 2 NEAR-MISS + 1 SKIP: correct grouping; SKIP shown as count only; no label for NEAR-MISS |
| `case-3-near-miss-only` | 3 NEAR-MISS issues, 0 READY: no label proposed, no confirmation prompt |
| `case-4-injection-flagged` | 1 READY + 1 NEAR-MISS (injection_flagged): injection noted in output; NEAR-MISS still gets no label |
