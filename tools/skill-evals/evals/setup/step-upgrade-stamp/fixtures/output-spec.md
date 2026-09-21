<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "findings": [
    {
      "override_file": "<relative path>",
      "kind": "target-missing" | "anchor-moved" | "requires-config-unresolved",
      "detail": "<free text>"
    }
  ],
  "stamped_skills": {
    "<skill name>": "<surface_hash>"
  },
  "target": "lock" | "local"
}
```

- `findings` — one entry per override that failed any of the three
  checks (target-skill existence, anchor resolution,
  `requires_config` resolution). Empty when every override in scope
  passed all three checks clean.
- `stamped_skills` — one entry per skill whose override passed **all
  three** checks clean this walk, keyed by that skill's frontmatter
  `name:` and mapped to its current `surface_hash`. A skill with any
  finding above — including a `requires-config-unresolved` finding on an
  otherwise-clean override — is **not** included here, even though its
  anchors resolved.
- `target` — where `stamped_skills` land: `"lock"` when the project is
  adopted, `"local"` otherwise.

Do not include any text outside the JSON object.
