<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare 2.11.0

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill prepare 2.11.0`):

```json
{
  "ok": true,
  "skill": "prepare",
  "blockers": [],
  "warnings": [],
  "values": {
    "sub_command": "plan",
    "version": "2.11.0",
    "release_branch_base": "main",
    "previous_tag": null,
    "release_lines": [
      "**`main`** — the 2.x train; next release `2.11.0`, Release Manager @jmclean."
    ],
    "organization": "ASF",
    "automated_signing_offered": true
  }
}
```

gh pr list access confirmed: apache/airflow responds with merged PRs.
Previous release tag detected: 2.10.3

.apache-magpie.local.lock matches .apache-magpie.lock — no drift.
No .apache-magpie-overrides/release-prepare.md found.
