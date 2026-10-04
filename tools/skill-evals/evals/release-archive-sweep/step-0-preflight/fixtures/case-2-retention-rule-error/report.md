<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

--planning-issue was NOT passed.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill archive-sweep`):

```json
{
  "ok": false,
  "skill": "archive-sweep",
  "blockers": [
    "required key `archive_retention_rule` is missing from release-management-config.md"
  ],
  "warnings": [],
  "values": {
    "non_asf": false,
    "dist_backend": "svnpubsub",
    "archive_url": "https://archive.apache.org/dist/airflow/<version>/",
    "release_lines": [
      "**`v2-11-stable`** — the 2.x train, supported; latest `2.11.0`."
    ]
  }
}
```
