<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "proposals": [
    {
      "kind": "reanchor" | "config",
      "skill": "<skill name>",
      "override_file": "<relative path, or null for a config finding>",
      "detail": "<free text — the heading that moved, or the file that is missing>"
    }
  ],
  "unchecked": ["anchor-resolution" | "requires_config"],
  "stamp_written": true | false
}
```

- `proposals` — one entry per finding from the two checks. `kind: "reanchor"`
  when an override's referenced anchor no longer resolves in the target
  skill's current `SKILL.md`; `kind: "config"` when a `requires_config`
  entry does not resolve through the lookup chain. Empty when both checks
  pass cleanly for everything in scope.
- `unchecked` — which check(s) could not be completed for at least one
  skill in scope, because that skill's `SKILL.md` was not readable this
  session (a marketplace install's plugin cache, denied under the
  sandbox). `requires_config` resolution needs only files already in the
  repository, so it is never unchecked. Empty when nothing was skipped.
- `stamp_written` is `true` only when `proposals` and `unchecked` are both
  empty — nothing changed, so the stamp is written immediately with no
  confirmation needed. Any finding, or anything left unchecked, means
  `false`: writing the stamp waits on confirming or completing those
  first.

Do not include any text outside the JSON object.
