<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Upstream: myorg/brand-new-project
Window: 2026-04-05 .. 2026-07-05
Baseline: not available (project created 2026-03-15)
Profile: non-asf

Scored signals (snapshot only — no baseline comparison possible):

thread_tone:
  active_dismissive_fraction: 8.0
  baseline_dismissive_fraction: null
  delta_pp: null
  gate_pass: true  (null → pass with note)
  injection_attempts_found: 0

time_to_first_reply:
  active_median_hours: 14.3
  baseline_median_hours: null
  increase_pct: null
  no_reply_count: 2
  gate_pass: true  (null → pass with note)

first_pr_retention:
  active_retention_rate: 33.3
  baseline_retention_rate: null
  decline_pp: null
  cohort_size: 6
  retention_sample_small: false
  gate_pass: true  (null → pass with note)

reviewer_load:
  active_gini: 0.30
  baseline_gini: null
  gini_increase: null
  reviewer_count: 3
  gate_pass: true  (null → pass with note)

overall_gate_pass: true (with notes — no baseline available)
gate_notes:
  - baseline period pre-dates project creation; snapshot-only output produced
  - all signal deltas are null; gate passes with note pending a baseline period
