<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "selector_type": "default" | "component" | "explicit-numbers" | "dry-run",
  "warn_days": <integer>,
  "close_days": <integer>,
  "component_filter": "<string>" | null,
  "explicit_numbers": [<integer>, ...] | null,
  "error": "<string describing validation error>" | null
}
```

`selector_type` is exactly one of the tokens `"default"`, `"component"`,
`"explicit-numbers"`, or `"dry-run"`. It is `"default"` when the invocation
passes no component filter, no explicit issue numbers, and no dry-run flag.
`warn_days` and `close_days` are the integer values read verbatim from the
config thresholds (do not invent or round them). `component_filter` and
`explicit_numbers` are `null` when none were supplied.
`error` is non-null only when the selector is invalid (e.g. `warn_days >= close_days`); otherwise it is `null`.
Return ONLY a single JSON object, no fences, no commentary. Do not include any text outside the JSON object.
