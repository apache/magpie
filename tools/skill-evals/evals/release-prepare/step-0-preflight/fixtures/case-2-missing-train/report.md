<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare 3.0.0

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill prepare 3.0.0`):

```json
{
  "ok": true,
  "skill": "prepare",
  "blockers": [],
  "warnings": [],
  "values": {
    "sub_command": "plan",
    "version": "3.0.0",
    "release_branch_base": "main",
    "previous_tag": null,
    "release_lines": [
      "**`v2-11-test`** — the 2.x train; next release `2.11.0`."
    ],
    "organization": "ASF",
    "automated_signing_offered": true
  }
}
```

release-trains.md lists only the 2.x train; no entry exists for version 3.0.0 or any 3.x train.

gh pr list access confirmed: apache/airflow responds.
