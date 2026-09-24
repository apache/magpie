<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "path": "tool" | "slash" | "none",
  "reviewers": ["<backend>", ...],
  "slash_command": "<command>" | null,
  "maintainer_types_command": true | false
}
```

- `path` — `"tool"` when model CLIs are run by the agent through the
  adversarial-review tool, `"slash"` when a slash command is proposed for
  the maintainer to type, `"none"` when no adversarial reviewer runs.
- `reviewers` — the backend names the tool path runs, in the order given;
  empty unless `path` is `"tool"`.
- `slash_command` — the slash command, exactly as configured; `null` unless
  `path` is `"slash"`.
- `maintainer_types_command` — `true` only on the slash path.

Do not include any text outside the JSON object.
