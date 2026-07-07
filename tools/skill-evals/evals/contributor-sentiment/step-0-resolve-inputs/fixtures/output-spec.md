<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "upstream": "<owner/repo>",
  "window_months": 6,
  "window_start": "YYYY-MM-DD",
  "window_end": "YYYY-MM-DD",
  "baseline_start": "YYYY-MM-DD",
  "baseline_end": "YYYY-MM-DD",
  "baseline_available": true,
  "profile": "asf" | "non-asf" | "custom",
  "inputs_valid": true,
  "notes": []
}
```

- `upstream`: the `owner/repo` resolved from config or user input.
- `window_months`: the window length in months.
- `window_start` / `window_end`: ISO-8601 dates for the active window.
- `baseline_start` / `baseline_end`: ISO-8601 dates for the baseline window.
- `baseline_available`: false if the project was created after `baseline_start` or if no baseline period could be established.
- `profile`: the resolved project profile.
- `inputs_valid`: true when all required inputs resolved without error.
- `notes`: any warnings, e.g. "baseline period pre-dates project creation".

Do not include any text outside the JSON object.
