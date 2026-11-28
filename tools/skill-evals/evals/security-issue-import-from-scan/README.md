<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-scan eval suite

9 cases across 2 steps: disposition bucketing and pointer routing.

## Steps covered

| Step | Directory | Cases | Notes |
|---|---|---|---|
| Step C — bucket by disposition | `step-c-bucket/` | 4 | Medium-but-by-design, CVE-worthy, PR-worth (no tracker), already-fixed |
| Pointer routing | `pointer-routing/` | 5 | the agent finds `pre-pr-adversarial-review.md` from the pointer alone at the review point and opens nothing before it; the output spec names no file, so removing the pointer fails the case; cases 3–5 route a scanner disclosure email to `email-scan.md`, vetted-ops reads to `vetted-reads.md` and a batch policy to `batched-apply.md` (mutation check when added: with those pointers deleted, all three failed) |

## Hard rules exercised

- **`creates_tracker` is true ONLY for `import-as-tracker`.** PR-worth and defense-in-depth findings are proposed per entry (open-PR-or-skip) and **never** create a `<tracker>` issue; by-design / duplicate / already-fixed create nothing.
- **Severity is a hypothesis, not a verdict.** A `Medium`-labelled finding whose attacker is a trusted role (connection-configuration user, DAG author, operator) is `by-design`, not a tracker — regardless of the scanner's label.
- **In-scope attacker required for a tracker.** `import-as-tracker` requires a genuine Security-Model violation reachable by a non-trusted-role attacker (e.g. an unauthenticated network client).
- **Fixed-since-commit → `already-fixed`.** A finding whose cited code was fixed on the default branch after the scan's commit is `already-fixed`, no action.
- **Every disposition carries grounding** — a Security-Model section, a precedent, or a fixing PR/commit.

## Pinned in code

What a bucket allows is decided by [`tools/security-management`](../../../security-management/README.md)
(`security-management issue-import-from-scan bucket-action`): `creates_tracker` is true only for `import-as-tracker`,
pytest-tested for every bucket in [`tests/test_issue_import_from_scan.py`](../../../security-management/tests/test_issue_import_from_scan.py).
Choosing the bucket and its grounding stays the model's, so this suite stays a model eval.

## Steps not covered

Step A (adapter read) and Step F (gist / report-back-PR / apply loop) are procedural / tool-driven without a clean prompt-only boundary (the Step D report, Step E decision grammar and Step F scrub are pytest-tested in `tools/security-management`); Step B's trust-boundary reasoning is exercised transitively through the Step C buckets above and is covered directly in the `security-issue-triage` suite.

## Run history

Live model runs over this whole eval directory, newest first.
Generated from [`runs.jsonl`](runs.jsonl) by `skill-eval-journal render`;
do not edit the table by hand.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-11-28 | `61f4ffe7` (opt/import-from-scan-intro) | `opus[1m]` | 1 | pass |  |
| 2026-11-28 | `835d2a29` (opt/import-from-scan-split) | `opus[1m]` | 2 | pass |  |
