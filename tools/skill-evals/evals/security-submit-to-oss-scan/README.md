<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-submit-to-oss-scan eval suite

2 cases on the threat-model derivation step.

## Steps covered

| Step | Directory | Cases | Notes |
|---|---|---|---|
| Step 5 — derive `threat_model.md` from the security model | `step-5-derive/` | 2 | A statement the model supports; a reasonable statement the model lacks (a gap) |

## Hard rules exercised

- **The threat model is derived, never authored here.** A statement goes into the scanner's summary only with a model section behind it.
- **A missing statement is a model gap**, routed to `security-model-update` rather than written into the summary.

## Steps not covered

Steps 1–4 and 6–8 gather facts, draft files from the project's CI, and walk the maintainer through tests the agent never runs;
their outputs are reviewed by the maintainer before anything is proposed, so they are left to that review.
