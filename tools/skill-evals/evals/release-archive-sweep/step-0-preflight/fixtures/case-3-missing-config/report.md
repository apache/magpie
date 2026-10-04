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
    "release-trains.md not found in <project-config> (looked in .apache-magpie-local/ then .apache-magpie-overrides/)",
    "archive destination for github-releases backend is not configured (archive_url_template missing)"
  ],
  "warnings": [],
  "values": {
    "non_asf": true,
    "dist_backend": "github-releases",
    "archive_url": null,
    "release_lines": []
  }
}
```
