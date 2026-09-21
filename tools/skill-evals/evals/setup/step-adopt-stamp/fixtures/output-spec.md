<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "reconciled_skills": {
    "<skill name>": "<surface_hash>"
  },
  "version": "<value>",
  "at": "<date>",
  "local_reconciled_json_cleared": true | false
}
```

- `reconciled_skills` — the full `reconciled.skills` map now written into
  the committed lock: every entry migrated from
  `.apache-magpie-local/reconciled.json`'s old `skills` map (hash values
  unchanged), plus one entry per skill newly configured or overridden by
  4a/4b/4c on this run, each keyed by that skill's frontmatter `name:`.
- `version` — the version Step 2 actually read off this machine, **not**
  necessarily the `min_version` value Step 2 wrote to the lock (the two
  can differ on a re-adoption, since `min_version` never moves backward).
- `at` — today's date.
- `local_reconciled_json_cleared` — `true` when
  `.apache-magpie-local/reconciled.json` had a `skills` map to migrate,
  and its `version` / `at` / `skills` keys were removed after copying;
  `false` when there was nothing there to migrate.

Do not include any text outside the JSON object.
