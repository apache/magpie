<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "plugins_removed": [...],
  "plugins_kept": [...],
  "keys_preserved": [...],
  "file_deleted": true | false
}
```

`plugins_removed` is a list of `<plugin>@<marketplace>` strings — the
`enabledPlugins` entries the rules above say to remove, in the order the
rules list them.

`plugins_kept` is a list of `<plugin>@<marketplace>` strings — the
`enabledPlugins` entries the rules above say to leave in place.

`keys_preserved` is a list of top-level key names — the keys of
`.claude/settings.json` the rules above say to leave untouched.

`file_deleted` reports whether the rules above call for deleting
`.claude/settings.json` itself.

Do not include any text outside the JSON object.
