<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "update_available": [
    {"plugin": "<id>", "installed": "<version>", "latest": "<version>"}
  ] | null,
  "unchecked": ["latest-version"] | []
}
```

- `update_available` — one entry per installed Magpie plugin whose
  version is behind the marketplace clone's version for that plugin,
  compared as PEP 440 with the dev segment intact (a newer `.devN`
  build is a newer version, reported like any other). Empty list when
  the clone was read successfully and every installed plugin is at or
  above the clone's version. `null` only when the comparison could not
  be performed at all — the marketplace clone could not be resolved or
  read — never as a synonym for "checked, nothing newer".
- `unchecked` — `["latest-version"]` when the clone could not be
  resolved or read this session, so the comparison did not run; empty
  when the comparison completed (whether or not it found anything).
  `update_available: null` and `unchecked: ["latest-version"]` always
  go together — a session that could not look never claims to know
  there is nothing newer.

Do not include any text outside the JSON object.
