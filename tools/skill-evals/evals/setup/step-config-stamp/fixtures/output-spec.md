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

- `write_stamp` — `true` only when this step actually writes an entry
  (to either the `skills` map or `acknowledged.skills`) for at least one
  skill in this run's scope; `false` otherwise. Two different situations
  both produce `false`: nothing has ever been configured or adopted in
  this repo (no committed lock, no `.apache-magpie-local/`, no
  `.apache-magpie-overrides/`); or every skill in scope is on an
  already-adopted project and was already fully configured **before**
  this run, so Step 3 wrote no file for it this run.
- `write_target` — where the entries land, always inside
  `.apache-magpie-local/reconciled.json`, never the committed lock:
  `"skills"` when the project is not adopted (its `skills` map, written
  for every skill in scope whether or not this run touched a file for
  it); `"acknowledged"` when it is already adopted (its
  `acknowledged.skills` map, written **only** for a skill whose missing
  configuration this run actually wrote — Step 3 produced the file that
  made it resolve for the first time this run). `null` when
  `write_stamp` is `false`.
- `entries` — one entry per skill actually written this run, each
  mapped to that skill's current `surface_hash` exactly as given in the
  input, keyed by that skill's frontmatter `name:`. Empty when
  `write_stamp` is `false`.
- `version` — only set when `write_target` is `"skills"`: the running
  plugin/framework version, exactly as given. `null` when `write_target`
  is `"acknowledged"` or `null` — the committed stamp's `version` is not
  this sub-action's to write on an adopted project, and there is nothing
  to date when nothing was written.
- `at` — only set when `write_target` is `"skills"`: today's date,
  exactly as given. `null` otherwise, for the same reason as `version`.

Do not include any text outside the JSON object.
