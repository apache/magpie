<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Upstream: apache/example-project
Window: 2026-01-05 .. 2026-07-05
Baseline: 2025-07-05 .. 2026-01-05
Profile: asf

Scored signals:

thread_tone:
  active_dismissive_fraction: 5.0
  baseline_dismissive_fraction: 5.0
  delta_pp: 0.0
  gate_pass: true
  injection_attempts_found: 0

time_to_first_reply:
  active_median_hours: 8.4
  baseline_median_hours: 7.6
  increase_pct: 10.5
  no_reply_count: 3
  gate_pass: true

first_pr_retention:
  active_retention_rate: 50.0
  baseline_retention_rate: 43.8
  decline_pp: -6.2  (improvement, not a decline)
  cohort_size: 18
  retention_sample_small: false
  gate_pass: true

reviewer_load:
  active_gini: 0.19
  baseline_gini: 0.21
  gini_increase: -0.02  (improvement)
  reviewer_count: 5
  gate_pass: true

overall_gate_pass: true
gate_notes: []
