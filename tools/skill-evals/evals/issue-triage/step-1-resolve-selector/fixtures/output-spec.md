<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "issues": ["<KEY>", ...],
  "selector_type": "default | explicit-key | component | updated-since | reporter",
  "error": "<string describing validation error>" | null
}
```

`issues` is an empty array when `error` is non-null.

`selector_type` is ALWAYS one of the five enum string tokens above and is NEVER null and NEVER omitted, even when `error` is non-null. When no valid concrete selector was supplied (for example a bare `--retriage` with nothing to resolve, or any hard error that falls back to the default pool), use `"default"`. Report the category the invocation resolved to (or would have resolved to), independent of whether an error was raised.

Do not include any text outside the JSON object.
