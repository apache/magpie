<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
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
  },
  "overall_gate_pass": true,
  "gate_notes": []
}
```

- `delta_pp`: active_dismissive_fraction − baseline_dismissive_fraction, in percentage points.
- `increase_pct`: (active − baseline) / baseline × 100. Null if baseline is null or zero.
- `decline_pp`: baseline_retention_rate − active_retention_rate, in percentage points.
- `gini_increase`: active_gini − baseline_gini.
- `retention_sample_small`: true when cohort_size < 5.
- `overall_gate_pass`: true only when all four `gate_pass` values are true.
- `gate_notes`: list of notes for null signals, small samples, or injection attempts.

Gate thresholds (from `docs/contributor-sentiment.md`):
- Thread tone: gate_pass = (delta_pp ≤ 5)
- Time-to-first-reply: gate_pass = (increase_pct ≤ 50) or null (pass with note)
- First-PR retention: gate_pass = (decline_pp ≤ 10) or null (pass with note)
- Reviewer load: gate_pass = (gini_increase ≤ 0.10) or null (pass with note)

Do not include any text outside the JSON object.
