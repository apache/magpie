<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Upstream: myorg/growing-project
Window: 2026-01-05 .. 2026-07-05
Baseline: 2025-07-05 .. 2026-01-05
Profile: non-asf

Scored signals:

thread_tone:
  active_dismissive_fraction: 6.7
  baseline_dismissive_fraction: 0.0
  delta_pp: 6.7
  gate_pass: false
  injection_attempts_found: 0

time_to_first_reply:
  active_median_hours: 18.2
  baseline_median_hours: 11.5
  increase_pct: 58.3
  no_reply_count: 5
  gate_pass: false

first_pr_retention:
  active_retention_rate: 18.2
  baseline_retention_rate: 40.0
  decline_pp: 21.8
  cohort_size: 22
  retention_sample_small: false
  gate_pass: false

reviewer_load:
  active_gini: 0.58
  baseline_gini: 0.18
  gini_increase: 0.40
  reviewer_count: 4
  gate_pass: false

overall_gate_pass: false
gate_notes:
  - thread tone regression: dismissive fraction rose 6.7 pp (threshold 5 pp)
  - time-to-first-reply rose 58.3% (threshold 50%)
  - first-PR retention declined 21.8 pp (threshold 10 pp)
  - reviewer load Gini rose 0.40 (threshold 0.10)
