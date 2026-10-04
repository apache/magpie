<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-rc-cut 2.12.0 rc0

Planning issue: apache/airflow#47000 (open, labelled `release-planning`,
title "Release Apache Airflow 2.12.0")
Planning issue body excerpt:
  Prep PR: apache/airflow#46990 — MERGED (label prep-pr-open absent)
  No RC tag exists yet for 2.12.0.

RC tag check: gh api repos/apache/airflow/git/refs/tags/2.12.0-rc0 → 404 (does not exist)

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill rc-cut 2.12.0 rc0`):

```json
{
  "ok": false,
  "skill": "rc-cut",
  "blockers": [
    "RC suffix 'rc0' does not match rc<N> with N >= 1 (e.g. rc1)"
  ],
  "warnings": [],
  "values": {
    "version": "2.12.0",
    "rc_number": null,
    "archive_reviewed": true,
    "allow_unreviewed_archive": false,
    "signing_mode": "rm-key",
    "staging_url": null,
    "rc_tag": null
  }
}
```
