<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

--planning-issue was NOT passed.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill archive-sweep`):

```json
{
  "ok": true,
  "skill": "archive-sweep",
  "blockers": [],
  "warnings": [],
  "values": {
    "non_asf": false,
    "dist_backend": "atr",
    "archive_url": "https://archive.apache.org/dist/magpie/",
    "release_lines": [
      "**`main`** — the 0.x train, supported; latest `0.2.0`."
    ]
  }
}
```
