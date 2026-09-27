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

`selector_type` is ALWAYS one of the five enum string tokens above and is NEVER null and NEVER omitted, even when `error` is non-null.
It names the kind of selector the user *supplied*, independent of whether that selector then failed validation:

- A positional argument given as an issue key (for example `triage <something>`) is `"explicit-key"`, including when the key fails the format check and `error` is set.
- `"default"` is used ONLY when the user supplied no selector at all (for example a bare `triage`, or a bare `--retriage` with nothing to resolve).

Do not include any text outside the JSON object.
