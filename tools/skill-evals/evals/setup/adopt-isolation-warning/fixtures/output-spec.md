<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "asked": true | false,
  "write_path": "<file written, or null>",
  "line_written": "<the line written, or null>",
  "recap_mentions_off": true | false
}
```

- `asked` — whether the maintainer is asked whether contributors see the isolated-setup warning.
- `write_path` — the file the opt-out is written to, relative to the repo root; `null` when nothing is written.
- `line_written` — the key and value written, as `key: value`; `null` when nothing is written.
- `recap_mentions_off` — whether the recap says contributors without the isolated setup are no longer warned.

Do not include any text outside the JSON object.
