<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-scan eval suite

4 cases on the disposition-bucketing step.

## Steps covered

| Step | Directory | Cases | Notes |
|---|---|---|---|
| Step C — bucket by disposition | `step-c-bucket/` | 4 | Medium-but-by-design, CVE-worthy, PR-worth (no tracker), already-fixed |

## Hard rules exercised

- **`creates_tracker` is true ONLY for `import-as-tracker`.** PR-worth and defense-in-depth findings are proposed per entry (open-PR-or-skip) and **never** create a `<tracker>` issue; by-design / duplicate / already-fixed create nothing.
- **Severity is a hypothesis, not a verdict.** A `Medium`-labelled finding whose attacker is a trusted role (connection-configuration user, DAG author, operator) is `by-design`, not a tracker — regardless of the scanner's label.
- **In-scope attacker required for a tracker.** `import-as-tracker` requires a genuine Security-Model violation reachable by a non-trusted-role attacker (e.g. an unauthenticated network client).
- **Fixed-since-commit → `already-fixed`.** A finding whose cited code was fixed on the default branch after the scan's commit is `already-fixed`, no action.
- **Every disposition carries grounding** — a Security-Model section, a precedent, or a fixing PR/commit.

## Steps not covered

Step A (adapter read) and Step F (gist / report-back-PR / apply loop) are procedural / tool-driven without a clean prompt-only boundary; Step B's trust-boundary reasoning is exercised transitively through the Step C buckets above and is covered directly in the `security-issue-triage` suite.
