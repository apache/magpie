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
| `step-6b-jvm-artefacts` | Step 6b — JVM artefact checks | 3 | Reading `verify-rc jvm`'s classification: the POM-licence and missing-companion-signature finding wording, and observations (a groupId outside `org.apache.*`, a consistent timestamp signal) that never change the verdict |
| `step-6c-nexus-staging` | Step 6c — Nexus staging repository | 1 | The anonymous voter path: `STATE-UNVERIFIED` on a `401` stays a warning while a missing companion `.asc` fails, and the recipe carries no credentialed or write call |
| `step-8-version-consistency` | Step 8 — Version string consistency | 2 | Exact version match across manifest files (PASS/FAIL) |

Total: **17 cases** across 8 step suites.

## Where the scripted cases went

Step 6b's gate, `--podling` and digest choice, `ABSENT` handling and findings filtering,
Step 6c's gates, staging-repository id check and probe classification,
and the whole of Step 9's roll-up are code in
[`release-management verify-rc`](../../../release-management/README.md#verify-rc).
The model-graded cases that tested that logic are pytest cases in
[`tools/release-management/tests/test_verify_rc.py`](../../../release-management/tests/test_verify_rc.py),
named after each former case with the same scenario and assertions:

| Former case | pytest |
|---|---|
| `step-6b-jvm-artefacts/case-1-clean-podling-staged-set` | `test_case_1_clean_podling_staged_set` |
| `step-6b-jvm-artefacts/case-4-jar-absent-nexus-only` | `test_case_4_jar_absent_nexus_only` |
| `step-6b-jvm-artefacts/case-5-observations-never-fail` | `test_case_5_observations_never_fail` |
| `step-6c-nexus-staging/case-1-closed-repo-complete-set` | `test_case_1_closed_repo_complete_set` |
| `step-6c-nexus-staging/case-2-open-repo` | `test_case_2_open_repo` |
| `step-6c-nexus-staging/case-4-stale-sibling-repos` | `test_case_4_stale_sibling_repos` |
| `step-6c-nexus-staging/case-5-not-reachable-404` | `test_case_5_not_reachable_404` |
| `step-6c-nexus-staging/case-6-snapshots-repo-targeted` | `test_case_6_snapshots_repo_targeted` |
| `step-6c-nexus-staging/case-7-version-mismatch` | `test_case_7_version_mismatch` |
| `step-6c-nexus-staging/case-8-non-jvm-skip` | `test_case_8_non_jvm_skip` |
| `step-6c-nexus-staging/case-9-malformed-id-skip` | `test_case_9_malformed_id_skip` |
| `step-9-reproducibility/case-1-identical-pass` … `case-5-convenience-artefact-differs` | `test_case_1_identical_pass` … `test_case_5_convenience_artefact_differs` |

The same file covers the Step 4 RAT classification, Step 7's `REVIEW` resolution and the Step 10 attestation decision, which never had model evals.
The kept Step 6b and 6c cases carry the command's real output in `report.md`, as a run would show it.

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

Steps 0, 2, 3, 5, 6, 6b, 6c and 8 all emit structured JSON.
In Steps 2, 3, 5, 6 and 8 each case feeds the
[`release-verify`](../../../release-verify/README.md) tool's JSON for the
scenario (produced by running the tool on equivalent fixture data); the
classification logic itself is covered by that tool's pytest suite, so
these cases grade how the model reads and reports the tool output, and
the judgement the tool leaves to it (Step 5's `REVIEW`). Steps 6b and 6c
feed `release-management verify-rc jvm` / `nexus` output the same way. Cases use
`expected.json` for exact-field grading and `output-spec.md` to
document the allowed schema.

The grader extracts JSON from the model's output and compares the
fields in `expected.json` exactly. Fields not present in `expected.json`
are ignored; fields present in `expected.json` must match exactly
(including `null` vs omitted), except prose fields declared in the step
fixtures' `grading-schema.json` (e.g. `paste_recipe`, `pom_findings`),
which are graded semantically.

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
- **Step 6b**: a tool `FAIL` (wrong POM licence, missing companion or
  companion signature) is always `"FAIL"`; `INHERITED-UNVERIFIED` is
  `"WARN"` — a correct POM inheriting from the ASF parent must not be
  failed; an `ABSENT` jar is a `"FAIL"` only when `release-build.md`
  declares `jvm_companion_location: staged`, and an observation
  otherwise; classified jars (`-tests`, `-shaded`, …) are never
  flagged in either direction; the informational observations
  (timestamp signal, package/groupId correspondence, companion
  content) never change the status and never assert reproducibility
  either way — an empty or single-entry jar is `insufficient-data`,
  and a placeholder companion is the sanctioned pattern, not a
  defect.
- **Step 6c**: a hard finding (repository not reachable at the id
  given for this RC, repository `open`, snapshots repository
  targeted, coordinates/version mismatch, missing sibling `.asc`,
  incomplete companion set) is always `"FAIL"`; `STATE-UNVERIFIED`
  (no Nexus credentials on the anonymous path, or a sandbox network
  refusal — never reported as "not reachable") and stale sibling
  repositories are `"WARN"`s; `open` and not-reachable are distinct
  findings and never conflated; `staging_repos` surfaces every
  repository found — never a silently picked one; the paste recipe
  carries no write verbs and reads credentials with `--netrc-file`;
  a non-JVM (or gate-failing) RC is an explicit `"SKIP"`.
- **Step 8**: `status` must be `"FAIL"` for any `match: false` or
  `extracted: null`; dev/snapshot suffixes are always `match: false`.
