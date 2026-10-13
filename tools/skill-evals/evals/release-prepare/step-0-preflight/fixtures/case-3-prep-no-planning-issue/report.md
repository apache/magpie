<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare prep 2.11.0
(no --planning-issue flag provided)

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill prepare prep 2.11.0`):

```json
{
  "ok": true,
  "skill": "prepare",
  "blockers": [],
  "warnings": [],
  "values": {
    "sub_command": "prep",
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

gh issue list search on apache/airflow: no open issue with label
  "release-planning" and "2.11.0" in the title was found.
  (The planning issue was never created; Step 1 was skipped.)

gh pr list access confirmed.

Facts for the verdict: no planning issue found (no `--planning-issue`); `gh pr list` access confirmed (`--gh-access`).

`release-management prepare verdict --preflight <scratch>/prepare-preflight.json --gh-access` output:

```json
{
  "verdict": "blocked",
  "sub_command": "prep",
  "version": "2.11.0",
  "blockers": [
    "No open issue labelled release-planning found for version 2.11.0; run Step 1 first or supply --planning-issue <url>"
  ],
  "release_branch_base": "main",
  "previous_tag": null,
  "train_covered": true,
  "read": []
}
```
