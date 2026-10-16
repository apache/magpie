<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return JSON only: `{"guard_status":"trusted|untrusted|missing","vetted_rules":"pass|unsafe|not-enabled","full_claude_parity":false,"next_steps":[]}`.
Use the observed hook trust, not project trust, for guard_status.
A write-capable vetted entry point with an allow decision is unsafe.
Use only these next_steps, in this order when applicable: `review-hook`, `replace-write-allow`, `report-read-isolation-gap`.
Include report-read-isolation-gap when the profile supplies no credential-file read restriction.
Never grant hook trust, install rules, or execute a write during verification.
