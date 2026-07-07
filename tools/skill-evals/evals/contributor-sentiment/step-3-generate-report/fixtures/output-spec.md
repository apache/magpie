<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "upstream": "<owner/repo>",
  "window_start": "YYYY-MM-DD",
  "window_end": "YYYY-MM-DD",
  "baseline_start": "YYYY-MM-DD",
  "baseline_end": "YYYY-MM-DD",
  "profile": "asf" | "non-asf" | "custom",
  "baseline_available": true,
  "signals": {
    "thread_tone": {
      "active_dismissive_fraction": 0.0,
      "baseline_dismissive_fraction": 0.0,
      "delta_pp": 0.0,
      "gate_pass": true,
      "injection_attempts_found": 0
    },
    "time_to_first_reply": {
      "active_median_hours": 0.0,
      "baseline_median_hours": 0.0,
      "increase_pct": 0.0,
      "no_reply_count": 0,
      "gate_pass": true
    },
    "first_pr_retention": {
      "active_retention_rate": 0.0,
      "baseline_retention_rate": 0.0,
      "decline_pp": 0.0,
      "cohort_size": 0,
      "retention_sample_small": false,
      "gate_pass": true
    },
    "reviewer_load": {
      "active_gini": 0.0,
      "baseline_gini": 0.0,
      "gini_increase": 0.0,
      "reviewer_count": 0,
      "gate_pass": true
    }
  },
  "gate_pass": true,
  "gate_notes": [],
  "save_offered": true
}
```

- `gate_pass`: true only when all four signal `gate_pass` values are true.
- `save_offered`: true when the skill offered to save the report to a file.
- All signal fields match the Step 2 scoring output.

Do not include any text outside the JSON object.
