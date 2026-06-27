<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Eval suite: `release-verify-rc`

Behavioural eval suite for the
[`release-verify-rc`](../../../../skills/release-verify-rc/SKILL.md) skill.

## Suites

| Suite | Step | Cases | What is graded |
|---|---|---|---|
| `step-0-preflight` | Step 0 — Pre-flight check | 3 | JSON pre-flight verdict (proceed/blocked), staging URL derivation, config validation |
| `step-2-verify-signatures` | Step 2 — Verify GPG signatures | 2 | Signature classification (PASS/FAIL/KEY-NOT-IN-KEYS), paste recipe |
| `step-3-verify-checksums` | Step 3 — Verify checksums | 2 | Checksum classification (PASS/MISMATCH/MISSING-DIGEST), deprecated md5 detection |
| `step-5-notice-license` | Step 5 — NOTICE/LICENSE presence | 2 | File presence (PASS/WARN/FAIL), diff-lines count, diff summary |
| `step-6-binary-exclusion` | Step 6 — Binary exclusion check | 2 | Prohibited-binary detection (PASS/FAIL), expected-binary classification |
| `step-7-version-consistency` | Step 7 — Version string consistency | 2 | Exact version match across manifest files (PASS/FAIL) |

Total: **13 cases** across 6 step suites.

## Run

```bash
# Full suite
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-verify-rc/

# One step only
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-verify-rc/step-0-preflight/

# CLI (non-interactive) mode
uv run --project tools/skill-evals skill-eval --cli tools/skill-evals/evals/release-verify-rc/
```

## Grading methodology

Steps 0, 2, 3, 5, 6, and 7 all emit structured JSON. Cases use
`expected.json` for exact-field grading and `output-spec.md` to
document the allowed schema.

The grader extracts JSON from the model's output and compares the
fields in `expected.json` exactly. Fields not present in `expected.json`
are ignored; fields present in `expected.json` must match exactly
(including `null` vs omitted).

`PASS` — all fields in `expected.json` match the model output.
`FAIL` — any field mismatch.
`MANUAL` — the grader could not extract valid JSON.
`ERROR` — harness error.

## Key grading rules

- **Step 0**: `verdict` must be `"blocked"` when any blocker is present;
  `blockers` must be non-empty; `staging_url` must be `null` when the
  URL cannot be derived.
- **Step 2**: `status` must be `"FAIL"` if any `classification` is not
  `"PASS"`. A `KEY-NOT-IN-KEYS` classification is a hard FAIL.
- **Step 3**: `status` must be `"FAIL"` for `MISMATCH`; `"WARN"` only
  for deprecated md5 anomalies; deprecated md5 never causes `"FAIL"` alone.
- **Step 5**: `status` must be `"FAIL"` when either file is absent;
  `"WARN"` for material diffs; `"PASS"` for version-string-only diffs.
- **Step 6**: `status` must be `"FAIL"` when `prohibited_found` is
  non-empty.
- **Step 7**: `status` must be `"FAIL"` for any `match: false` or
  `extracted: null`; dev/snapshot suffixes are always `match: false`.
