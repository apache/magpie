<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "write_stamp": true | false,
  "target": "lock" | "local" | null,
  "skills": {
    "<skill name>": "<surface_hash>"
  },
  "version": "<value>",
  "at": "<date>"
}
```

- `write_stamp` — `false` when Step 3 wrote nothing this run, so there is
  nothing to record; `true` otherwise.
- `target` — which store gets the entries: `"lock"` when the project is
  already adopted (`<committed-lock>` exists), `"local"` when it is not.
  `null` when `write_stamp` is `false`.
- `skills` — one entry per skill actually in this run's scope, each
  mapped to that skill's current `surface_hash` exactly as given in the
  input. Empty when `write_stamp` is `false`.
- `version` — the running plugin/framework version, exactly as given.
- `at` — today's date, exactly as given.

Do not include any text outside the JSON object.
