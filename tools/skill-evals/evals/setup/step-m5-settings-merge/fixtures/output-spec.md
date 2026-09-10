<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "create" | "merge" | "refuse",
  "keys_preserved": [...],
  "plugins_added": [...],
  "plugins_removed": [...],
  "marketplace_definition_changed": true | false
}
```

`action` is one of `"create"`, `"merge"`, or `"refuse"`.

`keys_preserved` is a list of strings — top-level key names from the
settings file, in the order they appear there.

`plugins_added` and `plugins_removed` are lists of `<plugin>@<marketplace>`
strings. Where more than one of the floor members appears in
`plugins_added`, list them in floor order: `magpie-setup@apache-magpie`,
`magpie-utilities@apache-magpie`, `magpie-agent-guard@apache-magpie`.

`marketplace_definition_changed` is a boolean.

Do not include any text outside the JSON object.
