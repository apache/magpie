<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "write_stamp": true | false,
  "write_target": "skills" | "acknowledged" | null,
  "entries": {
    "<skill name>": "<surface_hash>"
  },
  "version": "<value>" | null,
  "at": "<date>" | null
}
```

- `write_stamp` — `false` only when nothing has ever been configured or
  adopted in this repo (no committed lock, no `.apache-magpie-local/`,
  no `.apache-magpie-overrides/`); `true` otherwise.
- `write_target` — where the entries land, always inside
  `.apache-magpie-local/reconciled.json`, never the committed lock:
  `"skills"` when the project is not adopted (its `skills` map),
  `"acknowledged"` when it is already adopted (its `acknowledged.skills`
  map instead). `null` when `write_stamp` is `false`.
- `entries` — one entry per skill actually in this run's scope, each
  mapped to that skill's current `surface_hash` exactly as given in the
  input, keyed by that skill's frontmatter `name:`. Empty when
  `write_stamp` is `false`.
- `version` — only set when `write_target` is `"skills"`: the running
  plugin/framework version, exactly as given. `null` when `write_target`
  is `"acknowledged"` or `write_stamp` is `false` — the committed stamp's
  `version` is not this sub-action's to write on an adopted project.
- `at` — only set when `write_target` is `"skills"`: today's date,
  exactly as given. `null` otherwise, for the same reason as `version`.

Do not include any text outside the JSON object.
