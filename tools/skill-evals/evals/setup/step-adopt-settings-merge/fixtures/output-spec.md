<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "create" | "merge" | "refuse",
  "keys_preserved": [...],
  "plugins_added": [...],
  "allows_added": [...],
  "plugins_removed": [...],
  "marketplace_definition_changed": true | false
}
```

`action` reports which operation this merge performed on
`.claude/settings.json`: one of `"create"`, `"merge"`, or `"refuse"`.

`keys_preserved` is a list of strings — the top-level keys other than the
ones the merge rules say this merge touches, in the order they appear in
the settings file.

`plugins_added` is a list of `<plugin>@<marketplace>` strings — the entries
the merge added to `enabledPlugins`. Where it adds more than one, list them
in the order the merge rules give them.

`allows_added` is a list of `mcp__<server>__<tool>` strings — the derived
MCP allows the merge added to `permissions.allow`, in registry order.
It is empty when the floor derives no MCP allows, and `permissions` is
then left absent unless it was already present.

`plugins_removed` is a list of `<plugin>@<marketplace>` strings — the
entries the merge removed from `enabledPlugins`.

`marketplace_definition_changed` is a boolean — whether this merge added or
changed the `apache-magpie` entry in `extraKnownMarketplaces`.

Do not include any text outside the JSON object.
