<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-deduplicate eval suite

3 cases across 1 step: the pieces of the merge the model still writes.

## Steps covered

| Step | Directory | Cases | Notes |
|---|---|---|---|
| Step 3 — the merge inputs | `step-3-merge-inputs/` | 3 | Standard merge with two summaries, version widening, a reporter CVSS in the dropped report |

## Hard rules exercised

- The headline, analysis and merged summary never repeat a reporter-supplied
  CVSS score, vector or severity rating.
- Affected versions are widened to cover both trackers, not taken from the kept
  side alone.
- A merged summary is written only when both trackers carry different ones.

## Deterministic steps — pytest, not model evals

Steps 1, 2, 3 (assembling the merged body), 4, 5 and 6 are decided or rendered by
`security-management issue-deduplicate` and pytest-tested in
[`tools/security-management/tests/test_issue_deduplicate.py`](../../../security-management/tests/test_issue_deduplicate.py),
one test per former case of `step-1-classify` (cases 1–4), `step-2-extract-fields` (1–3),
`step-3-merge-body` (1–4), `step-4-rollup-entries` (1–2), `step-5-confirm` (1–3) and `step-6-recap` (1–2),
with the hard rules they graded: different scope labels refuse the merge, a dropped-side severity is never
carried over, a CWE conflict is a blocker, both credits and both threads land on the kept tracker, the dropped
report sits in a collapsed *Second independent report* block, every cross-reference is a link, and `cancel`
applies nothing. Prompt injection in a tracker body no longer reaches a decision: the checks read labels,
states and field values, never the report text.

## Steps not covered

Step 0 (pre-flight check) is a simple guardrail; the apply order (`apply-plan`) is pytest-tested in the same file.
