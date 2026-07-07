<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "classification": "FLAKY" | "CONSISTENTLY-BROKEN" | "CLEAN",
  "failure_rate": <float between 0 and 1>,
  "rerun_recovery_count": <integer>,
  "evidence_summary": "<one sentence describing the observed pattern>",
  "reason": "<short rationale for the classification>"
}
```

`classification` is one of:
- `FLAKY`: failure rate is above threshold AND at least one intermittency signal is present
  (re-run recovered, or failure rate is below 0.70 with both successes and failures observed)
- `CONSISTENTLY-BROKEN`: failure rate is 0.70 or above AND no re-run on the same SHA succeeded
- `CLEAN`: failure rate is below the configured threshold (0.10 by default)

`failure_rate` is the computed fraction of failure conclusions out of (success + failure) conclusions.
`rerun_recovery_count` is how many times a later attempt on the same SHA succeeded after an earlier failure.
Do not include any text outside the JSON object.
