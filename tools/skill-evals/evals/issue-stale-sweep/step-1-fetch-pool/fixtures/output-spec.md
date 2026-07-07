<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "selector_type": "default | component | explicit-numbers | dry-run",
  "warn_days": <integer>,
  "close_days": <integer>,
  "component_filter": "<string>" | null,
  "explicit_numbers": [<integer>, ...] | null,
  "error": "<string describing validation error>" | null
}
```

`error` is non-null when the selector is invalid (e.g. `warn_days >= close_days`).
Do not include any text outside the JSON object.
